"""Account-state enforcement independent of the optional password-version feature."""
from sqlalchemy import inspect, select
from fastapi import HTTPException
from app.models.account_status import AccountStatus

INACTIVE_MESSAGE = 'This account has been deactivated. Contact the administrator.'

def enabled(db):
    inspector = inspect(db.connection())
    if not inspector.has_table('AccountStatus') or not set(AccountStatus.__table__.columns.keys()) <= {c['name'] for c in inspector.get_columns('AccountStatus')}:
        raise HTTPException(503, 'Required account security schema is unavailable.')
    return True

def require_active(db,user,expected=None):
    enabled(db)
    # Caller holds User first. Locking read sees the latest committed state under MySQL RR.
    row=db.scalar(select(AccountStatus).where(AccountStatus.user_id==user.id).execution_options(populate_existing=True).with_for_update())
    version=row.version if row else 0
    if row is not None and not row.is_active:
        raise HTTPException(401,INACTIVE_MESSAGE,headers={'WWW-Authenticate':'Bearer','X-Auth-Error':'ACCOUNT_INACTIVE'})
    if expected is not None and (type(expected) is not int or expected != version):
        raise HTTPException(401,'Your session is no longer valid. Please sign in again.',headers={'WWW-Authenticate':'Bearer'})
    return version
