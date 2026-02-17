"""Phase 3b — integration_config, integration_conversation, user_mcp_server tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c3d4e5f6a7b8'
down_revision: str | None = 'b2c3d4e5f6a7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'integration_config',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('org_id', sa.Uuid(), nullable=False),
        sa.Column('integration_type', sa.String(50), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('config_encrypted', sa.Text(), nullable=True),
        sa.Column('webhook_secret_encrypted', sa.Text(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'org_id',
            'integration_type',
            name='uq_integration_config_org_type',
        ),
    )

    op.create_table(
        'integration_conversation',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('org_id', sa.Uuid(), nullable=False),
        sa.Column('integration_type', sa.String(), nullable=False),
        sa.Column('external_id', sa.Text(), nullable=False),
        sa.Column('conversation_id', sa.Text(), nullable=False),
        sa.Column('external_url', sa.Text(), nullable=True),
        sa.Column('extra_metadata', sa.JSON(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'integration_type',
            'external_id',
            'org_id',
            name='uq_integration_conversation_type_ext_org',
        ),
    )
    op.create_index(
        'ix_integration_conversation_conv',
        'integration_conversation',
        ['conversation_id'],
    )

    op.create_table(
        'user_mcp_server',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('org_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('server_type', sa.String(20), nullable=False),
        sa.Column('config_encrypted', sa.Text(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('approved', sa.Boolean(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_user_mcp_server_user_org',
        'user_mcp_server',
        ['user_id', 'org_id', 'enabled'],
    )


def downgrade() -> None:
    op.drop_index('ix_user_mcp_server_user_org', table_name='user_mcp_server')
    op.drop_table('user_mcp_server')
    op.drop_index(
        'ix_integration_conversation_conv',
        table_name='integration_conversation',
    )
    op.drop_table('integration_conversation')
    op.drop_table('integration_config')
