"""create image_meta table

Revision ID: abc58bff0618
Revises: 
Create Date: 2019-08-13 17:02:47.374612

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'abc58bff0618'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'image_meta',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('path', sa.String(1024), nullable=False),
        sa.Column('format', sa.String(20)),
        sa.Column('size', sa.Integer),
        sa.Column('width', sa.Integer),
        sa.Column('height', sa.Integer)
    )


def downgrade():
    op.drop_table('image_meta')
