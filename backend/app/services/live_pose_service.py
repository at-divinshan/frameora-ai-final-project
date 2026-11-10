"""Serialize successful analysis on the existing User row, including provider work.

This deliberately holds one row lock for a bounded provider call. No stale pending
reservations: failures roll back, successful results commit with usage atomically.
All callers use READ COMMITTED/locking reads for post-lock usage on MySQL.
"""
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import inspect, select, update
from app.models.user import User
from app.models.subscription import Subscription
from app.models.subscription_plan import SubscriptionPlan
from app.models.live_pose_session import LivePoseSession
from app.services.live_pose_provider import SceneResult, MAX_PEOPLE

LIMITS = {"user": {"free": 1, "starter": 5, "plus": 15, "premium": 40},
          "owner": {"basic": 5, "trial": 20, "pro": 100}}

def clock():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def require_schema(db):
    inspector = inspect(db.connection())
    table = LivePoseSession.__table__
    if not inspector.has_table(table.name) or not set(table.columns.keys()) <= {c["name"] for c in inspector.get_columns(table.name)}:
        raise HTTPException(503, "Live Pose Guide AI sessions need the approved database migration. Camera preview remains available.")
    unique = {tuple(c["column_names"]) for c in inspector.get_unique_constraints(table.name)}
    unique.update(tuple(c["column_names"]) for c in inspector.get_indexes(table.name) if c.get("unique"))
    if ("user_id", "request_key") not in unique:
        raise HTTPException(503, "Live Pose Guide session schema is incomplete.")

def allowance(db, user, now):
    if user.role not in LIMITS:
        raise HTTPException(403, "Live Pose Guide is available to users and studio owners.")
    # Existing subscription catalogue is the only source of paid entitlements.
    active = list(db.execute(select(Subscription, SubscriptionPlan).join(
        SubscriptionPlan, Subscription.plan_id == SubscriptionPlan.id).where(
        Subscription.user_id == user.id, Subscription.status == "active").with_for_update()))
    if len(active) > 1:
        raise HTTPException(503, "Subscription state is unavailable.")
    code = "basic" if user.role == "owner" else "free"
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    if active:
        sub, plan = active[0]
        if sub.start_date <= now and (sub.end_date is None or now < sub.end_date):
            if plan.user_role != user.role or not plan.is_active or plan.code not in LIMITS[user.role] or sub.plan_kind != plan.code:
                raise HTTPException(503, "Live Pose Guide plan is unavailable.")
            code = plan.code
            if code == "trial":
                end = min(sub.end_date or sub.start_date + timedelta(days=14), sub.start_date + timedelta(days=14))
                if now >= end:
                    code = "basic"
                    end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
                else:
                    start = sub.start_date
    period = "monthly_utc"
    if code == "free":
        start = end = None
        period = "lifetime"
    elif code == "trial":
        period = "trial_total"
    query = select(LivePoseSession).where(LivePoseSession.user_id == user.id)
    if code == "free":
        query = query.where(LivePoseSession.plan_code == "free")
    else:
        query = query.where(LivePoseSession.created_at >= start, LivePoseSession.created_at < end)
    # Locking reads see latest commits even under MySQL REPEATABLE READ.
    used = len(list(db.scalars(query.with_for_update())))
    limit = LIMITS[user.role][code]
    return dict(plan=code, limit=limit, used=used, remaining=max(0, limit-used),
                period=period, resets_at=end, proposed=not (user.role == "owner" and code == "basic"))

def lock_user(db, user):
    # A no-op write takes a database lock, including in isolated SQLite tests.
    db.execute(update(User).where(User.id == user.id).values(id=User.id))
    current = db.scalar(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))
    if current is None or current.role not in LIMITS:
        raise HTTPException(403, "Live Pose Guide is unavailable for this account.")
    return current

def entitlements(db, user, provider):
    try:
        require_schema(db)
        current = lock_user(db, user)
        return {**allowance(db, current, clock()), "vision_available": provider.available,
                "verification": "Live vision and mobile-device verification pending"}
    finally:
        db.rollback()

def analyze(db, user, key, raw, provider):
    try:
        require_schema(db)
        current = lock_user(db, user)
        digest = sha256(raw).hexdigest()
        previous = db.scalar(select(LivePoseSession).where(LivePoseSession.user_id == current.id,
            LivePoseSession.request_key == key).with_for_update())
        if previous:
            if previous.scene_hash != digest:
                raise HTTPException(409, "This session already uses a different snapshot. Start a new session.")
            try:
                result = SceneResult.model_validate(previous.result).model_dump()
            except ValidationError:
                raise HTTPException(409, "This older session cannot provide multi-person guidance. Reanalyze the scene with a new session.") from None
            db.rollback()
            return result
        now = clock()
        quota = allowance(db, current, now)
        if not quota["remaining"]:
            raise HTTPException(429, "Live Pose Guide allowance exhausted. View your plan for reset details.")
        try:
            result = SceneResult.model_validate(provider.analyze(raw)).model_dump()
        except ValidationError:
            raise HTTPException(502, "Scene analysis returned unusable suggestions. No session was deducted.") from None
        count = result["detected_people_count"]
        if count == 0 or count > MAX_PEOPLE:
            detail = "No people were detected. Include the people you want to photograph and reanalyze." if count == 0 else "This guide supports up to three people. Reframe a smaller group and reanalyze."
            raise HTTPException(422, {"message": detail + " No session was deducted.", "scene": result})
        db.add(LivePoseSession(user_id=current.id, request_key=key, scene_hash=digest,
                              plan_code=quota["plan"], created_at=now, result=result))
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
