"""job lease with fencing token

Redis SETNX + TTL 은 TTL 이 만료되는 순간 두 워커가 같은 job 을 동시에
처리하는 것을 막지 못했다. 소유권을 job 행으로 옮기고, 결과 기록 시
펜싱 토큰(lease_epoch)을 함께 검사한다.

Revision ID: 20260913_0003
Revises: 20260913_0002
Create Date: 2026-09-13 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260913_0003"
down_revision = "20260913_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("lease_owner", sa.String(length=64), nullable=True))
    op.add_column("jobs", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("lease_epoch", sa.Integer(), nullable=False, server_default="0"))
    # 만료된 lease 회수 스캔용
    op.create_index("ix_jobs_lease_expires_at", "jobs", ["lease_expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_jobs_lease_expires_at", table_name="jobs")
    op.drop_column("jobs", "lease_epoch")
    op.drop_column("jobs", "lease_expires_at")
    op.drop_column("jobs", "lease_owner")
