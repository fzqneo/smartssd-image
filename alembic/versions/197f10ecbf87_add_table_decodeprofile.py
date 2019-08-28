"""add table DecodeProfile

Revision ID: 197f10ecbf87
Revises: fb5e2c125b43
Create Date: 2019-08-22 16:46:50.417043

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '197f10ecbf87'
down_revision = 'fb5e2c125b43'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('DecodeProfile',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('path', sa.String(length=1024), nullable=False),
    sa.Column('basename', sa.String(length=1024), nullable=False),
    sa.Column('size', sa.Integer(), nullable=True),
    sa.Column('width', sa.Integer(), nullable=True),
    sa.Column('height', sa.Integer(), nullable=True),
    sa.Column('decode_ms', sa.Float(precision=53), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('DecodeProfile')
    # ### end Alembic commands ###