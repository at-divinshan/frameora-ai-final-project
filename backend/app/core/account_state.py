"""Account-state enforcement independent of the optional password-version feature."""
from sqlalchemy import inspect, select
from fastapi import HTTPException
from app.models.account_status import AccountStatus

INACTIVE_MESSAGE = 'This account has been deactivated. Contact the administrator.'

def enabled(db):
    return inspect(db.connection()).has_table('AccountStatus')

def require_active(db,user,expected=None):
    if not enabled(db): return 0
    # Caller holds User first. Locking read sees the latest committed state under MySQL RR.
    row=db.scalar(select(AccountStatus).where(AccountStatus.user_id==user.id).execution_options(populate_existing=True).with_for_update())
    version=row.version if row else 0
    if row is not None and not row.is_active:
        raise HTTPException(401,INACTIVE_MESSAGE,headers={'WWW-Authenticate':'Bearer','X-Auth-Error':'ACCOUNT_INACTIVE'})
    if expected is not None and (type(expected) is not int or expected != version):
        raise HTTPException(401,'Your session is no longer valid. Please sign in again.',headers={'WWW-Authenticate':'Bearer'})
    return version
