"""Launch the Phase-1 AI Writing Partner chat.

    py -3 chat.py --project ./MyProject

Reads settings from appsettings.json / appsettings.local.json and the Gemini API
key from Source/.env (GEMINI_API_KEY) or the environment. Without a key the chat
is disabled but all management commands still work.
"""

from __future__ import annotations

from app.chat_cli import main

if __name__ == "__main__":
    main()
