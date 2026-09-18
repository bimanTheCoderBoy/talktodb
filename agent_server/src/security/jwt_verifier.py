"""
JWT Verification module for Keycloak tokens.
"""
import asyncio
import httpx
from jose import jwt
from jose.exceptions import JWTError
from dotenv import load_dotenv
import os
import logging

load_dotenv()

logger = logging.getLogger(__name__)

# Simple cache for JWKS
_jwks_cache = None
_config_validated = False

# Configuration (env-var driven)
KEYCLOAK_JWKS_TIMEOUT = float(os.getenv("KEYCLOAK_JWKS_TIMEOUT", "10.0"))
KEYCLOAK_JWKS_MAX_RETRIES = int(os.getenv("KEYCLOAK_JWKS_MAX_RETRIES", "5"))


def _get_config():
    """Get Keycloak configuration from environment variables."""
    keycloak_realm = os.getenv("KEYCLOAK_REALM")
    keycloak_base_url = os.getenv("KEYCLOAK_BASE_URL")
    audience = os.getenv("AUDIENCE")
    
    if not keycloak_realm:
        raise ValueError("KEYCLOAK_REALM is not set")
    if not keycloak_base_url:
        raise ValueError("KEYCLOAK_BASE_URL is not set")
    if not audience:
        raise ValueError("AUDIENCE is not set")
    
    issuer = f"{keycloak_base_url}/realms/{keycloak_realm}"
    jwks_url = f"{issuer}/protocol/openid-connect/certs"
    
    return {
        "issuer": issuer,
        "jwks_url": jwks_url,
        "audience": audience,
    }


async def get_jwks(jwks_url: str):
    """Fetch JWKS from Keycloak (with caching and retry)."""
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    
    ssl_verify = os.getenv("KEYCLOAK_SSL_VERIFY", "false").lower() != "false"
    last_exception = None

    for attempt in range(1, KEYCLOAK_JWKS_MAX_RETRIES + 2):
        try:
            async with httpx.AsyncClient(timeout=KEYCLOAK_JWKS_TIMEOUT, verify=ssl_verify) as client:
                response = await client.get(jwks_url)
            response.raise_for_status()
            _jwks_cache = response.json()
            return _jwks_cache
        except httpx.HTTPError as e:
            last_exception = e
            if attempt <= KEYCLOAK_JWKS_MAX_RETRIES:
                logger.warning(
                    "JWKS fetch failed (attempt %d/%d): %s, retrying...",
                    attempt, KEYCLOAK_JWKS_MAX_RETRIES + 1, e,
                )
                await asyncio.sleep(min(2 ** attempt, 10))
                continue
            logger.error(f"Failed to fetch JWKS after {KEYCLOAK_JWKS_MAX_RETRIES + 1} attempts: {e}")
            raise ValueError(f"Failed to fetch JWKS from Keycloak: {e}")


async def verify_jwt(token: str) -> dict:
    """
    Verify a JWT token against Keycloak.
    
    Args:
        token: The JWT token string (without 'Bearer ' prefix)
        
    Returns:
        The decoded token payload
        
    Raises:
        ValueError: If token is invalid or expired
    """
    try:
        # Get config (validates env vars)
        config = _get_config()
        
        # Get unverified header to find the key ID
        unverified_header = jwt.get_unverified_header(token)
        
        # Fetch JWKS
        jwks = await get_jwks(config["jwks_url"])
        
        # Find the matching key
        key = None
        for k in jwks.get("keys", []):
            if k.get("kid") == unverified_header.get("kid"):
                key = k
                break
        
        if key is None:
            raise ValueError("Token key not found in JWKS")
        
        # Verify and decode the token
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=config["audience"],
            issuer=config["issuer"],
        )
        
        return payload

    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise ValueError(f"Invalid or expired token: {e}")
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during JWT validation: {e}")
        raise ValueError(f"Token validation error: {e}")
