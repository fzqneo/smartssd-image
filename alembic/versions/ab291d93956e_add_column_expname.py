"""add column expname

Revision ID: ab291d93956e
Revises: d5ff93769f21
Create Date: 2019-08-29 13:48:25.358304

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ab291d93956e'
down_revision = 'd5ff93769f21'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('AppExp', sa.Column('expname', sa.String(length=1024), nullable=False))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('AppExp', 'expname')
    # ### end Alembic commands ###
