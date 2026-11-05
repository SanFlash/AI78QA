"""Initial AI78QA domain schema."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("training_websites",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("base_url", sa.String(2048), nullable=False),
        sa.Column("environment_type", sa.String(32), nullable=False),
        sa.Column("allowed_domains", sa.JSON(), nullable=False),
        sa.Column("policy", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("training_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("website_id", sa.String(36), sa.ForeignKey("training_websites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("max_pages", sa.Integer(), nullable=False),
        sa.Column("max_depth", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(24), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)))
    op.create_table("training_observations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("training_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_url", sa.String(2048), nullable=False),
        sa.Column("page_title", sa.String(500), nullable=False),
        sa.Column("element_type", sa.String(48), nullable=False),
        sa.Column("semantic_name", sa.String(500), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("label", sa.String(48)),
        sa.Column("label_verified", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("datasets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("task", sa.String(80), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("ml_model_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("task", sa.String(80), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("artifact_uri", sa.String(2048)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor", sa.String(160), nullable=False),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=False),
        sa.Column("resource_id", sa.String(36), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))

def downgrade():
    for table in ["audit_events", "ml_model_versions", "datasets", "training_observations", "training_sessions", "training_websites", "projects"]:
        op.drop_table(table)
