"""Phase 3a — audit_log table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b2c3d4e5f6a7'
down_revision: str | None = 'a1b2c3d4e5f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'audit_log',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('actor_id', sa.Uuid(), nullable=True),
        sa.Column('org_id', sa.Uuid(), nullable=False),
        sa.Column(
            'action',
            sa.Enum(
                'MEMBER_INVITED',
                'MEMBER_REMOVED',
                'ROLE_CHANGED',
                'INTEGRATION_CONFIGURED',
                'MCP_SERVER_ADDED',
                'MCP_SERVER_REMOVED',
                'SETTINGS_UPDATED',
                'API_KEY_CREATED',
                'API_KEY_REVOKED',
                'ORG_CREATED',
                'ORG_UPDATED',
                'TEAM_CREATED',
                'TEAM_UPDATED',
                name='auditaction',
            ),
            nullable=False,
        ),
        sa.Column('resource_type', sa.String(), nullable=False),
        sa.Column('resource_id', sa.String(), nullable=False),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(['actor_id'], ['user.id']),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_audit_log_org_created',
        'audit_log',
        ['org_id', sa.text('created_at DESC')],
    )
    op.create_index('ix_audit_log_actor', 'audit_log', ['actor_id'])
    op.create_index('ix_audit_log_action', 'audit_log', ['action'])


def downgrade() -> None:
    op.drop_index('ix_audit_log_action', table_name='audit_log')
    op.drop_index('ix_audit_log_actor', table_name='audit_log')
    op.drop_index('ix_audit_log_org_created', table_name='audit_log')
    op.drop_table('audit_log')
    op.execute('DROP TYPE IF EXISTS auditaction')
