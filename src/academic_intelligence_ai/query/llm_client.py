import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from openai import OpenAI

from academic_intelligence_ai.monitoring.logger import get_logger

logger = get_logger("query.llm_client")

PROJECT_ROOT = Path(__file__).resolve().parents[3]

load_dotenv(PROJECT_ROOT / ".env")


def _load_config() -> dict:
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


class LLMClient:
    """OpenAI API client. Stateless — passes messages through, does not interpret content."""

    def __init__(self):
        config = _load_config()
        llm_cfg = config.get("llm", {})

        self.model = llm_cfg.get("model", "gpt-4o-mini")
        self.max_tokens = llm_cfg.get("max_tokens", 512)
        self.temperature = llm_cfg.get("temperature", 0.2)

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set in environment or .env file")

        self.client = OpenAI(api_key=api_key)
        logger.info("LLM client initialized: model=%s", self.model)

    def generate(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """Send messages to OpenAI and return response with metrics.

        Returns a dict with keys:
          - type: "text" | "tool_call"
          - answer: str (if type == "text")
          - tool_name: str, tool_arguments: dict (if type == "tool_call")
          - prompt_tokens, response_tokens, latency_ms
        """
        import time

        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        start = time.perf_counter()
        response = self.client.chat.completions.create(**kwargs)
        latency_ms = round((time.perf_counter() - start) * 1000)

        message = response.choices[0].message
        usage = response.usage

        prompt_tokens = usage.prompt_tokens if usage else 0
        response_tokens = usage.completion_tokens if usage else 0

        if message.tool_calls:
            tool_call = message.tool_calls[0]
            import json
            logger.info(
                "LLM tool call: %s, tokens=%d+%d, latency=%dms",
                tool_call.function.name, prompt_tokens, response_tokens, latency_ms,
            )
            return {
                "type": "tool_call",
                "tool_name": tool_call.function.name,
                "tool_arguments": json.loads(tool_call.function.arguments),
                "tool_call_id": tool_call.id,
                "prompt_tokens": prompt_tokens,
                "response_tokens": response_tokens,
                "latency_ms": latency_ms,
            }

        answer = message.content.strip() if message.content else ""
        logger.info(
            "LLM response: %d chars, tokens=%d+%d, latency=%dms",
            len(answer), prompt_tokens, response_tokens, latency_ms,
        )
        return {
            "type": "text",
            "answer": answer,
            "prompt_tokens": prompt_tokens,
            "response_tokens": response_tokens,
            "latency_ms": latency_ms,
        }
