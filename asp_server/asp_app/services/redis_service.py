from redis import Redis
import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator

logger = logging.getLogger(__name__)

# Heartbeat interval in seconds — keeps SSE alive during long-running operations
SSE_HEARTBEAT_INTERVAL = 15


class RedisService:
    @staticmethod
    async def stream_logs(redis_client: Redis, acss_session_id: str) -> AsyncGenerator[str, None]:
        """Stream log messages for a session with periodic heartbeats.
        
        Sends an SSE comment (: keepalive) every SSE_HEARTBEAT_INTERVAL seconds
        when no real messages arrive. This prevents proxies/browsers from closing
        the connection during long-running operations.
        """
        key = f"logs:{acss_session_id}"
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(key)
        try:
            last_activity = time.monotonic()
            while True:
                # get_message returns None if no message is available (non-blocking with timeout)
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    last_activity = time.monotonic()
                    yield f"data: {message['data']}\n\n"
                else:
                    # Send heartbeat if idle for too long
                    if time.monotonic() - last_activity >= SSE_HEARTBEAT_INTERVAL:
                        last_activity = time.monotonic()
                        yield f": keepalive\n\n"
                    # Brief sleep to avoid busy-loop
                    await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(key)
            await pubsub.close()

    @staticmethod
    async def stream_execution_state(redis_client: Redis, job_id: str) -> AsyncGenerator[str, None]:
        """Stream execution state updates for a job with periodic heartbeats.
        
        On connect, emits the latest snapshot stored in Redis so late-joining
        clients immediately see current progress (Redis Pub/Sub has no replay).
        Then subscribes for live updates.
        
        Sends an SSE comment (: keepalive) every SSE_HEARTBEAT_INTERVAL seconds
        when no real messages arrive. This prevents proxies/browsers from closing
        the connection during long-running operations.
        """
        snapshot_key = f"execution_state_snapshot:{job_id}"
        pubsub_key = f"execution_state:{job_id}"

        snapshot = await redis_client.get(snapshot_key)
        if snapshot:
            yield f"data: {snapshot}\n\n"

        pubsub = redis_client.pubsub()
        await pubsub.subscribe(pubsub_key)
        try:
            last_activity = time.monotonic()
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    last_activity = time.monotonic()
                    yield f"data: {message['data']}\n\n"
                else:
                    if time.monotonic() - last_activity >= SSE_HEARTBEAT_INTERVAL:
                        last_activity = time.monotonic()
                        yield f": keepalive\n\n"
                    await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(pubsub_key)
            await pubsub.close()

    @staticmethod
    async def publish_log(redis_client: Redis, channel: str, message: Any) -> None:
        """Publish a log message to Redis. Ensures message is always a string (stringifies with json.dumps if not)."""
        if not isinstance(message, str):
            message = json.dumps(message)
        await redis_client.publish(channel, message)

    @staticmethod
    async def publish_execution_state(redis_client: Redis, job_id: str, state: dict):
        """Publish execution state to Redis and persist a snapshot for late joiners."""
        payload = json.dumps(state)
        pubsub_key = f"execution_state:{job_id}"
        snapshot_key = f"execution_state_snapshot:{job_id}"
        await redis_client.set(snapshot_key, payload, ex=86400)
        await redis_client.publish(pubsub_key, payload)
