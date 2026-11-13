"""Additive phase/publication mappings; migration 010 is applied manually only."""
from datetime import datetime
from sqlalchemy import Integer, DateTime, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class ProjectGenerationPhase(Base):
    __tablename__ = 'ProjectGenerationPhase'
    __table_args__ = (
        UniqueConstraint('project_id', 'phase_number', name='uq_phase_project_number'),
        UniqueConstraint('generation_id', name='uq_phase_generation'),
        CheckConstraint('phase_number > 0', name='chk_phase_positive'),
        {'mysql_engine': 'InnoDB'},
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('CustomerProject.id', name='fk_phase_project'), nullable=False)
    generation_id: Mapped[int] = mapped_column(ForeignKey('AIGeneration.id', name='fk_phase_generation'), nullable=False)
    phase_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

class ShareLinkPhase(Base):
    __tablename__ = 'ShareLinkPhase'
    __table_args__ = (
        UniqueConstraint('share_link_id', 'phase_id', name='uq_link_phase'),
        {'mysql_engine': 'InnoDB'},
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    share_link_id: Mapped[int] = mapped_column(ForeignKey('ShareLink.id', name='fk_phase_link'), nullable=False)
    phase_id: Mapped[int] = mapped_column(ForeignKey('ProjectGenerationPhase.id', name='fk_publication_phase'), nullable=False)
    published_by: Mapped[int] = mapped_column(ForeignKey('User.id', name='fk_phase_publisher'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
