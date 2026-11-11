"""job board applications

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-11
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0003'
down_revision: str | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('candidates', sa.Column('source', sa.String(length=20), nullable=False, server_default='manual'))
    op.add_column('candidates', sa.Column('applicant_id', sa.UUID(), nullable=True))
    op.add_column('candidates', sa.Column('cv_id', sa.UUID(), nullable=True))
    op.add_column('candidates', sa.Column('cover_note', sa.Text(), nullable=False, server_default=''))
    op.add_column('candidates', sa.Column('match_score', sa.Float(), nullable=True))
    op.create_index(op.f('ix_candidates_applicant_id'), 'candidates', ['applicant_id'], unique=False)
    op.create_unique_constraint('uq_candidates_jd_applicant', 'candidates', ['jd_id', 'applicant_id'])
    op.create_foreign_key('fk_candidates_applicant', 'candidates', 'users', ['applicant_id'], ['id'])
    op.create_foreign_key('fk_candidates_cv', 'candidates', 'cvs', ['cv_id'], ['id'], ondelete='SET NULL')
    # Công ty cũ được tạo khi chưa có lựa chọn 0 cấp duyệt: giữ nguyên 1 cấp


def downgrade() -> None:
    op.drop_constraint('fk_candidates_cv', 'candidates', type_='foreignkey')
    op.drop_constraint('fk_candidates_applicant', 'candidates', type_='foreignkey')
    op.drop_constraint('uq_candidates_jd_applicant', 'candidates', type_='unique')
    op.drop_index(op.f('ix_candidates_applicant_id'), table_name='candidates')
    op.drop_column('candidates', 'match_score')
    op.drop_column('candidates', 'cover_note')
    op.drop_column('candidates', 'cv_id')
    op.drop_column('candidates', 'applicant_id')
    op.drop_column('candidates', 'source')
