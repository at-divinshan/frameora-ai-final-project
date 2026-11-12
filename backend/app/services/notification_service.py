"""Transactional events; no tokens, private URLs, provider calls or credit mutations."""
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import inspect, select, func
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models.app_notification import AppNotification as N
from app.services import subscription_service

LOW_CREDITS = 2
EXPIRY_WARNING_DAYS = 3

def available(db):
    return inspect(db.connection()).has_table(N.__tablename__)

def emit(db, user_id, key, message, href):
    # Until migration approval, existing comments/generation continue working.
    if not available(db): return
    if db.scalar(select(N.id).where(N.user_id == user_id, N.event_key == key)): return
    try:
        with db.begin_nested():
            db.add(N(user_id=user_id, event_key=key, message=message, href=href,
                     is_read=False, created_at=subscription_service.clock()))
            db.flush()
    except IntegrityError:
        # Concurrent replay of an already-recorded event must not undo business work.
        if not db.scalar(select(N.id).where(N.user_id == user_id, N.event_key == key)): raise

def recipient_inbox(db, user_id):
    from app.models.user import User
    role=db.scalar(select(User.role).where(User.id==user_id))
    return '/owner/notifications' if role == 'owner' else '/user/notifications'

def feedback_changed(db, row, old_status, old_revision):
    changes=[]
    if row.status != old_status: changes.append('Feedback status: ' + row.status.replace('_', ' ') + '.')
    if row.revised_asset_id != old_revision and row.revised_asset_id is not None:
        changes.append('The studio linked a revised image. Ask the studio for its secure share link.')
    if changes:
        emit(db,row.author_id,'feedback-change:'+str(row.id)+':'+str(uuid4()),
             f'Image {row.asset_id}: ' + ' '.join(changes), recipient_inbox(db,row.author_id))

def owner_state(db, user, state, history=()):
    now=subscription_service.clock()
    period=str(state.get('period_start'))
    if state.get('status') == 'active' and state.get('reason') != 'onboarding_required':
        balance=state['remaining_credits']
        if balance <= LOW_CREDITS or balance < state['batch_cost']:
            level='exhausted' if balance <= 0 else 'low'
            emit(db,user.id,f"credits:{state.get('subscription_id')}:{period}:{level}",
                 f'AI credits {level}: {balance} remaining. A batch requires {state["batch_cost"]} credits.', '/owner/subscription')
    for sub in history:
        if sub.end_date and sub.plan_kind in ('trial','pro') and sub.status in ('active','expired'):
            if sub.end_date <= now: kind='expired'
            elif sub.end_date <= now+timedelta(days=EXPIRY_WARNING_DAYS): kind='expiring'
            else: continue
            emit(db,user.id,f'subscription:{sub.id}:{sub.end_date.isoformat()}:{kind}',
                 f'Your {sub.plan_kind} subscription '+('has expired.' if kind=='expired' else 'expires within 3 days.'), '/owner/subscription')

def reconcile_owner(db,user):
    from app.services.owner_entitlement_service import resolve_locked
    from app.models.subscription import Subscription
    from app.models.customer_project import CustomerProject
    from app.models.share_link import ShareLink
    _,state=resolve_locked(db,user,now=subscription_service.clock())
    history=list(db.scalars(select(Subscription).where(Subscription.user_id==user.id)))
    owner_state(db,user,state,history)
    project_count=db.scalar(select(func.count()).select_from(CustomerProject).where(CustomerProject.studio_owner_id==user.id,CustomerProject.deleted_at.is_(None)))
    share_count=db.scalar(select(func.count()).select_from(ShareLink).join(CustomerProject,CustomerProject.id==ShareLink.project_id).where(CustomerProject.studio_owner_id==user.id,CustomerProject.deleted_at.is_(None),ShareLink.is_active.is_(True), (ShareLink.expires_at.is_(None)) | (ShareLink.expires_at>subscription_service.clock())))
    for name,count,limit,path in [('projects',project_count,state['max_projects'],'/owner/projects'),('share links',share_count,state['max_share_links'],'/owner/projects')]:
        if limit and count >= limit:
            emit(db,user.id,f"limit:{name}:{state.get('subscription_id')}:{state.get('period_start')}:{limit}",f'Your {name} limit ({limit}) has been reached. Existing access remains governed by your plan.',path)

def inbox(db,user,before=None,limit=20):
    if not available(db): raise HTTPException(503,'Notifications are unavailable until migration 008 is applied.')
    try:
        if user.role == 'owner': reconcile_owner(db,user)
        query=select(N).where(N.user_id==user.id,N.is_read.is_(False))
        if before: query=query.where(N.id<before)
        rows=list(db.scalars(query.order_by(N.id.desc()).limit(limit)))
        unread=db.scalar(select(func.count()).select_from(N).where(N.user_id==user.id,N.is_read.is_(False)))
        result={'items':[dict(id=n.id,message=n.message,href=n.href,is_read=n.is_read,created_at=n.created_at.isoformat()+'Z') for n in rows], 'unread_count':unread, 'next_before':rows[-1].id if len(rows)==limit else None}
        db.commit();return result
    finally: db.rollback()

def mark(db,user,notification_id,is_read):
    if not available(db): raise HTTPException(503,'Notifications are unavailable until migration 008 is applied.')
    try:
        row=db.scalar(select(N).where(N.id==notification_id,N.user_id==user.id).with_for_update())
        if not row: raise HTTPException(404,'Notification not found.')
        row.is_read=is_read;db.commit();return {'id':row.id,'is_read':is_read}
    finally: db.rollback()


def revision_shared(db, project_id, generation_id, share_id):
    from app.models.image_feedback import ImageFeedback
    from app.models.media_asset import MediaAsset
    if not available(db) or not inspect(db.connection()).has_table('ImageFeedback'): return
    rows=db.scalars(select(ImageFeedback).join(MediaAsset,MediaAsset.id==ImageFeedback.revised_asset_id).where(ImageFeedback.project_id==project_id,MediaAsset.generation_id==generation_id))
    for row in rows:
        emit(db,row.author_id,f'revision-share:{share_id}:{row.id}',f'The studio has shared a revised batch for image {row.asset_id}. Use the new secure link supplied by the studio.', recipient_inbox(db,row.author_id))
