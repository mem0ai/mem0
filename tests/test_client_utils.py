import inspect

import httpx
import pytest

from mem0.client.utils import api_error_handler
from mem0.exceptions import AuthenticationError, NetworkError, RateLimitError


def test_sync_returns_value():
    @api_error_handler
    def sync_fn():
        return {"result": "ok"}

    assert sync_fn() == {"result": "ok"}


@pytest.mark.asyncio
async def test_async_returns_value():
    @api_error_handler
    async def async_fn():
        return {"result": "ok"}

    assert await async_fn() == {"result": "ok"}


def test_async_decorated_preserves_coroutine_flag():
    @api_error_handler
    async def async_fn():
        return True

    assert inspect.iscoroutinefunction(async_fn)


def test_sync_decorated_is_not_coroutine():
    @api_error_handler
    def sync_fn():
        return True

    assert not inspect.iscoroutinefunction(sync_fn)


def test_sync_http_error_raises_structured_exception():
    @api_error_handler
    def sync_fn():
        request = httpx.Request("GET", "https://api.mem0.ai/v1/memories")
        response = httpx.Response(401, request=request, text="Unauthorized")
        raise httpx.HTTPStatusError("401", request=request, response=response)

    with pytest.raises(AuthenticationError):
        sync_fn()


@pytest.mark.asyncio
async def test_async_http_error_raises_structured_exception():
    @api_error_handler
    async def async_fn():
        request = httpx.Request("GET", "https://api.mem0.ai/v1/memories")
        response = httpx.Response(429, request=request, text="Rate limited")
        raise httpx.HTTPStatusError("429", request=request, response=response)

    with pytest.raises(RateLimitError):
        await async_fn()


@pytest.mark.asyncio
async def test_async_connect_error_raises_network_error():
    @api_error_handler
    async def async_fn():
        request = httpx.Request("GET", "https://api.mem0.ai/v1/memories")
        raise httpx.ConnectError("Connection refused", request=request)

    with pytest.raises(NetworkError) as exc_info:
        await async_fn()
    assert exc_info.value.error_code == "NET_CONNECT"
