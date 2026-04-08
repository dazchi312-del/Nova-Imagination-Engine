"""
Nova App Builder - AI Engine
Bridge between Nova and the local LLM (LM Studio)
Handles generation, retry, token tracking, conversation history
"""

from __future__ import annotations

import time
import json
from pathlib import Path
from typing import Any

import httpx

from core.errors import NovaEngineError
from core.logger import session_logger, LogLevel


class AIEngine:
    """
    Manages all communication with the local LLM.
    Designed for autonomous App Builder workflows.
    """

    MAX_RETRIES = 3
    RETRY_DELAY = 2.0  # seconds between retries

    def __init__(self, config_path: str = "nova_config.json") -> None:
        self.config = self._load_config(config_path)

        lm = self.config["lm_studio"]
        generation = self.config["generation"]

        self.base_url: str       = lm["base_url"].rstrip("/")
        self.chat_endpoint: str  = lm["chat_endpoint"]
        self.model: str          = lm["model"]
        self.timeout_seconds: int = lm["timeout_seconds"]

        self.default_temperature: float = generation["temperature"]
        self.default_max_tokens: int    = generation["max_tokens"]
        self.default_stream: bool       = generation["stream"]

        self.system_prompt: str = self.config["system_prompt"]
        self.url: str           = f"{self.base_url}{self.chat_endpoint}"

        # Token usage tracking across the session
        self.total_prompt_tokens:     int = 0
        self.total_completion_tokens: int = 0

        session_logger.log(
            f"AIEngine ready: {self.model} @ {self.base_url}",
            LogLevel.SYSTEM,
            {"model": self.model, "endpoint": self.url}
        )

    def _load_config(self, config_path: str) -> dict[str, Any]:
        path = Path(config_path)
        if not path.exists():
            raise NovaEngineError(f"Missing config file: {config_path}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise NovaEngineError(f"Invalid JSON in config: {exc}") from exc

    def generate(
        self,
        user_input: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """
        Send a single user message, get a response.
        Standard generation for simple exchanges.
        """
        if not user_input or not user_input.strip():
            raise NovaEngineError("User input is empty.")

        messages = [
            {"role": "system", "content": system_prompt or self.system_prompt},
            {"role": "user",   "content": user_input.strip()},
        ]

        return self._send(messages, temperature=temperature, max_tokens=max_tokens)

    def generate_with_history(
        self,
        messages: list[dict],
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """
        Send a full conversation history, get a response.
        Used for multi-turn conversations and planning loops.

        messages format:
            [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]
        """
        if not messages:
            raise NovaEngineError("Message history is empty.")

        full_messages = [
            {"role": "system", "content": system_prompt or self.system_prompt},
            *messages
        ]

        return self._send(full_messages, temperature=temperature, max_tokens=max_tokens)

    def _send(
        self,
        messages: list[dict],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """
        Internal send with retry logic and token tracking.
        """
        generation = self.config["generation"]

        payload = {
            "model":             self.model,
            "messages":          messages,
            "temperature":       self.default_temperature if temperature is None else temperature,
            "max_tokens":        self.default_max_tokens  if max_tokens  is None else max_tokens,
            "stream":            False,  # always False — streaming handled separately later
            "top_p":             generation.get("top_p", 0.9),
            "frequency_penalty": generation.get("frequency_penalty", 0.0),
            "presence_penalty":  generation.get("presence_penalty", 0.0),
        }

        last_error = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                session_logger.log(
                    f"LLM request attempt {attempt}/{self.MAX_RETRIES}",
                    LogLevel.SYSTEM
                )

                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(self.url, json=payload)
                    response.raise_for_status()
                    data = response.json()

                # Track token usage if LM Studio returns it
                usage = data.get("usage", {})
                prompt_tokens     = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                self.total_prompt_tokens     += prompt_tokens
                self.total_completion_tokens += completion_tokens

                session_logger.log(
                    "LLM response received",
                    LogLevel.SYSTEM,
                    {
                        "prompt_tokens":     prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_session_tokens": self.total_prompt_tokens + self.total_completion_tokens
                    }
                )

                return data["choices"][0]["message"]["content"].strip()

            except httpx.TimeoutException as exc:
                last_error = NovaEngineError(f"LM Studio timed out (attempt {attempt})")
                session_logger.log(
                    f"Timeout on attempt {attempt}",
                    LogLevel.SYSTEM,
                    {"attempt": attempt, "will_retry": attempt < self.MAX_RETRIES}
                )

            except httpx.HTTPStatusError as exc:
                last_error = NovaEngineError(
                    f"HTTP {exc.response.status_code}: {exc.response.text}"
                )
                session_logger.log(
                    f"HTTP error on attempt {attempt}: {exc.response.status_code}",
                    LogLevel.SYSTEM
                )

            except httpx.RequestError as exc:
                last_error = NovaEngineError(f"Connection failed: {exc}")
                session_logger.log(
                    f"Connection error on attempt {attempt}",
                    LogLevel.SYSTEM,
                    {"error": str(exc)}
                )

            except (KeyError, IndexError, TypeError) as exc:
                # Bad response structure — don't retry, it won't fix itself
                raise NovaEngineError(
                    f"Unexpected LM Studio response structure: {data}"
                ) from exc

            except ValueError as exc:
                raise NovaEngineError(f"Invalid JSON response: {exc}") from exc

            # Wait before retry (except on last attempt)
            if attempt < self.MAX_RETRIES:
                time.sleep(self.RETRY_DELAY)

        # All retries exhausted
        raise last_error

    def token_usage(self) -> dict:
        """Return total token usage for this session."""
        return {
            "prompt_tokens":     self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "total":             self.total_prompt_tokens + self.total_completion_tokens
        }
