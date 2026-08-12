"""Initial application schema.

The canonical schema is declared by SQLAlchemy models. The application creates it
idempotently on first boot; this migration provides an explicit Alembic baseline.
"""
from alembic import op
from app.database import Base
from app import models  # noqa: F401
revision="0001_initial"; down_revision=None; branch_labels=None; depends_on=None
def upgrade():
    bind=op.get_bind(); Base.metadata.create_all(bind=bind)
def downgrade():
    bind=op.get_bind(); Base.metadata.drop_all(bind=bind)

