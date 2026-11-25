"""Optional OpenAI narration for deterministic research results."""

from __future__ import annotations

import json
import logging

import httpx
from pydantic import SecretStr

from app.agents.research_agent.prompts import RESEARCH_INTERPRETATION_INSTRUCTIONS
from app.agents.research_agent.schemas import ResearchReport

logger = logging.getLogger(__name__)


class ResearchNarrator:
    """Explain computed evidence while leaving all signals to Python code."""

    endpoint = "https://api.openai.com/v1/responses"

    def __init__(self, api_key: SecretStr | None, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def interpret(self, report: ResearchReport) -> tuple[str, str]:
        if self.api_key is None:
            return self._deterministic_summary(report), "deterministic"
        try:
            response = httpx.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key.get_secret_value()}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "instructions": RESEARCH_INTERPRETATION_INSTRUCTIONS,
                    "input": json.dumps(self._facts(report), allow_nan=False),
                    "max_output_tokens": 240,
                },
                timeout=20.0,
            )
            response.raise_for_status()
            text = self._output_text(response.json())
            if text:
                return text, "openai"
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            logger.warning("Research narration unavailable; using deterministic summary: %s", exc)
        return self._deterministic_summary(report), "deterministic"

    @staticmethod
    def _facts(report: ResearchReport) -> dict:
        return {
            "ticker": report.ticker,
            "latest_price": report.latest_price,
            "indicators": report.indicators,
            "signal": report.signal.value,
            "strategy_votes": {
                "buy": report.decision.buy_votes,
                "sell": report.decision.sell_votes,
                "hold": report.decision.hold_votes,
            },
            "strategies": [
                {
                    "name": result.strategy,
                    "signal": result.signal.value,
                    "evidence": result.evidence,
                }
                for result in report.decision.strategies
            ],
            "limitations": report.limitations,
        }

    @staticmethod
    def _output_text(payload: dict) -> str:
        for item in payload.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text" and content.get("text", "").strip():
                    return content["text"].strip()
        return ""

    @staticmethod
    def _deterministic_summary(report: ResearchReport) -> str:
        votes = report.decision
        summary = (
            f"{report.ticker} has a deterministic {report.signal.value} research signal "
            f"based on {votes.buy_votes} buy, {votes.sell_votes} sell, and "
            f"{votes.hold_votes} hold strategy votes."
        )
        if report.signal.value == "INSUFFICIENT_DATA":
            summary += " There is not enough history to form a combined signal."
        return summary
