"""Separate high-entropy bearer credentials; compare digests and never echo inputs."""
import hashlib
import hmac

from fastapi import HTTPException, Request


def require_token(request: Request, expected: str) -> None:
    scheme, _, token = request.headers.get('authorization', '').partition(' ')
    valid = scheme.lower() == 'bearer' and hmac.compare_digest(
        hashlib.sha256(token.encode()).digest(), hashlib.sha256(expected.encode()).digest()
    )
    if not valid:
        raise HTTPException(401, 'invalid_token', headers={'WWW-Authenticate': 'Bearer'})


def require_admin(request: Request) -> None:
    require_token(request, request.app.state.settings.admin_token)


def require_ingest(request: Request) -> None:
    require_token(request, request.app.state.settings.ingest_token)
