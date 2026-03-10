"""initial job and event schema

Revision ID: 20260310_0001
Revises:
Create Date: 2026-03-10 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260310_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_jobs_status"), "jobs", ["status"], unique=False)

    op.create_table(
        "job_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_job_events_event_id"),
    )
    op.create_index(op.f("ix_job_events_event_type"), "job_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_job_events_job_id"), "job_events", ["job_id"], unique=False)
    op.create_index(op.f("ix_job_events_trace_id"), "job_events", ["trace_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_job_events_trace_id"), table_name="job_events")
    op.drop_index(op.f("ix_job_events_job_id"), table_name="job_events")
    op.drop_index(op.f("ix_job_events_event_type"), table_name="job_events")
    op.drop_table("job_events")

    op.drop_index(op.f("ix_jobs_status"), table_name="jobs")
    op.drop_table("jobs")
