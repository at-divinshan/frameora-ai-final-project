"""Google authentication orchestration; persistent changes occur only on explicit completion."""

import secrets
import time

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.google_oidc import authorization_url, digest, exchange_identity, new_secret, rejected
from app.core.security import require_jwt_configuration, verify_password
from app.core.security import auth_versions_enabled, require_password_management, hash_password
from app.core.auth_version import current_version, check_version
from app.repositories.user_repository import lock_profile
from app.services.password_service import locked_account, write_password
from app.models.user import User
from app.repositories.user_repository import (
    add_google_user, find_by_email, find_by_google_sub, link_google_identity,
)
from app.schemas.google_auth import GoogleRegistration
from app.services.auth_service import issue_session
from app.services.oauth_transaction_store import (
    AUTH_TTL, COMPLETION_TTL, REGISTRATION_TTL, get_store,
)


def public_account(user: User | None):
    if user is None or user.role not in ("user", "owner"):
        raise rejected()


def begin(browser: str, remember: bool, user: User | None = None,
          password: str | None = None, authorization: str = "") -> str:
    store = get_store()
    data = {"nonce": new_secret(), "verifier": new_secret(), "remember": remember, "action": "login",
            "versioned": auth_versions_enabled()}
    if user is not None:
        public_account(user)
        store.limit("link:" + str(user.id), 5, 300)
        valid = verify_password(password or "", user.password_hash)
        if not valid or not user.password_hash or user.google_sub is not None:
            raise HTTPException(401, "Unable to authenticate or link this account.")
        data.update({
            "action": "link", "user_id": user.id, "password_digest": digest(user.password_hash),
            "session_digest": digest(authorization), "reauthenticated_at": time.time(),
            "auth_version": getattr(user, "_authenticated_version", None),
        })
    state = store.put("authorization", browser, data, AUTH_TTL)
    return authorization_url(state, data["nonce"], data["verifier"])


def callback(db: Session, state: str, code: str | None, error: str | None, browser: str) -> tuple[str, str]:
    store = get_store()
    try:
        data = store.consume(state, browser, "authorization")
    except HTTPException as consume_error:
        if consume_error.status_code != 400 or not auth_versions_enabled():
            raise
        require_password_management()
        data = store.consume(state, browser, "password-setup-authorization")
    if auth_versions_enabled() and data.get("versioned") is not True:
        raise rejected()
    if error or not code or len(code) > 4096:
        raise rejected()
    identity = exchange_identity(code, data["verifier"], data["nonce"])
    if data["action"] == "password-setup":
        require_password_management()
        remaining = AUTH_TTL - int(time.time() - data["started_at"])
        current = lock_profile(db, data["user_id"])
        public_account(current)
        check_version(db, current, data.get("auth_version"), lock=True)
        if (remaining <= 0 or remaining > AUTH_TTL or current.password_hash is not None or
            current.google_sub != identity["sub"].encode("utf-8") or
            current.google_sub.hex() != data["expected_subject"]):
            raise rejected()
        proof = {key: data[key] for key in ("user_id", "auth_version", "session_digest", "started_at")}
        proof["subject"] = identity["sub"]
        return store.put("password-setup-completion", browser, proof, min(COMPLETION_TTL, remaining)), "password-setup"
    result = {"identity": identity, "remember": data["remember"]}
    if data["action"] == "link":
        # Reauthentication never becomes fresh again merely by completing Google consent.
        remaining = AUTH_TTL - int(time.time() - data["reauthenticated_at"])
        if remaining <= 0:
            raise rejected()
        user = lock_profile(db, data["user_id"])
        public_account(user)
        check_version(db, user, data.get("auth_version"), lock=True)
        if user.google_sub is not None or find_by_google_sub(db, identity["sub"].encode("utf-8")):
            raise rejected()
        result.update({k: data[k] for k in ("user_id", "password_digest", "session_digest", "reauthenticated_at")})
        result["auth_version"] = data.get("auth_version")
        return store.put("link-completion", browser, result, min(COMPLETION_TTL, remaining)), "link"
    user = find_by_google_sub(db, identity["sub"].encode("utf-8"))
    if user is not None:
        user = lock_profile(db, user.id)
        public_account(user)
        result.update({"action": "login", "user_id": user.id,
                       "auth_version": current_version(db, user.id, lock=True)})
    else:
        # An email collision is NOT evidence that the Google identity owns the local account.
        if find_by_email(db, identity["email"]) is not None:
            raise HTTPException(409, "Unable to register. Sign in to your existing account to link Google explicitly.")
        result["action"] = "register"
    return store.put("completion", browser, result, COMPLETION_TTL), "completion"


