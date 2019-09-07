"""Rename path to basedir

Revision ID: ec860df076ec
Revises: 634833f0120e
Create Date: 2019-09-07 12:40:54.657527

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'ec860df076ec'
down_revision = '634833f0120e'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('EurekaExp', sa.Column('basedir', sa.String(length=1024), nullable=False))
    op.drop_column('EurekaExp', 'path')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('EurekaExp', sa.Column('path', mysql.VARCHAR(length=1024), nullable=False))
    op.drop_column('EurekaExp', 'basedir')
    # ### end Alembic commands ###
