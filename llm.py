from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable


def _extract_json(text: str) -> Any:
    fenced = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL)
    candidates = fenced + [text]
    for candidate in candidates:
        candidate = candidate.strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    raise ValueError("No valid JSON object found in LLM response.")


class LLMClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.base_url = os.getenv(
            "OPENAI_BASE_URL",
            "https://api.openai.com/v1/chat/completions",
        )
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key or self.gemini_api_key)

    def _gemini_complete_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.gemini_model}:generateContent?key="
            f"{urllib.parse.quote(self.gemini_api_key or '')}"
        )
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                f"System instructions:\n{system_prompt}\n\n"
                                f"User request:\n{user_prompt}"
                            )
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
            },
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()

    def complete_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        fallback: Callable[[], str],
    ) -> str:
        if not self.enabled:
            return fallback()

        try:
            if self.gemini_api_key:
                return self._gemini_complete_text(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )

            payload = {
                "model": self.model,
                "temperature": 0.7,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
            request = urllib.request.Request(
                self.base_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
        except (urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError):
            return fallback()

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        fallback: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        text = self.complete_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            fallback=lambda: json.dumps(fallback(), indent=2),
        )
        try:
            result = _extract_json(text)
        except ValueError:
            return fallback()
        return result if isinstance(result, dict) else fallback()

