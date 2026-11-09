"""HTTP authentication/parsing only; all receipt transactions belong to Store."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse

from .models import MessageInput, RoutingInput, TargetInput
from .tasks import database_call
from .security import require_admin, require_ingest

router = APIRouter(prefix='/api')


def require_json(request: Request) -> None:
    content_type = request.headers.get('content-type', '').split(';')[0].strip().lower()
    if content_type != 'application/json':
        raise HTTPException(415, 'application_json_required')


async def _receive(payload: MessageInput, request: Request) -> JSONResponse:
    result = await database_call(request.app.state.store.receive, payload.model_dump())
    return JSONResponse(result, status_code=200 if result['duplicate'] else 201)


@router.post('/ingest', dependencies=[Depends(require_ingest), Depends(require_json)])
async def ingest(payload: MessageInput, request: Request):
    return await _receive(payload, request)


@router.post('/messages', dependencies=[Depends(require_admin), Depends(require_json)])
async def send_message(payload: MessageInput, request: Request):
    return await _receive(payload, request)


@router.get('/session', dependencies=[Depends(require_admin)])
async def session():
    return {'authenticated': True}


@router.get('/settings', dependencies=[Depends(require_admin)])
async def settings(request: Request):
    s = request.app.state.settings
    return {'ingest_path': '/api/ingest', 'retention_days': s.retention_days,
            'max_attempts': s.max_attempts, 'delivery_timeout': s.delivery_timeout}


@router.get('/targets', dependencies=[Depends(require_admin)])
async def targets(request: Request):
    return {'targets': await database_call(request.app.state.store.list_targets)}


@router.get('/routing', response_model=RoutingInput, dependencies=[Depends(require_admin)])
async def routing(request: Request):
    return await database_call(request.app.state.store.get_routing)


@router.put('/routing', response_model=RoutingInput, dependencies=[Depends(require_admin), Depends(require_json)])
async def update_routing(payload: RoutingInput, request: Request):
    return await database_call(request.app.state.store.update_routing, payload.model_dump())


@router.post('/targets', status_code=201, dependencies=[Depends(require_admin), Depends(require_json)])
async def create_target(payload: TargetInput, request: Request):
    return await database_call(request.app.state.store.create_target, payload.model_dump())


@router.put('/targets/{target_id}', dependencies=[Depends(require_admin), Depends(require_json)])
async def update_target(target_id: str, payload: TargetInput, request: Request):
    return await database_call(request.app.state.store.update_target, target_id, payload.model_dump())


@router.delete('/targets/{target_id}', status_code=204, dependencies=[Depends(require_admin)])
async def delete_target(target_id: str, request: Request):
    await database_call(request.app.state.store.delete_target, target_id)
    return Response(status_code=204)


@router.get('/messages', dependencies=[Depends(require_admin)])
async def messages(request: Request, limit: int = Query(50, ge=1, le=100), before: str | None = None):
    return await database_call(request.app.state.store.list_messages, limit=limit, before=before)


@router.get('/messages/{message_id}', dependencies=[Depends(require_admin)])
async def message(message_id: str, request: Request):
    return await database_call(request.app.state.store.get_message, message_id)


@router.post('/deliveries/{delivery_id}/retry', dependencies=[Depends(require_admin)])
async def retry(delivery_id: str, request: Request):
    return await database_call(request.app.state.store.manual_retry, delivery_id)


@router.post('/cleanup', dependencies=[Depends(require_admin)])
async def cleanup(request: Request):
    deleted = await database_call(request.app.state.store.cleanup,
                                      retention_days=request.app.state.settings.retention_days)
    return {'deleted': deleted}
