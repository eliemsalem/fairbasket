"""suivi d'utilisation et avis

Revision ID: 9d4b2c6e8f10
Revises: 7c3e9a1f2b55
Create Date: 2026-10-27 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d4b2c6e8f10'
down_revision: Union[str, None] = '7c3e9a1f2b55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('evenements',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True),
                    sa.Column('quand', sa.DateTime(timezone=True), nullable=False),
                    sa.Column('type', sa.String(20), nullable=False),
                    sa.Column('page', sa.String(80), nullable=True),
                    sa.Column('detail', sa.String(300), nullable=True),
                    sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_evenements_user_id', 'evenements', ['user_id'])
    op.create_index('ix_evenements_quand', 'evenements', ['quand'])
    op.create_index('ix_evenements_type', 'evenements', ['type'])
    op.create_table('avis',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True),
                    sa.Column('quand', sa.DateTime(timezone=True), nullable=False),
                    sa.Column('page', sa.String(80), nullable=True),
                    sa.Column('message', sa.String(2000), nullable=False),
                    sa.Column('traite', sa.Boolean(), server_default=sa.false(), nullable=False),
                    sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_avis_user_id', 'avis', ['user_id'])


def downgrade() -> None:
    op.drop_table('avis')
    op.drop_table('evenements')
