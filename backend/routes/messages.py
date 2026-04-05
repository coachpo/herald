from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.jwt import get_current_user_id
from ..database import get_session
from ..models import (
    BatchDeleteMessagesRequest,
    BatchDeleteMessagesResponse,
    DeliveriesResponse,
    MessageResponse,
    MessagesResponse,
)
from ..services.exceptions import NotFoundError
from ..services.messages import (
    batch_delete_messages as batch_delete_messages_service,
    delete_message as delete_message_service,
    get_message_deliveries as get_message_deliveries_service,
    get_message_detail as get_message_detail_service,
    list_messages as list_messages_service,
)

router = APIRouter()


@router.get("/messages", response_model=MessagesResponse)
async def list_messages(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    ingest_endpoint_id: UUID | None = Query(None),
    priority_min: int | None = Query(None),
    priority_max: int | None = Query(None),
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
):
    """List messages with optional filters."""
    messages = await list_messages_service(
        session=session,
        user_id=UUID(user_id),
        ingest_endpoint_id=ingest_endpoint_id,
        priority_min=priority_min,
        priority_max=priority_max,
        from_=from_,
        to=to,
    )
    return MessagesResponse(messages=messages)


@router.get("/messages/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: UUID,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Get single message detail."""
    try:
        message = await get_message_detail_service(
            session=session,
            user_id=UUID(user_id),
            message_id=message_id,
        )
        return MessageResponse(message=message)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="message_not_found")


@router.delete("/messages/{message_id}", status_code=204)
async def delete_message_route(
    message_id: UUID,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    try:
        await delete_message_service(
            session=session,
            user_id=UUID(user_id),
            message_id=message_id,
        )
    except NotFoundError:
        from . import _not_found_error

        raise _not_found_error()


@router.post("/messages/batch-delete", response_model=BatchDeleteMessagesResponse)
async def batch_delete_messages_route(
    req: BatchDeleteMessagesRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    deleted_count = await batch_delete_messages_service(
        session=session,
        user_id=UUID(user_id),
        older_than_days=req.older_than_days,
        ingest_endpoint_id=req.ingest_endpoint_id,
    )
    return BatchDeleteMessagesResponse(deleted_count=deleted_count)


@router.get("/messages/{message_id}/deliveries", response_model=DeliveriesResponse)
async def get_message_deliveries(
    message_id: UUID,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Get deliveries for a message."""
    try:
        deliveries = await get_message_deliveries_service(
            session=session,
            user_id=UUID(user_id),
            message_id=message_id,
        )
        return DeliveriesResponse(deliveries=deliveries)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="message_not_found")
