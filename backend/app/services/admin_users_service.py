from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select, func, or_, inspect
from app.models.user import User
from app.models.profile import UserProfile
from app.models.account_status import AccountStatus, AccountStatusAudit
from app.repositories.user_repository import lock_profile
from app.services.auth_service import require_single_admin

def ready(db):
    inspector=inspect(db.connection())
    for model in (AccountStatus,AccountStatusAudit):
        if not inspector.has_table(model.__tablename__) or not set(model.__table__.columns.keys()) <= {c['name'] for c in inspector.get_columns(model.__tablename__)}:
            raise HTTPException(503,detail={'code':'ADMIN_USERS_SCHEMA_UNAVAILABLE','message':'User management account-status schema is missing or incompatible.'})

def require_admin(db,user):
    if user.role!='admin':raise HTTPException(403,'Admin access required.')
    require_single_admin(db,user)

def view(user,state):
    return dict(id=user.id,name=user.name,email=user.email,role=user.role,created_at=user.created_at,
                is_active=state.is_active if state else True,status_version=state.version if state else 0)

def listing(db,admin,filters):
    require_admin(db,admin);ready(db)
    conditions=[User.role.in_(['user','owner'])]
    if filters.q.strip():conditions.append(or_(User.name.contains(filters.q.strip(),autoescape=True),User.email.contains(filters.q.strip(),autoescape=True)))
    if filters.role:conditions.append(User.role==filters.role)
    if filters.status:conditions.append(func.coalesce(AccountStatus.is_active,True)==(filters.status=='active'))
    query=select(User,AccountStatus).outerjoin(AccountStatus,AccountStatus.user_id==User.id).where(*conditions)
    # Counting an ORM entity subquery expands deferred columns (including the
    # optional auth_version column on legacy databases). Count rows directly.
    total=db.scalar(select(func.count()).select_from(User).outerjoin(
        AccountStatus,AccountStatus.user_id==User.id).where(*conditions))
    rows=db.execute(query.order_by(User.id.desc()).offset((filters.page-1)*filters.page_size).limit(filters.page_size))
    return dict(items=[view(user,state) for user,state in rows],total=total,page=filters.page,page_size=filters.page_size)

def detail(db,admin,identifier,payment_page=1):
    require_admin(db,admin);ready(db)
    user=db.get(User,identifier)
    if user is None or user.role not in ('user','owner'):raise HTTPException(404,'Account not found.')
    result=view(user,db.get(AccountStatus,identifier))
    result.update(phone=user.phone,is_verified=user.is_verified,studio=None)
    if user.role=='owner':
        profile=db.scalar(select(UserProfile).where(UserProfile.user_id==identifier))
        if profile:result['studio']={key:getattr(profile,key) for key in ('studio_name','studio_phone','studio_address','studio_city','studio_description','onboarding_status')}
    result['status_history']=[dict(actor_id=row.actor_id,is_active=row.new_active,changed_at=row.changed_at,version=row.version) for row in db.scalars(select(AccountStatusAudit).where(AccountStatusAudit.user_id==identifier).order_by(AccountStatusAudit.id.desc()).limit(20))]
    from app.services.admin_billing_service import subscription_details, payment_details
    result['subscription'] = subscription_details(db,user)
    result['payments'] = payment_details(db,user,payment_page)
    return result

def change(db,admin,identifier,data):
    try:
        admin=lock_profile(db,admin.id);require_admin(db,admin);ready(db)
        target=db.get(User,identifier,populate_existing=True,with_for_update=True)
        if target is None:raise HTTPException(404,'Account not found.')
        if target.id==admin.id or target.role not in ('user','owner'):raise HTTPException(403,'Admin accounts cannot be changed.')
        row=db.scalar(select(AccountStatus).where(AccountStatus.user_id==identifier).execution_options(populate_existing=True).with_for_update())
        version=row.version if row else 0
        active=row.is_active if row else True
        # A retried identical completed change is harmless; stale opposite changes are rejected.
        if active==data.is_active:return view(target,row)
        if version!=data.expected_version:raise HTTPException(409,'Account status changed. Refresh before trying again.')
        if version>=2147483647:raise HTTPException(409,'Account status requires administrator review.')
        now=datetime.now(timezone.utc).replace(tzinfo=None)
        if row is None:row=AccountStatus(user_id=identifier,is_active=True,version=0,changed_at=now);db.add(row)
        row.is_active=data.is_active;row.version=version+1;row.changed_at=now
        db.add(AccountStatusAudit(user_id=identifier,actor_id=admin.id,old_active=active,new_active=data.is_active,version=row.version,changed_at=now))
        db.flush();result=view(target,row);db.commit();return result
    finally:db.rollback()
