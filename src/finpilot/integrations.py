from __future__ import annotations

"""Optional, bounded integrations.

The repository does not launch a provider by default. The MCP client is a small
read-only JSON-RPC transport intended to be tested against an approved local
server. It deliberately accepts an explicit command list rather than a shell
string, and it never falls back to synthetic data when a live provider fails.
"""

import json
import os
import subprocess
import selectors
import math
import hashlib
from urllib.parse import urlparse
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .data import DataValidationError, Dataset, validate_as_of, validate_ticker
from .domain import Evidence, Observation
from .serialization import json_safe


class IntegrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class McpTool:
    name: str
    description: str = ""
    read_only: bool = True


class McpStdioClient:
    """Minimal MCP JSON-RPC client over newline-delimited stdio.

    A caller must provide an argv list. No shell parsing is performed. Methods
    are bounded by timeout and a maximum response size and only call explicitly
    allowlisted read-only tools.
    """

    def __init__(self, argv: Iterable[str], timeout: float = 20.0, max_response_bytes: int = 2_000_000, allowed_tools: Iterable[str] = ()):
        self.argv = tuple(argv)
        self.timeout = float(timeout)
        self.max_response_bytes = int(max_response_bytes)
        self.allowed_tools = frozenset(allowed_tools)
        self._counter = 0
        self._process: subprocess.Popen[str] | None = None

    def __enter__(self) -> "McpStdioClient":
        if not self.argv or any(not isinstance(arg, str) or not arg for arg in self.argv):
            raise IntegrationError("MCP argv must be a non-empty argument list")
        if self._process is not None:
            raise IntegrationError("MCP client is already open")
        if not 0 < self.timeout <= 120 or not 1 <= self.max_response_bytes <= 5_000_000:
            raise IntegrationError("invalid transport limits")
        # POSIX stdio transport; stderr cannot fill a pipe and block the child.
        env = {k: v for k, v in os.environ.items() if k in {'PATH', 'HOME', 'LANG', 'SYSTEMROOT', 'EDGAR_USER_AGENT'}}
        self._process = subprocess.Popen(self.argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0, shell=False, env=env)
        self._buffer = b''
        try:
            self._request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "finpilot", "version": "0.2.0"}})
            self._notify("notifications/initialized", {})
        except Exception:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self._process is not None:
            self._process.kill()
            self._process.wait(timeout=2)
            for stream in (self._process.stdin, self._process.stdout):
                if stream: stream.close()
            self._process = None

    def _send(self, payload: dict[str, Any]) -> None:
        if self._process is None or self._process.stdin is None:
            raise IntegrationError("MCP client is not open")
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        self._process.stdin.write((raw + "\n").encode('utf-8'))
        self._process.stdin.flush()

    def _readline(self) -> dict[str, Any]:
        if self._process is None or self._process.stdout is None:
            raise IntegrationError("MCP client is not open")
        deadline = time.monotonic() + self.timeout
        with selectors.DefaultSelector() as selector:
            selector.register(self._process.stdout, selectors.EVENT_READ)
            while time.monotonic() < deadline:
                while b'\n' in self._buffer:
                    line, self._buffer = self._buffer.split(b'\n', 1)
                    try:
                        value = json.loads(line)
                    except (ValueError, UnicodeError) as exc:
                        raise IntegrationError('MCP returned non-JSON output') from exc
                    if isinstance(value, dict) and ('id' in value or 'error' in value):
                        return value
                ready = selector.select(max(0, deadline - time.monotonic()))
                if not ready:
                    break
                chunk = os.read(self._process.stdout.fileno(), 65536)
                if not chunk:
                    break
                self._buffer += chunk
                if len(self._buffer) > self.max_response_bytes:
                    raise IntegrationError('MCP response exceeds configured size limit')
        raise IntegrationError('MCP response timed out or process exited')

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._counter += 1
        request_id = self._counter
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        response = self._readline()
        if response.get("id") != request_id:
            raise IntegrationError("MCP response id mismatch")
        if "error" in response:
            raise IntegrationError(f"MCP error for {method}: {response['error']}")
        return response.get("result", {})

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def list_tools(self) -> list[McpTool]:
        result = self._request("tools/list", {})
        tools = result.get("tools", [])
        if not isinstance(tools, list):
            raise IntegrationError("MCP tools/list result is not a list")
        return [McpTool(str(item["name"]), str(item.get("description", "")), str(item['name']) in self.allowed_tools) for item in tools if isinstance(item, dict) and item.get("name")]

    def call_read_only(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in self.allowed_tools:
            raise IntegrationError(f"MCP tool is not allowlisted: {name}")
        result = self._request("tools/call", {"name": name, "arguments": arguments})
        if result.get('isError'):
            raise IntegrationError('MCP tool reported an error')
        return result


def normalize_mcp_records(records: Iterable[dict[str, Any]], ticker: str, as_of: str, source: str) -> Dataset:
    """Normalize already-approved provider records; reject ambiguity, never guess."""
    symbol = validate_ticker(ticker)
    cutoff = validate_as_of(as_of)
    observations: list[Observation] = []
    evidence: list[Evidence] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise DataValidationError("provider record must be an object")
        required = ("metric", "value", "unit", "effective_at", "source_locator")
        if any(key not in record for key in required):
            raise DataValidationError(f"provider record missing one of {required}")
        if record["unit"] not in {"USD", "USD_mm", "percent", "shares", "date", "count"}:
            raise DataValidationError(f"unknown unit: {record['unit']}")
        metric = record['metric']
        if metric not in {'close','revenue','operating_income','free_cash_flow'}:
            raise DataValidationError('unsupported metric; explicit mapping required')
        if isinstance(record['value'], bool) or not isinstance(record['value'], (float,int)) or not math.isfinite(record['value']):
            raise DataValidationError('finite numeric value required')
        if record['unit'] not in {'USD','USD_mm'} or (metric == 'close' and (record['unit'] != 'USD' or record['value'] <= 0)):
            raise DataValidationError('incompatible unit/metric')
        if metric != 'close' and (not record.get('filed_at') or not record.get('period_start') or not record.get('period_end')):
            raise DataValidationError('filing date and reporting period required')
        effective_at = validate_as_of(str(record["effective_at"]))
        filed_at = record.get("filed_at")
        if filed_at is not None:
            filed_at = validate_as_of(str(filed_at))
        if effective_at > cutoff or (filed_at and filed_at > cutoff):
            continue
        locator = str(record["source_locator"])
        if urlparse(locator).scheme != 'https':
            raise DataValidationError('https source locator required')
        raw_hash = 'sha256:' + hashlib.sha256(json.dumps(record, sort_keys=True, allow_nan=False).encode()).hexdigest()
        evidence_id = f"ev-{source}-{index:04d}"
        evidence.append(Evidence(evidence_id, str(record.get("title", record["metric"])), source, locator, effective_at, str(record.get("excerpt", "provider record")), (str(record["metric"]),)))
        observations.append(Observation(symbol, str(record["metric"]), record["value"], str(record["unit"]), record.get("period_start"), record.get("period_end"), filed_at, effective_at, source, locator, raw_hash))
    return Dataset(observations, evidence, source, {"provenance": "caller-supplied records; source authenticity not independently verified", "ticker": symbol, "as_of": cutoff, "record_count": len(observations)})


class LlmClient:
    """Optional OpenAI-compatible bounded text adapter.

    It is not used by the offline pipeline. The caller supplies an opener in
    tests; production use must set the endpoint and key through environment
    variables and must send only approved summaries.
    """

    def __init__(self, endpoint: str, api_key: str | None = None, model: str = "local", timeout: float = 30, max_output_chars: int = 12_000, opener: Callable[..., Any] | None = None):
        parsed = urlparse(endpoint)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise IntegrationError('endpoint must not contain credentials/query/fragment')
        if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in {'localhost', '127.0.0.1', '::1'}):
            raise IntegrationError('require HTTPS or explicitly local HTTP')
        self.endpoint = endpoint.rstrip("/") + "/chat/completions"
        self.api_key = api_key
        self.model = model
        self.timeout = float(timeout)
        self.max_output_chars = int(max_output_chars)
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                raise IntegrationError('redirect rejected to protect credentials')
        self.opener = opener or urllib.request.build_opener(NoRedirect()).open

    @classmethod
    def from_env(cls) -> "LlmClient | None":
        endpoint = os.getenv("FINPILOT_LLM_ENDPOINT")
        if not endpoint:
            return None
        return cls(endpoint, os.getenv("FINPILOT_LLM_API_KEY"), os.getenv("FINPILOT_LLM_MODEL", "local"))

    def draft(self, context: dict[str, Any], evidence_ids: set[str], max_claims: int = 8) -> dict[str, Any]:
        if max_claims < 1 or max_claims > 20:
            raise IntegrationError("max_claims must be between 1 and 20")
        safe_context = json_safe(context)
        payload = {"model": self.model, "temperature": 0, "messages": [{"role": "system", "content": "Return JSON only with claims [{text,evidence_ids}]. Never invent numbers, evidence IDs, tools, or calculations."}, {"role": "user", "content": json.dumps(safe_context, ensure_ascii=False)}], "max_tokens": 1500}
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(self.endpoint, data=body, method="POST", headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {})})
        try:
            with self.opener(request, timeout=self.timeout) as response:
                raw = response.read(self.max_output_chars * 2)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise IntegrationError(f"LLM request failed: {exc}") from exc
        try:
            outer = json.loads(raw.decode("utf-8"))
            text = outer["choices"][0]["message"]["content"]
            output = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise IntegrationError("LLM response did not contain valid structured JSON") from exc
        claims = output.get("claims") if isinstance(output, dict) else None
        if not isinstance(claims, list) or len(claims) > max_claims:
            raise IntegrationError("LLM claims must be a bounded list")
        checked: list[dict[str, Any]] = []
        for claim in claims:
            if not isinstance(claim, dict) or not isinstance(claim.get("text"), str) or not isinstance(claim.get("evidence_ids"), list):
                raise IntegrationError("invalid LLM claim schema")
            ids = [str(item) for item in claim["evidence_ids"]]
            if not ids or not set(ids).issubset(evidence_ids):
                raise IntegrationError("LLM cited an evidence ID absent from the run")
            checked.append({"text": claim["text"][:self.max_output_chars], "evidence_ids": ids})
        usage = outer.get("usage", {}) if isinstance(outer, dict) else {}
        return {"status": "validated", "model": self.model, "claims": checked, "usage": json_safe(usage)}
