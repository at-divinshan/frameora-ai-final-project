"""Owner-only AI operations and saved photography inputs, separate from free previews."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.user import User
from app.routers.owner import owner_identity, owner_request
from app.schemas.owner_ai import OwnerEntitlements, OwnerGenerationPreferences, OwnerGenerationResponse
from app.schemas.photography_plan import PhotographyPlanCreate, PhotographyPlanPatch, PhotographyPlanRead
from app.services import owner_entitlement_service as entitlements, owner_generation_service as generations
from app.services import ai_image_storage, plan_service

router = APIRouter(prefix='/owner', tags=['Owner AI credits'], dependencies=[Depends(owner_request)])


@router.get('/entitlements', response_model=OwnerEntitlements)
@router.get('/ai/eligibility', response_model=OwnerEntitlements)
def eligibility(user: User = Depends(owner_identity), db: Session = Depends(get_db)):
    return entitlements.read(db, user)


async def exact_generation_fields(request: Request):
    form = await request.form()
    allowed = {
        'plan_id', 'description', 'reference', 'idempotency_key',
        'reference_photo',
        'background_mode', 'pose_mode', 'camera_angle_mode', 'outfit_mode',
        'dress_colors', 'outfit_details', 'additional_instructions',
    }
    if set(form) - allowed or any(len(form.getlist(key)) != 1 for key in form):
        raise HTTPException(422, 'Generation fields must be accepted once each and use the supported owner fields.')


def owner_generation_preferences(
    background_mode: str = Form('same'),
    pose_mode: str = Form('natural'),
    camera_angle_mode: str = Form('mixed'),
    outfit_mode: str = Form('same'),
    dress_colors: str = Form('', max_length=200),
    outfit_details: str = Form('', max_length=1000),
    additional_instructions: str = Form('', max_length=2000),
) -> OwnerGenerationPreferences:
    try:
        return OwnerGenerationPreferences(
            background_mode=background_mode,
            pose_mode=pose_mode,
            camera_angle_mode=camera_angle_mode,
            outfit_mode=outfit_mode,
            dress_colors=dress_colors.strip(),
            outfit_details=outfit_details.strip(),
            additional_instructions=additional_instructions.strip(),
        )
    except ValidationError as error:
        messages = '; '.join(item['msg'] for item in error.errors(include_input=False))
        raise HTTPException(422, detail=f'Invalid owner generation preferences: {messages}') from None


def _normalize_reference(reference):
    if reference is None:
        return None
    try:
        if reference.content_type not in ('image/jpeg', 'image/png', 'image/webp'):
            raise HTTPException(422, 'Upload a JPEG, PNG or WebP reference image.')
        data = reference.file.read(ai_image_storage.MAX_UPLOAD + 1)
        if len(data) > ai_image_storage.MAX_UPLOAD:
            raise HTTPException(413, 'Reference images must not exceed 5 MiB.')
        return ai_image_storage.normalize_image(data)
    finally:
        reference.file.close()


def _normalize_reference_fields(reference, reference_photo):
    if reference is not None and reference_photo is not None:
        raise HTTPException(422, 'Upload only one reference image.')
    return _normalize_reference(reference if reference is not None else reference_photo)


@router.post('/ai/generations', response_model=OwnerGenerationResponse,
             dependencies=[Depends(exact_generation_fields)])
def generate(response: Response, plan_id: int = Form(..., gt=0),
             idempotency_key: str = Form(..., min_length=16, max_length=128, pattern=r'^[A-Za-z0-9_-]+$'),
             description: str = Form('', max_length=2000), reference: UploadFile | None = File(None),
             reference_photo: UploadFile | None = File(None),
             preferences: OwnerGenerationPreferences = Depends(owner_generation_preferences),
             user: User = Depends(owner_identity), db: Session = Depends(get_db)):
    normalized = _normalize_reference_fields(reference, reference_photo)
    result = generations.generate(db, user, plan_id=plan_id, description=description.strip(),
                                  reference=normalized, idempotency_key=idempotency_key,
                                  preferences=preferences.model_dump())
    response.status_code = 200 if result['replayed'] else 201
    return result


@router.post('/projects/{project_id}/ai/generations', response_model=OwnerGenerationResponse,
             dependencies=[Depends(exact_generation_fields)])
def generate_for_project(project_id: int, response: Response, plan_id: int = Form(..., gt=0),
                         idempotency_key: str = Form(..., min_length=16, max_length=128, pattern=r'^[A-Za-z0-9_-]+$'),
                         description: str = Form('', max_length=2000), reference: UploadFile | None = File(None),
                         reference_photo: UploadFile | None = File(None),
                         preferences: OwnerGenerationPreferences = Depends(owner_generation_preferences),
                         user: User = Depends(owner_identity), db: Session = Depends(get_db)):
    normalized = _normalize_reference_fields(reference, reference_photo)
    result = generations.generate(db, user, plan_id=plan_id, description=description.strip(),
                                  reference=normalized, idempotency_key=idempotency_key,
                                  project_id=project_id, preferences=preferences.model_dump())
    response.status_code = 200 if result['replayed'] else 201
    return result


@router.get('/ai/generations', response_model=list[OwnerGenerationResponse])
def gallery(user: User = Depends(owner_identity), db: Session = Depends(get_db)):
    return generations.list_results(db, user)


@router.get('/projects/{project_id}/ai/generations', response_model=list[OwnerGenerationResponse])
def project_gallery(project_id: int, user: User = Depends(owner_identity), db: Session = Depends(get_db)):
    return generations.list_project_results(db, user, project_id)


@router.get('/ai/generations/{generation_id}', response_model=OwnerGenerationResponse)
def result(generation_id: int, user: User = Depends(owner_identity), db: Session = Depends(get_db)):
    return generations.get_result(db, user, generation_id)


@router.post('/ai/generations/{generation_id}/recover', response_model=OwnerGenerationResponse)
def recover(generation_id: int, user: User = Depends(owner_identity), db: Session = Depends(get_db)):
    return generations.recover(db, user, generation_id)


@router.get('/ai/images/{asset_id}')
def image(asset_id: int, user: User = Depends(owner_identity), db: Session = Depends(get_db)):
    return Response(generations.get_image(db, user, asset_id), media_type='image/png', headers={
        'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
        'Content-Disposition': 'inline; filename="frameora.png"',
    })


# These are photography requirements only, not CustomerProject management.
@router.post('/photography-plans', response_model=PhotographyPlanRead, status_code=201)
def create_plan(data: PhotographyPlanCreate, user: User = Depends(owner_identity), db: Session = Depends(get_db)):
    return plan_service.create_plan(db, user, data)


@router.get('/photography-plans', response_model=list[PhotographyPlanRead])
def list_plans(user: User = Depends(owner_identity), db: Session = Depends(get_db)):
    return plan_service.list_owner_plans(db, user)


@router.get('/photography-plans/{plan_id}', response_model=PhotographyPlanRead)
def get_plan(plan_id: int, user: User = Depends(owner_identity), db: Session = Depends(get_db)):
    return plan_service.get_owner_plan(db, user, plan_id)


@router.patch('/photography-plans/{plan_id}', response_model=PhotographyPlanRead)
def edit_plan(plan_id: int, data: PhotographyPlanPatch, user: User = Depends(owner_identity), db: Session = Depends(get_db)):
    return plan_service.update_owner_plan(db, user, plan_id, data)
