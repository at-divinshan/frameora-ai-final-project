from fastapi import HTTPException
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from app.models.image_feedback import ImageFeedback
from app.models.media_asset import MediaAsset
from app.models.user import User
from app.services import share_service, project_service, notification_service as notifications


def require_schema(db):
    inspector=inspect(db.connection());table=ImageFeedback.__table__
    if not inspector.has_table(table.name) or not set(table.columns.keys()) <= {c['name'] for c in inspector.get_columns(table.name)}:
        raise HTTPException(503, "Image feedback is unavailable until migration 007 is approved and applied.")
    unique={tuple(c['column_names']) for c in inspector.get_unique_constraints(table.name)}
    unique.update(tuple(c['column_names']) for c in inspector.get_indexes(table.name) if c.get('unique'))
    if ('author_id','request_key') not in unique:
        raise HTTPException(503, "Image feedback schema is incomplete.")


def shared_asset(db, token, asset_id):
    link,project,generation=share_service._active_share(db,token,share_service._now())
    from app.services.project_phase_service import visible_generations
    allowed = [g.id for g in visible_generations(db, link, project, generation)]
    asset=db.scalar(select(MediaAsset).where(MediaAsset.id==asset_id,
        MediaAsset.generation_id.in_(allowed),MediaAsset.user_id==project.studio_owner_id,
        MediaAsset.asset_type=='ai_generated'))
    if asset is None:raise HTTPException(404,"Shared image not found.")
    return link,project,asset


def view(row, *, author=None, plan_id=None, customer=False):
    data=dict(id=row.id,asset_id=row.asset_id,comment=row.comment,status=row.status,
              created_at=row.created_at.isoformat()+'Z',updated_at=row.updated_at.isoformat()+'Z')
    if not customer:data.update(project_id=row.project_id,author_name=author,plan_id=plan_id,revised_asset_id=row.revised_asset_id)
    return data


def customer_comments(db,user,token,asset_id,data=None):
    try:
        link,project,asset=shared_asset(db,token,asset_id)
        require_schema(db)
        if data is not None:
            key=str(data.request_key)
            previous=db.scalar(select(ImageFeedback).where(ImageFeedback.author_id==user.id,ImageFeedback.request_key==key).with_for_update())
            if previous:
                if previous.asset_id!=asset_id or previous.share_link_id!=link.id or previous.comment!=data.comment:
                    raise HTTPException(409,"This submission key was used for different feedback.")
                result=view(previous,customer=True)
            else:
                now=share_service._now()
                if link.expires_at is not None and link.expires_at<=now:raise HTTPException(404,"Share link not found.")
                row=ImageFeedback(project_id=project.id,asset_id=asset.id,share_link_id=link.id,
                    author_id=user.id,request_key=key,comment=data.comment,status='pending',created_at=now,updated_at=now)
                db.add(row);db.flush();result=view(row,customer=True)
                notifications.emit(db,project.studio_owner_id,f'comment:{row.id}',f'New customer feedback on image {asset.id}.',f'/owner/projects/{project.id}#feedback-{row.id}')
        else:
            # Same login-plus-valid-token model. Show only this author's comments,
            # never another customer's identity or unrelated owner feedback.
            rows=db.scalars(select(ImageFeedback).where(ImageFeedback.asset_id==asset_id,
                ImageFeedback.project_id==project.id,ImageFeedback.author_id==user.id).order_by(ImageFeedback.id))
            result=[view(row,customer=True) for row in rows]
        db.commit();return result
    except IntegrityError:
        db.rollback();raise HTTPException(409,"A submission is already in progress. Retry with the same key.") from None
    finally:db.rollback()


def owner_feedback(db,user,project_id,feedback_id=None,data=None):
    try:
        project_service.require_project_access(db,user,project_id,editable=False)
        require_schema(db)
        if data is not None:
            row=db.scalar(select(ImageFeedback).where(ImageFeedback.id==feedback_id,ImageFeedback.project_id==project_id).with_for_update())
            if row is None:raise HTTPException(404,"Feedback not found.")
            old_status,old_revision=row.status,row.revised_asset_id
            if 'revised_asset_id' in data.model_fields_set:
                if data.revised_asset_id is not None:
                    asset=db.scalar(select(MediaAsset).where(MediaAsset.id==data.revised_asset_id,
                        MediaAsset.user_id==user.id,MediaAsset.asset_type=='ai_generated'))
                    if asset is None or asset.id==row.asset_id or share_service._owned_generation(db,user,project_id,asset.generation_id) is None:
                        raise HTTPException(404,"Revision image not found for this project.")
                row.revised_asset_id=data.revised_asset_id
            if data.status is not None:row.status=data.status
            row.updated_at=share_service._now();db.flush()
            notifications.feedback_changed(db,row,old_status,old_revision)
        rows=db.execute(select(ImageFeedback,User.name,MediaAsset.plan_id).join(User,User.id==ImageFeedback.author_id)
            .join(MediaAsset,MediaAsset.id==ImageFeedback.asset_id).where(ImageFeedback.project_id==project_id)
            .order_by(ImageFeedback.asset_id,ImageFeedback.created_at,ImageFeedback.id))
        result=[view(row,author=name,plan_id=plan) for row,name,plan in rows]
        db.commit();return result
    finally:db.rollback()
