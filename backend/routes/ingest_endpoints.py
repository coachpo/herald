from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.jwt import get_current_user_id
from ..database import get_session
from ..models import (
    IngestEndpoint,
    IngestEndpointCreateRequest,
    IngestEndpointCreateResponse,
    IngestEndpointResponse,
    IngestEndpointUpdateRequest,
    IngestEndpointsResponse,
)
from ..services.exceptions import NotFoundError, TemporarilyUnavailableError
from ..services.ingest_endpoints import (
    create_ingest_endpoint as create_ingest_endpoint_service,
    delete_ingest_endpoint as delete_ingest_endpoint_service,
    get_ingest_endpoint_detail as get_ingest_endpoint_detail_service,
    list_ingest_endpoints as list_ingest_endpoints_service,
    revoke_ingest_endpoint as revoke_ingest_endpoint_service,
    update_ingest_endpoint as update_ingest_endpoint_service,
)

router = APIRouter()


@router.get("/ingest-endpoints", response_model=IngestEndpointsResponse)
async def list_ingest_endpoints(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """List all ingest endpoints."""
    endpoints = await list_ingest_endpoints_service(
        session=session,
        user_id=UUID(user_id),
    )
    return IngestEndpointsResponse(endpoints=endpoints)


@router.post(
    "/ingest-endpoints",
    response_model=IngestEndpointCreateResponse,
    status_code=201,
)
async def create_ingest_endpoint_route(
    req: IngestEndpointCreateRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    try:
        endpoint_dict, plain_token, ingest_url = await create_ingest_endpoint_service(
            session=session,
            user_id=UUID(user_id),
            name=req.name,
            base_url=str(request.base_url),
        )
    except TemporarilyUnavailableError:
        from . import _temporarily_unavailable_error

        raise _temporarily_unavailable_error()

    return IngestEndpointCreateResponse(
        endpoint=IngestEndpoint(**endpoint_dict),
        ingest_key=plain_token,
        ingest_url=ingest_url,
    )


@router.get("/ingest-endpoints/{endpoint_id}", response_model=IngestEndpointResponse)
async def get_ingest_endpoint_detail(
    endpoint_id: UUID,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Get single ingest endpoint."""
    try:
        endpoint = await get_ingest_endpoint_detail_service(
            session,
            user_id=UUID(user_id),
            id=endpoint_id,
        )
        return IngestEndpointResponse(endpoint=endpoint)
    except NotFoundError:
        from . import _not_found_error

        raise _not_found_error()


@router.patch("/ingest-endpoints/{endpoint_id}", response_model=IngestEndpointResponse)
async def update_ingest_endpoint_route(
    endpoint_id: UUID,
    req: IngestEndpointUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    try:
        endpoint_dict = await update_ingest_endpoint_service(
            session=session,
            user_id=UUID(user_id),
            id=endpoint_id,
            name=req.name,
        )
    except NotFoundError:
        from . import _not_found_error

        raise _not_found_error()
    except TemporarilyUnavailableError:
        from . import _temporarily_unavailable_error

        raise _temporarily_unavailable_error()

    return IngestEndpointResponse(endpoint=IngestEndpoint(**endpoint_dict))


@router.delete("/ingest-endpoints/{endpoint_id}", status_code=204)
async def delete_ingest_endpoint_route(
    endpoint_id: UUID,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    try:
        await delete_ingest_endpoint_service(
            session=session,
            user_id=UUID(user_id),
            id=endpoint_id,
        )
    except NotFoundError:
        from . import _not_found_error

        raise _not_found_error()
    except TemporarilyUnavailableError:
        from . import _temporarily_unavailable_error

        raise _temporarily_unavailable_error()

    return Response(status_code=204)


@router.post("/ingest-endpoints/{endpoint_id}/revoke", status_code=204)
async def revoke_ingest_endpoint_route(
    endpoint_id: UUID,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    try:
        await revoke_ingest_endpoint_service(
            session=session,
            user_id=UUID(user_id),
            id=endpoint_id,
        )
    except NotFoundError:
        from . import _not_found_error

        raise _not_found_error()
    except TemporarilyUnavailableError:
        from . import _temporarily_unavailable_error

        raise _temporarily_unavailable_error()

    return Response(status_code=204)
