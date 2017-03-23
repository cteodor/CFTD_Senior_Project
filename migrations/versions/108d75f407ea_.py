"""empty message

Revision ID: 108d75f407ea
Revises: cb3cfcc47e2f
Create Date: 2017-03-05 16:33:59.848346

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '108d75f407ea'
down_revision = 'cb3cfcc47e2f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('sections',
    sa.Column('sectionNumber', sa.Integer(), nullable=False),
    sa.Column('courseNumber', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('sectionNumber')
    )
    op.create_table('students',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=True),
    sa.Column('email', sa.String(length=128), nullable=True),
    sa.Column('teamid', sa.Integer(), nullable=True),
    sa.Column('password', sa.String(length=128), nullable=True),
    sa.Column('bracket', sa.String(length=32), nullable=True),
    sa.Column('banned', sa.Boolean(), nullable=True),
    sa.Column('verified', sa.Boolean(), nullable=True),
    sa.Column('admin', sa.Boolean(), nullable=True),
    sa.Column('joined', sa.DateTime(), nullable=True),
    sa.Column('sectionid', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['sectionid'], ['sections.sectionNumber'], ),
    sa.ForeignKeyConstraint(['teamid'], ['teams.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('name')
    )
    op.add_column(u'awards', sa.Column('studentid', sa.Integer(), nullable=True))
    op.drop_constraint(None, 'awards', type_='foreignkey')
    op.create_foreign_key(None, 'awards', 'students', ['studentid'], ['id'])
    op.drop_column(u'awards', 'teamid')
    op.add_column(u'solves', sa.Column('studentid', sa.Integer(), nullable=True))
    op.create_unique_constraint(None, 'solves', ['chalid', 'studentid'])
    op.drop_constraint(None, 'solves', type_='foreignkey')
    op.create_foreign_key(None, 'solves', 'students', ['studentid'], ['id'])
    op.drop_column(u'solves', 'teamid')
    op.add_column(u'teams', sa.Column('sectionNumber', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'teams', 'sections', ['sectionNumber'], ['sectionNumber'])
    op.drop_column(u'teams', 'website')
    op.drop_column(u'teams', 'verified')
    op.drop_column(u'teams', 'admin')
    op.drop_column(u'teams', 'country')
    op.drop_column(u'teams', 'banned')
    op.drop_column(u'teams', 'joined')
    op.drop_column(u'teams', 'affiliation')
    op.drop_column(u'teams', 'bracket')
    op.drop_column(u'teams', 'password')
    op.drop_column(u'teams', 'email')
    op.add_column(u'tracking', sa.Column('student', sa.Integer(), nullable=True))
    op.drop_constraint(None, 'tracking', type_='foreignkey')
    op.create_foreign_key(None, 'tracking', 'students', ['student'], ['id'])
    op.drop_column(u'tracking', 'team')
    op.add_column(u'wrong_keys', sa.Column('studentid', sa.Integer(), nullable=True))
    op.drop_constraint(None, 'wrong_keys', type_='foreignkey')
    op.create_foreign_key(None, 'wrong_keys', 'students', ['studentid'], ['id'])
    op.drop_column(u'wrong_keys', 'teamid')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(u'wrong_keys', sa.Column('teamid', sa.INTEGER(), nullable=True))
    op.drop_constraint(None, 'wrong_keys', type_='foreignkey')
    op.create_foreign_key(None, 'wrong_keys', 'teams', ['teamid'], ['id'])
    op.drop_column(u'wrong_keys', 'studentid')
    op.add_column(u'tracking', sa.Column('team', sa.INTEGER(), nullable=True))
    op.drop_constraint(None, 'tracking', type_='foreignkey')
    op.create_foreign_key(None, 'tracking', 'teams', ['team'], ['id'])
    op.drop_column(u'tracking', 'student')
    op.add_column(u'teams', sa.Column('email', sa.VARCHAR(length=128), nullable=True))
    op.add_column(u'teams', sa.Column('password', sa.VARCHAR(length=128), nullable=True))
    op.add_column(u'teams', sa.Column('bracket', sa.VARCHAR(length=32), nullable=True))
    op.add_column(u'teams', sa.Column('affiliation', sa.VARCHAR(length=128), nullable=True))
    op.add_column(u'teams', sa.Column('joined', sa.DATETIME(), nullable=True))
    op.add_column(u'teams', sa.Column('banned', sa.BOOLEAN(), nullable=True))
    op.add_column(u'teams', sa.Column('country', sa.VARCHAR(length=32), nullable=True))
    op.add_column(u'teams', sa.Column('admin', sa.BOOLEAN(), nullable=True))
    op.add_column(u'teams', sa.Column('verified', sa.BOOLEAN(), nullable=True))
    op.add_column(u'teams', sa.Column('website', sa.VARCHAR(length=128), nullable=True))
    op.drop_constraint(None, 'teams', type_='foreignkey')
    op.drop_column(u'teams', 'sectionNumber')
    op.add_column(u'solves', sa.Column('teamid', sa.INTEGER(), nullable=True))
    op.drop_constraint(None, 'solves', type_='foreignkey')
    op.create_foreign_key(None, 'solves', 'teams', ['teamid'], ['id'])
    op.drop_constraint(None, 'solves', type_='unique')
    op.drop_column(u'solves', 'studentid')
    op.add_column(u'awards', sa.Column('teamid', sa.INTEGER(), nullable=True))
    op.drop_constraint(None, 'awards', type_='foreignkey')
    op.create_foreign_key(None, 'awards', 'teams', ['teamid'], ['id'])
    op.drop_column(u'awards', 'studentid')
    op.drop_table('students')
    op.drop_table('sections')
    # ### end Alembic commands ###