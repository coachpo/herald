from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.jwt import get_current_user_id
from ..database import get_session
from ..models import (
    Channel,
    ChannelCreateRequest,
    ChannelTestRequest,
    ChannelTestResponse,
    ChannelWithConfigResponse,
    ChannelsResponse,
)
from ..services.channel_operations import (
    create_channel as create_channel_service,
    delete_channel as delete_channel_service,
    list_channels as list_channels_service,
    test_channel as test_channel_service,
)
from ..services.exceptions import (
    ChannelConfigValidationError,
    NotFoundError,
    TemporarilyUnavailableError,
)

router = APIRouter()


@router.get("/channels", response_model=ChannelsResponse)
async def list_channels(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """List all channels."""
    channels = await list_channels_service(
        session=session,
        user_id=UUID(user_id),
    )
    return ChannelsResponse(channels=channels)


@router.post("/channels", response_model=ChannelWithConfigResponse, status_code=201)
async def create_channel_route(
    req: ChannelCreateRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    try:
        channel_dict = await create_channel_service(
            session=session,
            user_id=UUID(user_id),
            type=req.type,
            name=req.name,
            config=req.config,
        )
    except ChannelConfigValidationError as exc:
        from . import _validation_error

        raise _validation_error(exc.details)
    except TemporarilyUnavailableError:
        from . import _temporarily_unavailable_error

        raise _temporarily_unavailable_error()

    config = channel_dict.pop("config")
    return ChannelWithConfigResponse(channel=Channel(**channel_dict), config=config)


@router.delete("/channels/{channel_id}", status_code=204)
async def delete_channel_route(
    channel_id: UUID,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    try:
        await delete_channel_service(
            session=session,
            user_id=UUID(user_id),
            id=channel_id,
        )
    except NotFoundError:
        from . import _not_found_error

        raise _not_found_error()
    except TemporarilyUnavailableError:
        from . import _temporarily_unavailable_error

        raise _temporarily_unavailable_error()

    return Response(status_code=204)


@router.post("/channels/{channel_id}/test", response_model=ChannelTestResponse)
async def test_channel_route(
    channel_id: UUID,
    req: ChannelTestRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    title = str(req.title or "").strip() or None
    body = str(req.body or "").strip() or None
    payload_json = req.payload_json
    if not body and payload_json is None:
        body = "Test notification from Herald"

    try:
        result = await test_channel_service(
            session=session,
            user_id=UUID(user_id),
            channel_id=channel_id,
            title=title,
            body=body,
            payload_json=payload_json,
        )
    except NotFoundError:
        from . import _not_found_error

        raise _not_found_error()
    except ValueError as exc:
        from . import _validation_error

        raise _validation_error(
            {"error": str(exc)},
            message="invalid channel config",
        )
    except Exception as exc:
        from . import _channel_test_failed_error

        raise _channel_test_failed_error(str(exc))

    return ChannelTestResponse(**result)
