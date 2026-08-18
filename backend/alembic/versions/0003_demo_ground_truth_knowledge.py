"""Align demo ground truth and add knowledge document metadata."""

from alembic import op
import sqlalchemy as sa


revision = "0003_demo_ground_truth_knowledge"
down_revision = "0002_dataset_index_error"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    ground_columns = {column["name"] for column in inspector.get_columns("ground_truth")}
    additions = {
        "question": sa.Column("question", sa.Text(), nullable=True),
        "kpi_name": sa.Column("kpi_name", sa.String(length=255), nullable=True),
        "expected_interfaces": sa.Column("expected_interfaces", sa.JSON(), nullable=True),
        "expected_components": sa.Column("expected_components", sa.JSON(), nullable=True),
        "expected_knowledge_ids": sa.Column("expected_knowledge_ids", sa.JSON(), nullable=True),
        "expected_status": sa.Column("expected_status", sa.String(length=50), nullable=True),
    }
    for name, column in additions.items():
        if name not in ground_columns:
            op.add_column("ground_truth", column)

    if "knowledge_documents" not in inspector.get_table_names():
        op.create_table(
            "knowledge_documents",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("document_code", sa.String(length=100), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("document_type", sa.String(length=100), nullable=False),
            sa.Column("source", sa.String(length=255), nullable=False),
            sa.Column("version", sa.String(length=50), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("metadata", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("document_code"),
        )
        op.create_index("ix_knowledge_documents_document_code", "knowledge_documents", ["document_code"], unique=True)


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if "knowledge_documents" in inspector.get_table_names():
        op.drop_index("ix_knowledge_documents_document_code", table_name="knowledge_documents")
        op.drop_table("knowledge_documents")
    ground_columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("ground_truth")}
    for name in ("expected_status", "expected_knowledge_ids", "expected_components", "expected_interfaces", "kpi_name", "question"):
        if name in ground_columns:
            op.drop_column("ground_truth", name)
