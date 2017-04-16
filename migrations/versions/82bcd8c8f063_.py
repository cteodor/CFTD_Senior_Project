"""empty message

Revision ID: 82bcd8c8f063
Revises: 108d75f407ea
Create Date: 2017-04-09 15:03:12.384000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '82bcd8c8f063'
down_revision = '108d75f407ea'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('challenges', sa.Column('level', sa.Integer(), nullable=True))
    op.add_column('challenges', sa.Column('prereq', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'challenges', 'challenges', ['prereq'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'challenges', type_='foreignkey')
    op.drop_column('challenges', 'prereq')
    op.drop_column('challenges', 'level')
    # ### end Alembic commands ###