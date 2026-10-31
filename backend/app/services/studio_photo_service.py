"""Private owner-only studio photos; column presence gates migration 004."""
from fastapi import HTTPException
from sqlalchemy import inspect
from app.repositories.user_repository import lock_profile
from app.repositories.profile_repository import find_owner_profile
from app.services.onboarding_service import require_owner
from app.services import profile_image_storage as storage
from app.services.profile_image_service import cleanup


def available(db):
    return any(c['name'] == 'studio_photo' and c['nullable'] and getattr(c['type'], 'length', None) == 68
               for c in inspect(db.connection()).get_columns('UserProfile'))


def status(db, user):
    require_owner(user)
    if not available(db):
        return {'available': False, 'has_photo': False}
    profile = find_owner_profile(db, user.id)
    return {'available': True, 'has_photo': bool(profile and storage.valid_key(profile.studio_photo))}


def locked_profile(db, user):
    if not available(db):
        raise HTTPException(503, 'Studio photos are unavailable until the separate photo migration is approved and applied.')
    require_owner(lock_profile(db, user.id))
    profile = find_owner_profile(db, user.id, lock=True)
    if not profile:
        raise HTTPException(409, 'Save studio details before uploading a photo.')
    return profile


def change(db, user, data):
    key = None
    commit_started = False
    try:
        # Check schema before decoding or writing; no file or row on unavailable schema.
        if not available(db):
            raise HTTPException(503, 'Studio photos are unavailable until the separate photo migration is approved and applied.')
        try:
            normalized = storage.normalize_image(data, formats=('JPEG', 'PNG', 'WEBP')) if data is not None else None
        except HTTPException as error:
            if error.status_code == 422:
                raise HTTPException(422, 'Use a valid non-animated JPEG, PNG or WebP image, at most 16 megapixels.') from None
            raise
        profile = locked_profile(db, user)
        previous = profile.studio_photo
        if normalized is not None:
            key = storage.write_image(normalized)
        profile.studio_photo = key
        db.flush()
        commit_started = True
        db.commit()
    except Exception as error:
        db.rollback()
        if key and not commit_started:
            cleanup(key)
        if isinstance(error, OSError):
            raise HTTPException(503, 'Studio photo storage is unavailable.') from None
        raise
    cleanup(previous)
    return {'available': True, 'has_photo': bool(key)}


def read(db, user):
    profile = locked_profile(db, user)
    try:
        return storage.read_image(profile.studio_photo)
    except OSError:
        raise HTTPException(404, 'Studio photo not found.') from None
