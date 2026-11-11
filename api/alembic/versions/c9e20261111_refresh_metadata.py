"""Match observation times, standings formats and genuine snapshots.

Revision ID: c9e20261111
Revises: b88b48e25165
"""
from alembic import op
import sqlalchemy as sa
revision = 'c9e20261111'
down_revision = 'b88b48e25165'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('match', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('standing', sa.Column('stage', sa.String(100), nullable=True))
    op.add_column('standing', sa.Column('group_name', sa.String(100), nullable=True))
    op.create_table('standings_snapshot',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('season_id', sa.Integer(), sa.ForeignKey('season.id'), nullable=False),
        sa.Column('captured_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('rows', sa.JSON(), nullable=False))
    op.create_index('ix_standings_snapshot_season_id', 'standings_snapshot', ['season_id'])

def downgrade():
    op.drop_table('standings_snapshot')
    op.drop_column('standing', 'group_name')
    op.drop_column('standing', 'stage')
    op.drop_column('match', 'updated_at')
