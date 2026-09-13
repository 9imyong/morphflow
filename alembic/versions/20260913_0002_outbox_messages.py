"""transactional outbox for kafka publishing

상태 변경과 Kafka 발행을 한 트랜잭션에 묶을 수 없어, 발행할 메시지를 같은
트랜잭션에 적재해 두고 릴레이가 내보내는 구조로 바꾼다.

Revision ID: 20260913_0002
Revises: 20260310_0001
Create Date: 2026-09-13 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260913_0002"
down_revision = "20260310_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outbox_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.String(length=64), nullable=False),
        sa.Column("topic", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("headers", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", name="uq_outbox_messages_message_id"),
    )
    # 릴레이는 PENDING 만 id 순으로 훑는다. 발행이 끝난 행이 쌓여도 스캔이 커지지 않도록
    # 부분 인덱스를 쓴다.
    op.create_index(
        "ix_outbox_messages_pending",
        "outbox_messages",
        ["id"],
        unique=False,
        postgresql_where=sa.text("status = 'PENDING'"),
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_messages_pending", table_name="outbox_messages")
    op.drop_table("outbox_messages")
