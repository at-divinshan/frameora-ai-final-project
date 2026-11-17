"""Verification transactions; no session or schema creation."""
from hashlib import sha256
from secrets import compare_digest
from types import SimpleNamespace
from sqlalchemy import select
from fastapi import HTTPException
from app.models.user import User
from app.core.account_state import require_active

class EmailVerificationRepository:
    def __init__(self, db): self.db = db

    def pending_by_email(self, email):
        try:
            user = self.db.scalar(select(User).where(User.email == email,
                User.email_verification_required.is_(True), User.is_verified.is_(False),
                User.role.in_(('user', 'owner'))).with_for_update())
            if user is None: return None
            try: require_active(self.db, user)
            except HTTPException as error:
                if error.status_code == 401: return None
                raise
            return SimpleNamespace(id=user.id, email=user.email, auth_version=user.auth_version,
                                   is_verified=False, email_verification_required=True)
        finally:
            self.db.rollback()  # Release read locks before SMTP.

    def verify_pending(self, *, user_id, email_digest, auth_version):
        try:
            if type(user_id) is not int or type(auth_version) is not int or not isinstance(email_digest, str):
                return False
            user = self.db.get(User, user_id, populate_existing=True, with_for_update=True)
            if (user is None or user.role not in ('user','owner') or not user.email_verification_required
                    or user.is_verified or user.auth_version != auth_version
                    or not compare_digest(sha256(user.email.strip().lower().encode()).hexdigest(), email_digest)):
                return False
            try: require_active(self.db, user)
            except HTTPException as error:
                if error.status_code == 401: return False
                raise
            user.is_verified = True
            user.email_verification_required = False
            self.db.commit()
            return True
        finally:
            self.db.rollback()
