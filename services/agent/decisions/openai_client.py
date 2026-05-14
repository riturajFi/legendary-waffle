import json
import os
from typing import Any, Dict, Optional

from .prompts import SYSTEM_PROMPT, build_user_prompt


class OpenAiDecisionClient:
    def __init__(self, model: Optional[str] = None):
        self._load_dotenv()
        self.model = model or os.getenv("OPENAI_DECISION_MODEL") or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    def available(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))

    def decide(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if not self.available():
            raise RuntimeError("OPENAI_API_KEY not set")

        from openai import OpenAI

        client = OpenAI()
        response = client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(context)},
            ],
            max_output_tokens=500,
        )
        return self._parse_json(response.output_text)

    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise
            return json.loads(text[start : end + 1])

    @staticmethod
    def _load_dotenv() -> None:
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except Exception:
            return
