"""
Simple async HTTP client with connection reuse and retry logic.
"""

import asyncio
import logging
import os
from typing import Dict, Any, Optional

import httpx

logger = logging.getLogger(__name__)

# Global client instance
_client: Optional[httpx.AsyncClient] = None

# Configuration (env-var driven)
MAX_RETRIES = int(os.getenv("COVERAGE_API_MAX_RETRIES", "3"))
RETRY_DELAY = float(os.getenv("COVERAGE_API_RETRY_DELAY", "1.0"))
TIMEOUT = float(os.getenv("COVERAGE_API_TIMEOUT", "30.0"))


class RetryableHTTPError(Exception):
    """Raised when all retry attempts failed."""
    def __init__(self, message: str, last_error: Exception, attempts: int):
        super().__init__(message)
        self.last_error = last_error
        self.attempts = attempts


async def get_client() -> httpx.AsyncClient:
    """Get or create the global HTTP client."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=TIMEOUT)
    return _client


async def close_client() -> None:
    """Close the global client (call on app shutdown)."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None


def _should_retry(error: Exception) -> bool:
    """Check if error is retryable."""
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code >= 500 or error.response.status_code in (408, 429)
    return isinstance(error, (httpx.ConnectError, httpx.TimeoutException))


async def _request_with_retry(method: str, url: str, **kwargs) -> httpx.Response:
    """Execute HTTP request with retry logic."""
    client = await get_client()
    last_error = None
    
    for attempt in range(MAX_RETRIES):
        try:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except Exception as e:
            last_error = e
            if not _should_retry(e) or attempt == MAX_RETRIES - 1:
                if attempt > 0:
                    logger.error(f"Request failed after {attempt + 1} attempts: {url}")
                raise
            logger.warning(f"Retry {attempt + 1}/{MAX_RETRIES} for {url}: {e}")
            await asyncio.sleep(RETRY_DELAY * (attempt + 1))
    
    raise RetryableHTTPError(f"Failed after {MAX_RETRIES} attempts", last_error, MAX_RETRIES)


async def get(url: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> httpx.Response:
    """Send GET request with retry."""
    return await _request_with_retry("GET", url, headers=headers, **kwargs)


async def post(url: str, headers: Optional[Dict[str, str]] = None, json: Optional[Dict[str, Any]] = None, **kwargs) -> httpx.Response:
    """Send POST request with retry."""
    return await _request_with_retry("POST", url, headers=headers, json=json, **kwargs)


async def put(url: str, headers: Optional[Dict[str, str]] = None, json: Optional[Dict[str, Any]] = None, **kwargs) -> httpx.Response:
    """Send PUT request with retry."""
    return await _request_with_retry("PUT", url, headers=headers, json=json, **kwargs)
