"""venue sourcing models

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-02-16 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "t003_ticket_check_in_pin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Extend existing venues table with new columns ---
    op.add_column("venues", sa.Column("slug", sa.String(), nullable=True))
    op.add_column("venues", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("venues", sa.Column("city", sa.String(), nullable=True))
    op.add_column("venues", sa.Column("country", sa.String(2), nullable=True))
    op.add_column("venues", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("venues", sa.Column("longitude", sa.Float(), nullable=True))
    op.add_column("venues", sa.Column("website", sa.String(), nullable=True))
    op.add_column("venues", sa.Column("phone", sa.String(), nullable=True))
    op.add_column("venues", sa.Column("email", sa.String(), nullable=True))
    op.add_column("venues", sa.Column("whatsapp", sa.String(), nullable=True))
    op.add_column("venues", sa.Column("cover_photo_id", sa.String(), nullable=True))
    op.add_column("venues", sa.Column("total_capacity", sa.Integer(), nullable=True))
    op.add_column(
        "venues",
        sa.Column(
            "is_public", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.add_column(
        "venues",
        sa.Column(
            "status", sa.String(), nullable=False, server_default=sa.text("'draft'")
        ),
    )
    op.add_column("venues", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.add_column(
        "venues", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "venues", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "venues",
        sa.Column(
            "verified", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.add_column(
        "venues",
        sa.Column(
            "domain_match",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "venues",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "venues",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Status constraint (H-18)
    op.create_check_constraint(
        "ck_venues_status",
        "venues",
        "status IN ('draft','pending_review','approved','rejected','suspended')",
    )

    # Indexes on venues
    op.create_unique_constraint("uq_venues_slug", "venues", ["slug"])
    op.create_index("ix_venues_slug", "venues", ["slug"])
    op.create_index("ix_venues_city", "venues", ["city"])
    op.create_index("ix_venues_country", "venues", ["country"])
    op.create_index("ix_venues_status", "venues", ["status"])
    op.create_index("ix_venues_lat_lng", "venues", ["latitude", "longitude"])

    # --- venue_spaces ---
    op.create_table(
        "venue_spaces",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "venue_id",
            sa.String(),
            sa.ForeignKey("venues.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("floor_level", sa.String(), nullable=True),
        sa.Column(
            "layout_options",
            ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- venue_space_pricing ---
    op.create_table(
        "venue_space_pricing",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "space_id",
            sa.String(),
            sa.ForeignKey("venue_spaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("rate_type", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- venue_photos ---
    op.create_table(
        "venue_photos",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "venue_id",
            sa.String(),
            sa.ForeignKey("venues.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "space_id",
            sa.String(),
            sa.ForeignKey("venue_spaces.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("s3_key", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "is_cover",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- amenity_categories ---
    op.create_table(
        "amenity_categories",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("icon", sa.String(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- amenities ---
    op.create_table(
        "amenities",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "category_id",
            sa.String(),
            sa.ForeignKey("amenity_categories.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(), nullable=True),
        sa.Column("metadata_schema", JSONB, nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- venue_amenities (join table) ---
    op.create_table(
        "venue_amenities",
        sa.Column(
            "venue_id",
            sa.String(),
            sa.ForeignKey("venues.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "amenity_id",
            sa.String(),
            sa.ForeignKey("amenities.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- venue_verification_documents ---
    op.create_table(
        "venue_verification_documents",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "venue_id",
            sa.String(),
            sa.ForeignKey("venues.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("document_type", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("s3_key", sa.String(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default=sa.text("'uploaded'"),
        ),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- Seed amenity categories and amenities ---
    _seed_amenities()


def _seed_amenities():
    """Insert predefined amenity categories and amenities."""
    import uuid

    amenity_categories = op.get_bind()

    seed_data = {
        "Accessibility": {
            "icon": "\u267f",
            "sort_order": 0,
            "amenities": [
                ("Wheelchair access", None, 0),
                ("Elevator", None, 1),
                ("Accessible restrooms", None, 2),
                ("Braille signage", None, 3),
            ],
        },
        "Technology": {
            "icon": "\U0001f4e1",
            "sort_order": 1,
            "amenities": [
                ("Wi-Fi", {"speed_tier": ["basic", "standard", "high"]}, 0),
                ("Projector", None, 1),
                ("Sound system", None, 2),
                ("Video conferencing", None, 3),
                ("Screens/TVs", None, 4),
                ("Microphones", None, 5),
            ],
        },
        "Catering": {
            "icon": "\U0001f37d\ufe0f",
            "sort_order": 2,
            "amenities": [
                ("In-house catering", None, 0),
                ("External catering allowed", None, 1),
                ("Halal options", None, 2),
                ("Vegetarian options", None, 3),
                ("Kitchen available", None, 4),
                ("Bar/drinks", None, 5),
            ],
        },
        "Infrastructure": {
            "icon": "\U0001f3d7\ufe0f",
            "sort_order": 3,
            "amenities": [
                ("Parking", None, 0),
                ("Generator/backup power", None, 1),
                ("Air conditioning", None, 2),
                ("Security", None, 3),
                ("On-site staff", None, 4),
            ],
        },
        "Outdoor": {
            "icon": "\U0001f333",
            "sort_order": 4,
            "amenities": [
                ("Garden/outdoor space", None, 0),
                ("Rooftop", None, 1),
                ("Pool area", None, 2),
                ("Terrace", None, 3),
                ("Courtyard", None, 4),
            ],
        },
        "Payment": {
            "icon": "\U0001f4b3",
            "sort_order": 5,
            "amenities": [
                ("Mobile money (M-Pesa)", None, 0),
                ("Card payment", None, 1),
                ("Bank transfer", None, 2),
                ("Invoice", None, 3),
            ],
        },
    }

    for cat_name, cat_info in seed_data.items():
        cat_id = f"vac_{uuid.uuid4().hex[:12]}"
        amenity_categories.execute(
            sa.text(
                "INSERT INTO amenity_categories (id, name, icon, sort_order) "
                "VALUES (:id, :name, :icon, :sort_order)"
            ),
            {
                "id": cat_id,
                "name": cat_name,
                "icon": cat_info["icon"],
                "sort_order": cat_info["sort_order"],
            },
        )

        for amenity_name, metadata_schema, sort_order in cat_info["amenities"]:
            amenity_id = f"vam_{uuid.uuid4().hex[:12]}"
            # Use sa.insert instead of raw SQL so SQLAlchemy's JSONB type handles
            # serialization — avoids double-encoding from json.dumps()
            amenity_categories.execute(
                sa.text(
                    "INSERT INTO amenities (id, category_id, name, metadata_schema, sort_order) "
                    "VALUES (:id, :category_id, :name, :metadata_schema, :sort_order)"
                ).bindparams(sa.bindparam("metadata_schema", type_=JSONB)),
                {
                    "id": amenity_id,
                    "category_id": cat_id,
                    "name": amenity_name,
                    "metadata_schema": metadata_schema,
                    "sort_order": sort_order,
                },
            )


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("venue_verification_documents")
    op.drop_table("venue_amenities")
    op.drop_table("amenities")
    op.drop_table("amenity_categories")
    op.drop_table("venue_photos")
    op.drop_table("venue_space_pricing")
    op.drop_table("venue_spaces")

    # Drop indexes from venues
    op.drop_index("ix_venues_lat_lng", table_name="venues")
    op.drop_index("ix_venues_status", table_name="venues")
    op.drop_index("ix_venues_country", table_name="venues")
    op.drop_index("ix_venues_city", table_name="venues")
    op.drop_index("ix_venues_slug", table_name="venues")
    op.drop_constraint("uq_venues_slug", "venues", type_="unique")
    op.drop_constraint("ck_venues_status", "venues", type_="check")

    # Drop new columns from venues
    columns_to_drop = [
        "slug", "description", "city", "country", "latitude", "longitude",
        "website", "phone", "email", "whatsapp", "cover_photo_id",
        "total_capacity", "is_public", "status", "rejection_reason",
        "submitted_at", "approved_at", "verified", "domain_match",
        "created_at", "updated_at",
    ]
    for col in columns_to_drop:
        op.drop_column("venues", col)
