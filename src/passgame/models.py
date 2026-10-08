"""Diagnostic adapters and an explicitly configured chat-completions endpoint.

Request schema verified against:
https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create
No model names, provider prices or credentials are guessed.
"""

from dataclasses import dataclass
import os
import math
import time
from urllib.parse import urlparse
import httpx

from .constraints import Rule
from .oracle import new_only
import json


class BudgetExceeded(RuntimeError):
    pass


class InfrastructureError(RuntimeError):
    pass


@dataclass
class Response:
    raw: str
    provider_response: dict
    attempts: int
    latency_seconds: float
    usage: dict
    cost_reserved: float = 0.0


class Budget:
    """Conservative reservations are never refunded, including retries/timeouts."""
    def __init__(self, limit: float, reserved: float = 0.0):
        if not math.isfinite(limit) or not math.isfinite(reserved) or limit < 0 or reserved < 0:
            raise ValueError("Budget cannot be negative")
        self.limit, self.reserved = limit, reserved

    def reserve(self, maximum_cost: float):
        if not math.isfinite(maximum_cost) or maximum_cost < 0 or self.reserved + maximum_cost > self.limit + 1e-12:
            raise BudgetExceeded("Spending ceiling reached before sending the next request")
        self.reserved += maximum_cost


class DiagnosticAdapter:
    def __init__(self, name: str):
        if name not in {"reference_oracle", "unchanged", "new_only"}:
            raise ValueError(f"Unknown diagnostic: {name}")
        self.name = name

    def complete(self, messages: list[dict], context: dict) -> Response:
        start = time.monotonic()
        if self.name == "reference_oracle":
            artifact = context["witness"]
        elif self.name == "new_only":
            artifact = new_only(context["current"], Rule.from_dict(context["new_rule"]))
        else:
            artifact = context["current"]
        raw = json.dumps({"password": artifact})
        return Response(raw, {"adapter": self.name, "diagnostic_not_llm": True}, 1, time.monotonic()-start, {})


class ChatAdapter:
    def __init__(self, config: dict, budget: Budget, reserve_callback=None, transport=None):
        self.config, self.budget, self.reserve_callback = config, budget, reserve_callback
        endpoint = config["base_url"].rstrip("/")
        parsed = urlparse(endpoint)
        if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}):
            raise ValueError("Use HTTPS for remote endpoints")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Endpoint URL cannot contain credentials or query arguments")
        self.endpoint = endpoint + "/chat/completions"
        key_env = config.get("api_key_env")
        key = os.environ.get(key_env) if key_env else None
        if key_env and not key:
            raise ValueError(f"Missing credential environment variable: {key_env}")
        self.headers = {"Authorization": f"Bearer {key}"} if key else {}
        self.client = httpx.Client(timeout=config.get("timeout_seconds", 90), transport=transport)
        self.parameters = config.get("parameters", {"max_completion_tokens": 256})
        if any(k in self.parameters for k in {"messages", "model", "stream", "n", "tools", "response_format"}):
            raise ValueError("Parameters cannot override core protocol fields or enable tool/schema assistance")
        cap = self.parameters.get("max_completion_tokens", self.parameters.get("max_tokens"))
        if type(cap) is not int or cap <= 0:
            raise ValueError("A positive completion-token cap is required")
        self.output_cap = cap
        self.input_price = float(config["input_price_per_million"])
        self.output_price = float(config["output_price_per_million"])
        if not math.isfinite(self.input_price) or not math.isfinite(self.output_price) or self.input_price < 0 or self.output_price < 0:
            raise ValueError("Prices must be nonnegative")

    def complete(self, messages: list[dict], context: dict) -> Response:
        payload = {"model": self.config["model_id"], "messages": messages, "stream": False, **self.parameters}
        # User sets a verified hard prompt token ceiling; over-reserve at that ceiling.
        # Byte bound + explicit per-message overhead is a deliberately loose preflight.
        input_cap = int(self.config["max_input_tokens"])
        byte_bound = sum(len(m["content"].encode("utf-8"))+32 for m in messages)+32
        if byte_bound > input_cap:
            raise ValueError("Conservative prompt bound exceeds configured max_input_tokens")
        reserve = (input_cap*self.input_price + self.output_cap*self.output_price)/1e6
        total_reserved, start = 0.0, time.monotonic()
        retries = int(self.config.get("transport_retries", 2))
        for attempt in range(retries+1):
            self.budget.reserve(reserve)
            total_reserved += reserve
            if self.reserve_callback:
                self.reserve_callback(self.budget.reserved)
            try:
                result = self.client.post(self.endpoint, headers=self.headers, json=payload)
            except httpx.TransportError:
                if attempt < retries:
                    time.sleep(min(2**attempt, 4))
                    continue
                raise InfrastructureError("Transport failure; reservation retained") from None
            if result.status_code == 429 or result.status_code >= 500:
                if attempt < retries:
                    time.sleep(min(2**attempt, 4))
                    continue
                raise InfrastructureError(f"HTTP {result.status_code}; retry cap reached")
            if result.status_code >= 400:
                raise InfrastructureError(f"HTTP {result.status_code}; request rejected")
            try:
                body = result.json()
                raw = body["choices"][0]["message"].get("content") or ""
                usage = body.get("usage", {})
            except (ValueError, KeyError, IndexError, TypeError):
                raise InfrastructureError("Provider returned an invalid response envelope") from None
            if not isinstance(raw, str):
                raise InfrastructureError("Provider content was not a text string")
            return Response(raw, body, attempt+1, time.monotonic()-start, usage, total_reserved)
        raise AssertionError("Unreachable")

    def close(self):
        self.client.close()
