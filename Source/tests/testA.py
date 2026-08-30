from google import genai

from ai import load_settings


def main() -> None:
    settings = load_settings()
    if not settings.ai.api_key:
        raise SystemExit("No API key. Set GEMINI_API_KEY in Source/.env.")
    client = genai.Client(api_key=settings.ai.api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Giới thiệu về Luffy đi.",
    )
    print(response.text.encode("utf-8", errors="replace").decode("utf-8"))


if __name__ == "__main__":
    main()