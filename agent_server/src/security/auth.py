from langgraph_sdk import Auth
from security.jwt_verifier import verify_jwt

auth = Auth()


@auth.authenticate
async def get_current_user(authorization: str | None):
    if not authorization:
        raise Auth.exceptions.HTTPException(
            status_code=401,
            detail="Missing Authorization header"
        )

    parts = authorization.split()
    if len(parts) != 2:
        raise Auth.exceptions.HTTPException(
            status_code=401,
            detail="Invalid Authorization header format"
        )

    scheme, token = parts
    if scheme.lower() != "bearer":
        raise Auth.exceptions.HTTPException(
            status_code=401,
            detail="Invalid authentication scheme"
        )

    try:
        payload = await verify_jwt(token)
    except ValueError:
        raise Auth.exceptions.HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )
  
    return {
        "identity": payload["sub"],  #Keycloak user id
        "email": payload.get("email"),
        "username": payload.get("preferred_username"),
        "roles": payload.get("realm_access", {}).get("roles", []),
    }


@auth.on
async def add_owner(ctx, value):
    filters = {"owner": ctx.user.identity}
    metadata = value.setdefault("metadata", {})
    metadata.update(filters)
    return filters
