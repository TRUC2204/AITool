"""AIWritingPartner — the Phase-1 orchestrator (Definition of Done).

One object the user talks to. It grounds every answer in project data, proposes
changes instead of writing them, lets the user review / approve / reject /
commit / undo, honours Internet Mode, and records a full observable trace so any
misbehaviour can be reconstructed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from knowledge_graph import KnowledgeGraph

from ai import (
    AgentLimits,
    AgentRuntime,
    AppSettings,
    CostRates,
    CostTracker,
    IAIProvider,
    ObservedProvider,
    ToolCallLog,
    ToolContext,
    build_partner_tools,
)
from changes import (
    Change,
    ChangeHistory,
    ChangeStatus,
    CommitEngine,
    CommitRecord,
    Proposal,
    UndoManager,
    UndoResult,
)
from grounding import (
    NO_EVIDENCE_MESSAGE,
    EvidenceTracker,
    KnowledgeMode,
    KnowledgeModeController,
    SourceRef,
)
from memory import (
    ConsistencyIssue,
    LongTermMemory,
    MemoryPromotion,
    WorkingMemory,
)
from observability import (
    DiagnosticPackage,
    ErrorCategory,
    ErrorTracker,
    EventLog,
    EventType,
    render_full_debug,
)
from retrieval import (
    ContextCache,
    KnowledgeRetrievalService,
    RetrievalLimits,
    SearchService,
)

_SYSTEM_BASE = (
    "You are an AI writing partner for a personal fiction / world-building project. "
    "The project's Knowledge Graph is your long-term memory and the ONLY authority "
    "on this world.\n\n"
    "WORKFLOW (multi-step, FR-07):\n"
    "1. Use SearchNode / GetNode / GetRelatedNodes to gather relevant project data "
    "before answering. Plan your own retrieval; the user will not point you to nodes.\n"
    "2. To change the world, DO NOT write directly. Stage changes with "
    "ProposeCreateNode / ProposeUpdateNode / ProposeDeleteNode / ProposeLinkNodes, "
    "each with a clear reason. The user reviews and approves before anything is saved.\n"
    "3. Answer concisely and name the nodes you relied on.\n"
    "You only ever operate on THIS project (FR-21)."
)


@dataclass
class ChatTurn:
    answer: str
    sources: list[SourceRef] = field(default_factory=list)
    proposal: Optional[Proposal] = None
    tool_calls: list[ToolCallLog] = field(default_factory=list)
    stop_reason: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    no_evidence: bool = False

    @property
    def has_proposal(self) -> bool:
        return self.proposal is not None and not self.proposal.is_empty


class AIWritingPartner:
    def __init__(
        self,
        graph: KnowledgeGraph,
        provider: Optional[IAIProvider] = None,
        limits: Optional[AgentLimits] = None,
        cost_rates: Optional[CostRates] = None,
        event_log: Optional[EventLog] = None,
    ) -> None:
        self.graph = graph
        self._provider = provider
        self.limits = limits or AgentLimits()

        self.event_log = event_log or EventLog()
        self.errors = ErrorTracker(self.event_log)
        self.knowledge_mode = KnowledgeModeController(event_log=self.event_log)
        self.cost = CostTracker(cost_rates)
        self.cache = ContextCache()

        self.search = SearchService(graph)
        self.retrieval = KnowledgeRetrievalService(
            graph, RetrievalLimits(max_nodes=self.limits.max_nodes_loaded,
                                   max_depth=self.limits.max_relationship_depth)
        )
        self.long_term = LongTermMemory(graph)
        self.promotion = MemoryPromotion()

        self.history = ChangeHistory()
        self.commit_engine = CommitEngine(graph, self.history, self.event_log, self.errors)
        self.undo_manager = UndoManager(graph, self.history, self.event_log)

        self.sessions: dict[str, WorkingMemory] = {}
        self.current: Optional[WorkingMemory] = None
        self.settings: Optional[AppSettings] = None
        self._proposal_counter = 0
        self._last_turn: Optional[ChatTurn] = None
        self._last_evidence = EvidenceTracker()

    @property
    def has_provider(self) -> bool:
        return self._provider is not None

    # -- session management (FR-13, Epic 8) --------------------------------
    def start_session(self, session_id: Optional[str] = None) -> WorkingMemory:
        session_id = session_id or f"S{len(self.sessions) + 1:03d}"
        working = WorkingMemory(session_id)
        self.sessions[session_id] = working
        self.current = working
        self.event_log.emit(
            EventType.SESSION, f"session {session_id} started", session_id=session_id
        )
        return working

    def _require_session(self) -> WorkingMemory:
        if self.current is None:
            return self.start_session()
        return self.current

    # -- knowledge mode (FR-03, Epic 4) ------------------------------------
    def set_internet_mode(self, enabled: bool) -> KnowledgeMode:
        session_id = self.current.session_id if self.current else None
        if enabled:
            self.knowledge_mode.enable_external(session_id)
        else:
            self.knowledge_mode.disable_external(session_id)
        return self.knowledge_mode.mode

    # -- the one conversational entry point --------------------------------
    def chat(self, text: str) -> ChatTurn:
        if self._provider is None:
            raise RuntimeError(
                "No AI provider configured. Set GEMINI_API_KEY and pass a provider."
            )
        working = self._require_session()
        working.add_message("user", text)

        evidence = EvidenceTracker()
        self._last_evidence = evidence

        def _active_proposal() -> Proposal:
            if working.active_proposal is None:
                working.set_active_proposal(self._new_proposal(working))
            return working.active_proposal

        ctx = ToolContext(
            graph=self.graph,
            retrieval=self.retrieval,
            search=self.search,
            evidence=evidence,
            cache=self.cache,
            event_log=self.event_log,
            consistency=self.long_term.consistency,
            get_active_proposal=_active_proposal,
            session_id=working.session_id,
        )
        registry = build_partner_tools(ctx)
        provider = ObservedProvider(
            self._provider, self.event_log, self.cost, self.errors, working.session_id
        )
        agent = AgentRuntime(
            provider, registry, self.limits, system_prompt=self._system_prompt(working)
        )

        try:
            result = agent.run(text)
        except Exception as exc:  # noqa: BLE001 - surfaced through error tracker
            self.errors.capture(exc, ErrorCategory.AI, session_id=working.session_id)
            raise

        self._log_tool_calls(result.tool_calls, working.session_id)

        proposal = working.active_proposal if working.active_proposal and not working.active_proposal.is_empty else None
        no_evidence = (
            not self.knowledge_mode.is_external_allowed
            and not evidence.has_internal_evidence
            and proposal is None
        )
        answer = self._compose_answer(result.final_text, evidence, no_evidence)
        working.add_message("assistant", answer)

        turn = ChatTurn(
            answer=answer,
            sources=evidence.sources(),
            proposal=proposal,
            tool_calls=result.tool_calls,
            stop_reason=result.stop_reason,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            no_evidence=no_evidence,
        )
        self._last_turn = turn
        return turn

    # -- review / approve / reject (FR-10, Epic 6) -------------------------
    def active_proposal(self) -> Optional[Proposal]:
        return self.current.active_proposal if self.current else None

    def validate_proposal(self) -> list[ConsistencyIssue]:
        proposal = self.active_proposal()
        return self.long_term.validate_proposal(proposal) if proposal else []

    def approve(self, change_ids: Optional[list[str]] = None) -> int:
        proposal = self.active_proposal()
        if proposal is None:
            return 0
        targets = change_ids or [c.id for c in proposal.pending()]
        count = 0
        for change_id in targets:
            change = proposal.get(change_id)
            if change and change.status == ChangeStatus.PENDING:
                change.status = ChangeStatus.APPROVED
                count += 1
        self._log_review(proposal, "approve", count)
        return count

    def reject(self, change_ids: Optional[list[str]] = None) -> int:
        proposal = self.active_proposal()
        if proposal is None:
            return 0
        targets = change_ids or [c.id for c in proposal.pending()]
        count = 0
        for change_id in targets:
            change = proposal.get(change_id)
            if change and change.status == ChangeStatus.PENDING:
                change.status = ChangeStatus.REJECTED
                count += 1
        self._log_review(proposal, "reject", count)
        return count

    def edit_change(
        self,
        change_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
    ) -> bool:
        """Edit a staged change before commit (Epic 6 - Edit proposal)."""
        proposal = self.active_proposal()
        if proposal is None:
            return False
        change = proposal.get(change_id)
        if change is None:
            return False
        if title is not None:
            change.title = title
        if content is not None:
            change.content = content
        return True

    def commit(self) -> Optional[CommitRecord]:
        proposal = self.active_proposal()
        if proposal is None or not proposal.approved():
            return None
        record = self.commit_engine.commit(proposal, self.current.session_id)
        self.cache.bump_revision()  # invalidate stale reads after a write
        if self.current:
            self.current.clear_proposal()
        return record

    def discard_proposal(self) -> None:
        if self.current:
            self.current.clear_proposal()

    # -- undo / restore (FR-12, Epic 7) ------------------------------------
    def undo_last(self) -> Optional[UndoResult]:
        result = self.undo_manager.undo_last()
        if result is not None:
            self.cache.bump_revision()
        return result

    def undo(self, record_id: str) -> UndoResult:
        result = self.undo_manager.undo_record(record_id)
        self.cache.bump_revision()
        return result

    # -- memory promotion (FR-18, Epic 3) ----------------------------------
    def promote_assumptions(self) -> Optional[Proposal]:
        working = self._require_session()
        candidates = self.promotion.candidates_from_assumptions(working)
        if not candidates:
            return None
        proposal = self.promotion.build_proposal(
            candidates, self._next_proposal_id(working), working.session_id
        )
        working.set_active_proposal(proposal)
        self.event_log.emit(
            EventType.MEMORY_PROMOTION,
            f"proposed promoting {len(candidates)} fact(s)",
            session_id=working.session_id,
            count=len(candidates),
        )
        return proposal

    # -- panels & diagnostics (Epic 8 & 10) --------------------------------
    def context_panel(self) -> str:
        if self._last_turn is None:
            return "Context panel: (no turn yet)"
        lines = ["[CONTEXT PANEL]", self._last_evidence.render_attribution(), ""]
        lines.append("Tools called:")
        for call in self._last_turn.tool_calls:
            lines.append(f"  - {call.name} ({'ok' if call.ok else 'fail'})")
        if self.current:
            snap = self.current.snapshot()
            lines.extend(
                ["", f"Goal: {snap['goal']}", f"Summary: {snap['summary']}",
                 f"Assumptions: {', '.join(snap['assumptions']) or '(none)'}"]
            )
        return "\n".join(lines)

    def change_panel(self) -> str:
        proposal = self.active_proposal()
        if proposal is None or proposal.is_empty:
            return "[CHANGE PANEL]\n(no pending changes)"
        return "[CHANGE PANEL]\n" + proposal.render()

    def debug_view(self) -> str:
        session_id = self.current.session_id if self.current else None
        return render_full_debug(self.event_log, session_id)

    def export_diagnostics(self, directory: str) -> str:
        package = DiagnosticPackage(self.event_log, self.errors)
        session_id = self.current.session_id if self.current else None
        return package.export(directory, session_id)

    def history_view(self) -> list[CommitRecord]:
        return self.history.records()

    def search_history(self, text: str) -> list[CommitRecord]:
        return self.history.search(text)

    # -- internals ---------------------------------------------------------
    def _new_proposal(self, working: WorkingMemory) -> Proposal:
        return Proposal(
            id=self._next_proposal_id(working),
            session_id=working.session_id,
            summary="AI-proposed changes",
        )

    def _next_proposal_id(self, working: WorkingMemory) -> str:
        self._proposal_counter += 1
        return f"{working.session_id}-P{self._proposal_counter}"

    def _system_prompt(self, working: WorkingMemory) -> str:
        parts = [_SYSTEM_BASE, self.knowledge_mode.directive()]
        if working.current_goal:
            parts.append(f"CURRENT GOAL: {working.current_goal}")
        if working.discussion_summary:
            parts.append(f"DISCUSSION SO FAR: {working.discussion_summary}")
        if working.assumptions:
            parts.append("WORKING ASSUMPTIONS:\n- " + "\n- ".join(working.assumptions))
        history = working.history_text(limit=6)
        if history:
            parts.append(f"RECENT MESSAGES:\n{history}")
        return "\n\n".join(parts)

    def _compose_answer(
        self, text: Optional[str], evidence: EvidenceTracker, no_evidence: bool
    ) -> str:
        if no_evidence and not text:
            return NO_EVIDENCE_MESSAGE
        body = text or (NO_EVIDENCE_MESSAGE if no_evidence else "")
        if evidence.has_internal_evidence:
            return f"{body}\n\n{evidence.render_attribution()}"
        return body

    def _log_tool_calls(self, tool_calls: list[ToolCallLog], session_id: str) -> None:
        for call in tool_calls:
            self.event_log.emit(
                EventType.TOOL_CALL,
                call.name,
                session_id=session_id,
                iteration=call.iteration,
                args=call.args,
                ok=call.ok,
                error=call.error,
            )

    def _log_review(self, proposal: Proposal, action: str, count: int) -> None:
        self.event_log.emit(
            EventType.PROPOSAL_REVIEWED,
            f"{action} {count} change(s) in {proposal.id}",
            session_id=proposal.session_id,
            action=action,
            count=count,
        )
