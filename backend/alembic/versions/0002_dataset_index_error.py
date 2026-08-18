"""Add an explicit indexing error field to datasets."""

from alembic import op
import sqlalchemy as sa


revision = "0002_dataset_index_error"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("datasets")}
    if "index_error" not in columns:
        op.add_column("datasets", sa.Column("index_error", sa.Text(), nullable=True))


def downgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("datasets")}
    if "index_error" in columns:
        op.drop_column("datasets", "index_error")
