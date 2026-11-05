"""Persist browser screenshots with each training session."""
from alembic import op
import sqlalchemy as sa

revision = "0002_evidence_artifacts"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "evidence_artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("training_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(160), nullable=False),
        sa.Column("mime_type", sa.String(80), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "filename", name="uq_evidence_session_filename"),
    )


def downgrade():
    op.drop_table("evidence_artifacts")
