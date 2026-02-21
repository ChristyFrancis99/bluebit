"""Initial schema

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'institutions',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('domain', sa.String(), unique=True),
        sa.Column('module_config', postgresql.JSONB(), server_default='{}'),
        sa.Column('weight_config', postgresql.JSONB(), server_default='{}'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('institution_id', postgresql.UUID(as_uuid=False),
                  sa.ForeignKey('institutions.id')),
        sa.Column('email', sa.String(), unique=True, nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('role', sa.String()),
        sa.Column('full_name', sa.String()),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'submissions',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('users.id')),
        sa.Column('institution_id', postgresql.UUID(as_uuid=False),
                  sa.ForeignKey('institutions.id')),
        sa.Column('file_path', sa.String(), nullable=False),
        sa.Column('file_hash', sa.String(), nullable=False),
        sa.Column('text_hash', sa.String()),
        sa.Column('original_filename', sa.String()),
        sa.Column('file_size_bytes', sa.Integer()),
        sa.Column('word_count', sa.Integer()),
        sa.Column('status', sa.String(), server_default='pending'),
        sa.Column('modules_requested', postgresql.JSONB()),
        sa.Column('assignment_id', sa.String()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime()),
    )

    op.create_table(
        'integrity_reports',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('submission_id', postgresql.UUID(as_uuid=False),
                  sa.ForeignKey('submissions.id'), unique=True),
        sa.Column('integrity_score', sa.Float(), nullable=False),
        sa.Column('risk_level', sa.String()),
        sa.Column('confidence', sa.Float()),
        sa.Column('module_results', postgresql.JSONB(), nullable=False),
        sa.Column('weights_used', postgresql.JSONB()),
        sa.Column('recommendation', sa.Text()),
        sa.Column('flags', postgresql.JSONB()),
        sa.Column('pdf_path', sa.String()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'writing_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=False),
                  sa.ForeignKey('users.id'), unique=True),
        sa.Column('feature_vector', postgresql.ARRAY(sa.Float()), nullable=False),
        sa.Column('sample_count', sa.Integer(), server_default='0'),
        sa.Column('last_updated', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'module_configs',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('institution_id', postgresql.UUID(as_uuid=False),
                  sa.ForeignKey('institutions.id')),
        sa.Column('module_id', sa.String(), nullable=False),
        sa.Column('enabled', sa.Boolean(), server_default='true'),
        sa.Column('weight', sa.Float(), server_default='1.0'),
        sa.Column('config', postgresql.JSONB(), server_default='{}'),
        sa.UniqueConstraint('institution_id', 'module_id'),
    )

    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('actor_id', postgresql.UUID(as_uuid=False)),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('resource_type', sa.String()),
        sa.Column('resource_id', sa.String()),
        sa.Column('details', postgresql.JSONB()),
        sa.Column('ip_address', sa.String()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # Indexes
    op.create_index('idx_submissions_user', 'submissions', ['user_id'])
    op.create_index('idx_submissions_status', 'submissions', ['status'])
    op.create_index('idx_reports_risk', 'integrity_reports', ['risk_level'])
    op.create_index('idx_module_configs_inst', 'module_configs', ['institution_id'])
    op.create_index('idx_audit_logs_actor', 'audit_logs', ['actor_id'])


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('module_configs')
    op.drop_table('writing_profiles')
    op.drop_table('integrity_reports')
    op.drop_table('submissions')
    op.drop_table('users')
    op.drop_table('institutions')