def complete(db: Session, handle: str, browser: str):
    require_jwt_configuration()
    store = get_store()
    data = store.consume(handle, browser, "completion")
    if data["action"] == "register":
        registration = store.put("registration", browser, data, REGISTRATION_TTL)
        return {"status": "registration_required"}, registration
    user = find_by_google_sub(db, data["identity"]["sub"].encode("utf-8"))
    public_account(user)
    user = lock_profile(db, user.id)
    public_account(user)
    check_version(db, user, data.get("auth_version"), lock=True)
    if user.id != data["user_id"]:
        raise rejected()
    return issue_session(db, user, data["remember"]), None


def register(db: Session, handle: str, browser: str, request: GoogleRegistration):
    require_jwt_configuration()
    data = get_store().consume(handle, browser, "registration")
    subject = data["identity"]["sub"].encode("utf-8")
    email = data["identity"]["email"]
    if request.role not in ("user", "owner") or request.accept_terms is not True:
        raise rejected()
    if find_by_google_sub(db, subject) is not None or find_by_email(db, email) is not None:
        raise HTTPException(409, "Unable to register. Please sign in or restart account linking.")
    try:
        user = add_google_user(db, name=request.name, email=email, subject=subject, role=request.role)
        result = issue_session(db, user, data["remember"])
        db.commit()
        return result
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Unable to register. Please sign in or restart account linking.") from None


def link(db: Session, handle: str, browser: str, user: User, authorization: str):
    public_account(user)
    data = get_store().consume(handle, browser, "link-completion")
    if data["user_id"] != user.id or not secrets.compare_digest(data["session_digest"], digest(authorization)):
        raise rejected()
    if not 0 <= time.time() - data["reauthenticated_at"] < AUTH_TTL:
        raise rejected()
    # Reload under a row lock: do not rely on the dependency's earlier identity-map snapshot.
    current = lock_profile(db, user.id)
    public_account(current)
    check_version(db, current, data.get("auth_version"), lock=True)
    if not current.password_hash or not secrets.compare_digest(data["password_digest"], digest(current.password_hash)):
        raise rejected()
    try:
        if not link_google_identity(
            db, user_id=current.id, subject=data["identity"]["sub"].encode("utf-8"),
            password_hash=current.password_hash,
        ):
            raise rejected()
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Unable to link this Google account.") from None
    return {"status": "linked"}


def begin_password_setup(browser: str, user: User, authorization: str):
    require_password_management()
    public_account(user)
    if user.password_hash is not None or user.google_sub is None:
        raise rejected()
    data = {"action": "password-setup", "nonce": new_secret(), "verifier": new_secret(),
            "user_id": user.id, "auth_version": user._authenticated_version,
            "expected_subject": user.google_sub.hex(),
            "session_digest": digest(authorization), "started_at": time.time(), "versioned": True}
    state = get_store().put("password-setup-authorization", browser, data, AUTH_TTL)
    return authorization_url(state, data["nonce"], data["verifier"])


def complete_password_setup(db, handle, browser, user, authorization, request):
    require_password_management()
    public_account(user)
    data = get_store().consume(handle, browser, "password-setup-completion")
    if (data["user_id"] != user.id or
        not secrets.compare_digest(data["session_digest"], digest(authorization)) or
        not 0 <= time.time() - data["started_at"] < AUTH_TTL):
        raise rejected()
    try:
        current = locked_account(db, user, data["auth_version"])
        public_account(current)
        if current.password_hash is not None or current.google_sub != data["subject"].encode("utf-8"):
            raise rejected()
        return write_password(db, current, data["auth_version"], hash_password(request.new_password))
    except Exception:
        db.rollback()
        raise
