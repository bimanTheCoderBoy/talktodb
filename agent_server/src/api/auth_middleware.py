import logging
from typing import Optional
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from api.jwt_verifier import verify_jwt

logger = logging.getLogger(__name__)


class AuthMiddleware:
    """
    Middleware to authenticate requests via JWT.
    
    - Validates JWT from Authorization header
    - Attaches user to request.state.user
    - Returns 401 for invalid tokens on protected paths
    - Skips public paths like /health, /docs
    """
    
    # Paths that don't require authentication
    PUBLIC_PATHS = {
        "/health",
        "/ok",
        "/docs",
        "/redoc",
        "/openapi.json",
    }
    
    def __init__(self, app: ASGIApp):
        """Initialize the middleware."""
        self.app = app
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        """Process incoming requests and validate authentication."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope["path"]
        headers = dict(scope["headers"])
        method = scope["method"]
        
        # Skip public paths
        if self._is_public_path(path):
            await self.app(scope, receive, send)
            return
        # Get and validate JWT
        authorization = headers.get(b"authorization", b"").decode("latin-1")
        user = await self._validate_and_get_user(authorization)
        
        if not user:
            logger.warning(f"🚫 Auth failed for {method} {path}")
            response = JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized - Invalid or missing token"}
            )
            await response(scope, receive, send)
            return
        
        # Attach user to request state
        # Store in scope so it persists through the middleware chain
        scope["state"] = scope.get("state", {})
        scope["state"]["user"] = user
        
        logger.info(f"✅ Auth success: {user.get('username')} for {method} {path}")
        
        await self.app(scope, receive, send)
    
    def _is_public_path(self, path: str) -> bool:
        """Check if path is public (no auth required)."""
        if path in self.PUBLIC_PATHS:
            return True
        if path.startswith("/docs") or path.startswith("/redoc"):
            return True
        return False
    
    async def _validate_and_get_user(self, authorization: str | None) -> Optional[dict]:
        """Validate JWT and return user info, or None if invalid."""
        if not authorization:
            return None
        
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        
        try:
            payload = await verify_jwt(parts[1])
            return {
                "identity": payload["sub"],
                "email": payload.get("email"),
                "username": payload.get("preferred_username"),
                "roles": payload.get("realm_access", {}).get("roles", []),
            }
        except Exception as e:
            logger.warning(f"JWT validation failed: {e}")
            return None

