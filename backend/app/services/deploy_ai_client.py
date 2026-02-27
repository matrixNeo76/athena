"""
ATHENA - Deploy.AI / Complete.dev HTTP client
TODO-2: Implements authentication + chat + message calls against the Deploy.AI Core API.

Adds exponential-backoff retry (3 attempts, 1s/2s/4s delays) for transient
network failures (NetworkError, TimeoutException, ConnectError).

Public interface:
    get_access_token()              → str
    create_chat(agent_id)           → str
    send_message(chat_id, content)  → str
    call_agent(agent_id, prompt)    → str  (convenience one-shot wrapper)
"""
import asyncio
import logging
import time
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Error ─────────────────────────────────────────────────────────────────────

class DeployAIError(Exception):
    def __init__(self, operation: str, status_code: int, detail: str):
        self.operation   = operation
        self.status_code = status_code
        self.detail      = detail
        super().__init__(f"[DeployAI] '{operation}' failed ({status_code}): {detail}")


# ── Token cache ───────────────────────────────────────────────────────────────

_token_cache: dict = {"token": None, "expires_at": 0.0}
_TOKEN_EXPIRY_BUFFER_SEC = 60


def _is_token_valid() -> bool:
    return (
        _token_cache["token"] is not None
        and time.time() < _token_cache["expires_at"] - _TOKEN_EXPIRY_BUFFER_SEC
    )


def _auth_headers(token: str) -> dict:
    return {
        "accept":        "application/json",
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {token}",
        "X-Org":         settings.DEPLOY_AI_ORG_ID,
    }


# ── Retry helper ──────────────────────────────────────────────────────────────

_MAX_RETRIES  = 3
_RETRY_DELAYS = [1.0, 2.0, 4.0]   # seconds — exponential backoff

_TRANSIENT_EXCEPTIONS = (
    httpx.NetworkError,
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
)


async def _request_with_retry(
    method: str,
    url: str,
    *,
    op_name: str,
    timeout: float = 30.0,
    **kwargs,
) -> httpx.Response:
    """
    Execute an HTTP request with exponential-backoff retry on transient failures.
    Raises DeployAIError after all retries are exhausted.
    API-level errors (non-200 status) are NOT retried — caller handles them.
    """
    last_exc: Optional[Exception] = None

    for attempt in range(_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await getattr(client, method)(url, **kwargs)
            return response
        except _TRANSIENT_EXCEPTIONS as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES - 1:
                delay = _RETRY_DELAYS[attempt]
                logger.warning(
                    "[DeployAI] %s — transient error on attempt %d/%d, retrying in %.1fs: %s",
                    op_name, attempt + 1, _MAX_RETRIES, delay, exc,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "[DeployAI] %s — all %d attempts exhausted: %s",
                    op_name, _MAX_RETRIES, exc,
                )

    raise DeployAIError(
        op_name, 0,
        f"Network failure after {_MAX_RETRIES} attempts: {last_exc}",
    )


# ── Auth ──────────────────────────────────────────────────────────────────────

async def get_access_token() -> str:
    if _is_token_valid():
        return _token_cache["token"]

    logger.info("[DeployAI] Fetching new access token…")
    payload = {
        "grant_type":    "client_credentials",
        "client_id":     settings.DEPLOY_AI_CLIENT_ID,
        "client_secret": settings.DEPLOY_AI_CLIENT_SECRET.get_secret_value(),
    }
    response = await _request_with_retry(
        "post",
        settings.DEPLOY_AI_AUTH_URL,
        op_name="get_access_token",
        timeout=15.0,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if response.status_code != 200:
        raise DeployAIError("get_access_token", response.status_code, response.text)

    data = response.json()
    token: str  = data["access_token"]
    expires_in: int = data.get("expires_in", 3600)
    _token_cache["token"]      = token
    _token_cache["expires_at"] = time.time() + expires_in
    logger.info("[DeployAI] Token acquired — expires in %ds", expires_in)
    return token


# ── Chat & message ────────────────────────────────────────────────────────────

async def create_chat(agent_id: str) -> str:
    token    = await get_access_token()
    response = await _request_with_retry(
        "post",
        f"{settings.DEPLOY_AI_API_URL}/chats",
        op_name="create_chat",
        timeout=30.0,
        headers=_auth_headers(token),
        json={"agentId": agent_id, "stream": False},
    )
    if response.status_code != 200:
        raise DeployAIError("create_chat", response.status_code, response.text)
    return response.json()["id"]


async def send_message(chat_id: str, content: str, *, timeout: float = 120.0) -> str:
    token = await get_access_token()
    body  = {
        "chatId":  chat_id,
        "stream":  False,
        "content": [{"type": "text", "value": content}],
    }
    response = await _request_with_retry(
        "post",
        f"{settings.DEPLOY_AI_API_URL}/messages",
        op_name="send_message",
        timeout=timeout,
        headers=_auth_headers(token),
        json=body,
    )
    if response.status_code != 200:
        raise DeployAIError("send_message", response.status_code, response.text)

    data = response.json()
    for block in data.get("content", []):
        if block.get("type") == "text":
            return block["value"]
    raise ValueError(
        f"No text content in response for chat '{chat_id}'. Response: {data}"
    )


async def call_agent(agent_id: str, prompt: str, *, timeout: float = 120.0) -> str:
    """Convenience one-shot wrapper: create chat → send message → return reply."""
    chat_id = await create_chat(agent_id)
    return await send_message(chat_id, prompt, timeout=timeout)
