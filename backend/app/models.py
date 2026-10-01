"""Data model. A space holds work items, sprints and members; everything else hangs off work items."""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (JSON, Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Table,
                        Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, utcnow

DEFAULT_STATUSES = [
    {"name": "To do", "category": "todo", "wip": 0},
    {"name": "In progress", "category": "doing", "wip": 0},
    {"name": "In review", "category": "doing", "wip": 0},
    {"name": "Done", "category": "done", "wip": 0},
]

ROLES = ("viewer", "member", "admin")
TYPES = ("Epic", "Story", "Task", "Bug", "Subtask")
PRIORITIES = ("Highest", "High", "Medium", "Low")

item_assignees = Table(
    "item_assignees", Base.metadata,
    Column("item_id", ForeignKey("work_items.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)
item_watchers = Table(
    "item_watchers", Base.metadata,
    Column("item_id", ForeignKey("work_items.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    handle: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    prefs: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Space(Base):
    __tablename__ = "spaces"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    seq: Mapped[int] = mapped_column(Integer, default=0)
    statuses: Mapped[list] = mapped_column(JSON, default=lambda: [dict(s) for s in DEFAULT_STATUSES])
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Membership(Base):
    __tablename__ = "memberships"
    space_id: Mapped[int] = mapped_column(ForeignKey("spaces.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), default="member")
    user: Mapped[User] = relationship()


class Sprint(Base):
    __tablename__ = "sprints"
    id: Mapped[int] = mapped_column(primary_key=True)
    space_id: Mapped[int] = mapped_column(ForeignKey("spaces.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    goal: Mapped[str] = mapped_column(Text, default="")
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    state: Mapped[str] = mapped_column(String(16), default="future")  # future | active | closed
    committed_points: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    completed_points: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Version(Base):
    """A release. Sprints are when work happens; versions are what ships."""
    __tablename__ = "versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    space_id: Mapped[int] = mapped_column(ForeignKey("spaces.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    release_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    released: Mapped[bool] = mapped_column(Boolean, default=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class WorkItem(Base):
    __tablename__ = "work_items"
    __table_args__ = (UniqueConstraint("space_id", "number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    space_id: Mapped[int] = mapped_column(ForeignKey("spaces.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    key: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(16), default="Task")
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(60))
    priority: Mapped[str] = mapped_column(String(16), default="Medium")
    reporter_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    points: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    estimate_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    logged_hours: Mapped[float] = mapped_column(Float, default=0)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    labels: Mapped[list] = mapped_column(JSON, default=list)
    checklist: Mapped[list] = mapped_column(JSON, default=list)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("work_items.id", ondelete="SET NULL"), nullable=True)
    sprint_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sprints.id", ondelete="SET NULL"), nullable=True)
    version_id: Mapped[Optional[int]] = mapped_column(ForeignKey("versions.id", ondelete="SET NULL"), nullable=True)
    rank: Mapped[float] = mapped_column(Float, default=0)
    external_key: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    assignees: Mapped[list[User]] = relationship(secondary=item_assignees, lazy="selectin")
    watchers: Mapped[list[User]] = relationship(secondary=item_watchers, lazy="selectin")
    parent: Mapped[Optional["WorkItem"]] = relationship(remote_side="WorkItem.id", lazy="joined")
    space: Mapped[Space] = relationship(lazy="joined")


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("work_items.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    edited_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Link(Base):
    """One row per link. Types read source-to-target: A blocks B, A relates to B, A duplicates B."""
    __tablename__ = "links"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("work_items.id", ondelete="CASCADE"), index=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("work_items.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class History(Base):
    __tablename__ = "history"
    id: Mapped[int] = mapped_column(primary_key=True)
    space_id: Mapped[int] = mapped_column(ForeignKey("spaces.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("work_items.id", ondelete="SET NULL"), nullable=True, index=True)
    item_key: Mapped[str] = mapped_column(String(24))
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    field: Mapped[str] = mapped_column(String(40))
    old_value: Mapped[str] = mapped_column(Text, default="")
    new_value: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Worklog(Base):
    __tablename__ = "worklogs"
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("work_items.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    hours: Mapped[float] = mapped_column(Float)
    note: Mapped[str] = mapped_column(Text, default="")
    day: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Attachment(Base):
    __tablename__ = "attachments"
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("work_items.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    size: Mapped[int] = mapped_column(Integer, default=0)
    storage_name: Mapped[str] = mapped_column(String(80))
    uploaded_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    item_key: Mapped[str] = mapped_column(String(24), default="")
    event: Mapped[str] = mapped_column(String(32))
    text: Mapped[str] = mapped_column(Text)
    in_app: Mapped[bool] = mapped_column(Boolean, default=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    email_pending: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class SavedFilter(Base):
    __tablename__ = "saved_filters"
    id: Mapped[int] = mapped_column(primary_key=True)
    space_id: Mapped[int] = mapped_column(ForeignKey("spaces.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(String(120))
    query: Mapped[str] = mapped_column(Text)
    shared: Mapped[bool] = mapped_column(Boolean, default=False)
