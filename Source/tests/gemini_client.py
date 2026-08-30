import json
import os
import requests

from ai import load_settings


# ========================================
# API KEY CONFIGURATION
# ========================================
# Set GEMINI_API_KEY in Source/.env or as an environment variable.
API_KEY = os.getenv("GEMINI_API_KEY") or load_settings().ai.api_key


class GeminiClient:

    BASE_URL = (
        "https://generativelanguage.googleapis.com"
        "/v1beta/models/"
        "gemini-2.5-flash:generateContent"
    )

    def __init__(self, api_key: str = None):
        if api_key is None:
            api_key = API_KEY
        
        if not api_key:
            raise ValueError(
                "API key not set. "
                "Please set GEMINI_API_KEY in Source/.env or as an environment variable."
            )
        self.api_key = api_key

    def generate(
        self,
        prompt: str,
    ) -> str:

        response = requests.post(
            self.BASE_URL,
            params={
                "key": self.api_key,
            },
            headers={
                "Content-Type":
                "application/json",
            },
            json={
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt,
                            }
                        ]
                    }
                ]
            },
            timeout=120,
        )

        response.raise_for_status()

        data = response.json()

        return (
            data["candidates"][0]
            ["content"]["parts"][0]
            ["text"]
        )