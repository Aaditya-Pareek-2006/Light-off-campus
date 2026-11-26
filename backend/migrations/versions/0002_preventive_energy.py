"""Add room checklists, inspections and energy campaigns."""
from alembic import op
from app.db import Base
from app import models
revision = "0002_preventive_energy"
down_revision = "0001_initial"
branch_labels = None
depends_on = None
def upgrade():
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
def downgrade():
    bind = op.get_bind()
    for table in ("campaign_pledges", "energy_campaigns", "energy_inspections", "room_checklists"):
        op.drop_table(table)
