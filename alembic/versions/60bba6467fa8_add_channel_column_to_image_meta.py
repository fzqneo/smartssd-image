"""add channel column to image_meta

Revision ID: 60bba6467fa8
Revises: abc58bff0618
Create Date: 2019-08-13 19:19:39.325345

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '60bba6467fa8'
down_revision = 'abc58bff0618'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('image_meta', sa.Column('channel', sa.Integer))


def downgrade():
    op.drop_column('image_meta', 'channel')
