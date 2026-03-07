import requests
from pathlib import Path

import yaml

from academic_intelligence_ai.monitoring.logger import get_logger

logger = get_logger("query.llm_client")

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def load_config() -> dict:
    """Load configuration from config/config.yaml."""
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


class LLMClient:
    """Client for communicating with a local Ollama LLM instance."""

    def __init__(self):
        config = load_config()
        llm_cfg = config.get("llm", {})

        self.model = llm_cfg.get("model", "mistral")
        self.base_url = llm_cfg.get("base_url", "http://localhost:11434")
        self.max_tokens = llm_cfg.get("max_tokens", 512)
        self.temperature = llm_cfg.get("temperature", 0.2)

        logger.info("LLM client initialized: model=%s, url=%s", self.model, self.base_url)

    def generate(self, prompt: str) -> dict:
        """Send a prompt to Ollama and return response with metrics.

        Returns a dict with keys: answer, prompt_tokens, response_tokens, latency_ms.
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": self.max_tokens,
                "temperature": self.temperature,
            },
        }

        logger.debug("Sending prompt to LLM (%d chars)", len(prompt))

        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()

        result = response.json()
        answer = result.get("response", "").strip()

        prompt_tokens = result.get("prompt_eval_count", 0)
        response_tokens = result.get("eval_count", 0)
        total_ns = result.get("total_duration", 0)
        latency_ms = round(total_ns / 1e6)

        logger.info(
            "LLM response: %d chars, tokens=%d+%d, latency=%dms",
            len(answer), prompt_tokens, response_tokens, latency_ms,
        )

        return {
            "answer": answer,
            "prompt_tokens": prompt_tokens,
            "response_tokens": response_tokens,
            "latency_ms": latency_ms,
        }
