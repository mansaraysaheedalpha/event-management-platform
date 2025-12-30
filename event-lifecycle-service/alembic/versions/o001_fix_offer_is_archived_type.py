"""Fix offer is_archived column type from VARCHAR to BOOLEAN

Revision ID: o001_fix_offer_archived
Revises: t001_ticket_mgmt
Create Date: 2025-12-30

This migration fixes the data type inconsistency where offer.is_archived
was defined as VARCHAR but should be BOOLEAN to match the ad.is_archived column.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'o001_fix_offer_archived'
down_revision = 't001_ticket_mgmt'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Add a temporary boolean column
    op.add_column('offers', sa.Column('is_archived_temp', sa.Boolean(), nullable=True))

    # Step 2: Migrate data: Convert 'false' string to False boolean, 'true' to True
    op.execute("""
        UPDATE offers
        SET is_archived_temp = CASE
            WHEN is_archived = 'false' THEN FALSE
            WHEN is_archived = 'true' THEN TRUE
            ELSE FALSE
        END
    """)

    # Step 3: Make the temp column NOT NULL now that data is migrated
    op.alter_column('offers', 'is_archived_temp', nullable=False)

    # Step 4: Drop the old VARCHAR column
    op.drop_column('offers', 'is_archived')

    # Step 5: Rename the temp column to the original name
    op.alter_column('offers', 'is_archived_temp', new_column_name='is_archived')


def downgrade() -> None:
    # Reverse the process: Convert BOOLEAN back to VARCHAR
    op.add_column('offers', sa.Column('is_archived_temp', sa.String(), nullable=True))

    op.execute("""
        UPDATE offers
        SET is_archived_temp = CASE
            WHEN is_archived = FALSE THEN 'false'
            WHEN is_archived = TRUE THEN 'true'
            ELSE 'false'
        END
    """)

    op.alter_column('offers', 'is_archived_temp', nullable=False, server_default=sa.text("'false'"))
    op.drop_column('offers', 'is_archived')
    op.alter_column('offers', 'is_archived_temp', new_column_name='is_archived')
