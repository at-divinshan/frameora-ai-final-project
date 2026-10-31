"""Read-only Admin queries. Never commit, activate a plan or create profiles."""
from fastapi import HTTPException
from sqlalchemy import func, or_, select
from app.models.user import User
from app.models.profile import UserProfile
from app.repositories.profile_repository import STUDIO_FIELDS
from app.schemas.admin import OwnerRecord, OwnerDetail
from app.schemas.owner import StudioDetails
from app.services import subscription_service, studio_photo_service


def summary(db):
    counts = dict(db.execute(select(User.role, func.count()).group_by(User.role)).all())
    return {'normal_users': counts.get('user', 0), 'studio_owners': counts.get('owner', 0)}


def record(user, profile):
    return OwnerRecord(id=user.id, name=user.name, email=user.email, created_at=user.created_at,
        onboarding_status=profile.onboarding_status if profile else 'pending_studio',
        studio=StudioDetails(**{key: getattr(profile, key) for key in STUDIO_FIELDS}) if profile else None)


def owners(db, filters):
    conditions = [User.role == 'owner']
    if filters.q.strip():
        conditions.append(or_(*(column.contains(filters.q.strip(), autoescape=True) for column in
            (User.name, User.email, UserProfile.studio_name, UserProfile.studio_city))))
    if filters.onboarding:
        conditions.append(func.coalesce(UserProfile.onboarding_status, 'pending_studio') == filters.onboarding)
    total = db.scalar(select(func.count()).select_from(User).outerjoin(UserProfile, UserProfile.user_id == User.id).where(*conditions))
    # Select only necessary account columns, never hashes, identity subjects or private settings.
    rows = db.execute(select(User.id, User.name, User.email, User.created_at, UserProfile)
        .outerjoin(UserProfile, UserProfile.user_id == User.id).where(*conditions)
        .order_by(User.created_at.desc(), User.id.desc()).offset((filters.page - 1) * filters.page_size).limit(filters.page_size)).all()
    return {'items': [record(row, row.UserProfile) for row in rows], 'total': total,
            'page': filters.page, 'page_size': filters.page_size}


def owner(db, owner_id):
    user = db.scalar(select(User).where(User.id == owner_id, User.role == 'owner'))
    if user is None:
        raise HTTPException(404, 'Studio Owner not found.')
    return user


def detail(db, owner_id):
    user = owner(db, owner_id)
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == owner_id))
    data = record(user, profile).model_dump()
    photo = studio_photo_service.status(db, user)
    data.update(photo_available=photo['available'], has_photo=photo['has_photo'])
    try:
        # Existing shared entitlement calculation: action=None never grants/writes.
        entitlement = subscription_service.snapshot(db, user)
        data.update(subscription_status='active' if entitlement['plan'] else 'not_selected', subscription=entitlement)
    except HTTPException as error:
        if error.status_code != 503:
            raise
        data.update(subscription_status='unavailable', subscription=None)
    return OwnerDetail(**data)
