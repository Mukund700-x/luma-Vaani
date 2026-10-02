"""002 hospital_core — departments, patients, doctors, doctor_departments

Adds Phase 2 tables and fixes last_login_at column type.

Revision ID: 002
Revises: 001
Create Date: 2026-10-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Fix last_login_at type: TEXT → TIMESTAMPTZ ────────────────────────────
    # Safe USING clause handles empty/null values and any ISO 8601 strings
    # that may have been written by pre-fix code.
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN last_login_at
        TYPE TIMESTAMPTZ
        USING CASE
            WHEN last_login_at IS NULL THEN NULL
            WHEN last_login_at = '' THEN NULL
            ELSE last_login_at::TIMESTAMPTZ
        END
    """)

    # ── departments ───────────────────────────────────────────────────────────
    op.create_table(
        "departments",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "hospital_id", UUID(as_uuid=True),
            sa.ForeignKey("hospitals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("color", sa.String(7)),   # hex color #RRGGBB
        sa.Column("icon", sa.String(50)),   # frontend icon key
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.UniqueConstraint("hospital_id", "slug", name="uq_departments_hospital_slug"),
    )
    op.create_index("ix_departments_hospital_id", "departments", ["hospital_id"])
    op.create_index(
        "ix_departments_hospital_slug", "departments", ["hospital_id", "slug"]
    )

    # ── patients ──────────────────────────────────────────────────────────────
    op.create_table(
        "patients",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "hospital_id", UUID(as_uuid=True),
            sa.ForeignKey("hospitals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mrn", sa.String(100), comment="Medical Record Number"),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20)),
        sa.Column("email", sa.String(255)),
        sa.Column("date_of_birth", sa.Date),
        sa.Column("gender", sa.String(20)),
        sa.Column("blood_group", sa.String(5)),
        sa.Column(
            "preferred_language", sa.String(10),
            nullable=False, server_default="en",
        ),
        sa.Column("emergency_contact", JSONB, nullable=False, server_default="{}"),
        sa.Column("address", JSONB),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.UniqueConstraint(
            "hospital_id", "mrn", name="uq_patients_hospital_mrn"
        ),
    )
    op.create_index("ix_patients_hospital_id", "patients", ["hospital_id"])
    op.create_index("ix_patients_hospital_mrn", "patients", ["hospital_id", "mrn"])
    op.create_index("ix_patients_phone", "patients", ["phone"])
    op.create_index("ix_patients_email", "patients", ["email"])

    # ── doctors ───────────────────────────────────────────────────────────────
    op.create_table(
        "doctors",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "hospital_id", UUID(as_uuid=True),
            sa.ForeignKey("hospitals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column(
            "registration_number", sa.String(100),
            comment="Medical Council / NMC registration number",
        ),
        sa.Column("specialization", sa.String(255)),
        sa.Column("qualifications", sa.Text),
        sa.Column(
            "consultation_fee_paise", sa.BigInteger,
            comment="Consultation fee in paise (100 paise = 1 INR)",
        ),
        sa.Column("bio", sa.Text),
        sa.Column("avatar_url", sa.Text),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="ACTIVE"
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )
    op.create_index("ix_doctors_hospital_id", "doctors", ["hospital_id"])
    op.create_index("ix_doctors_user_id", "doctors", ["user_id"])
    op.create_index(
        "ix_doctors_hospital_status", "doctors", ["hospital_id", "status"]
    )

    # ── doctor_departments ────────────────────────────────────────────────────
    op.create_table(
        "doctor_departments",
        sa.Column(
            "doctor_id", UUID(as_uuid=True),
            sa.ForeignKey("doctors.id", ondelete="CASCADE"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "department_id", UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="CASCADE"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "is_primary", sa.Boolean, nullable=False, server_default="false"
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )
    op.create_index(
        "ix_doctor_departments_department_id",
        "doctor_departments",
        ["department_id"],
    )

    # ── Trigger: auto-update updated_at on departments, patients, doctors ─────
    # PostgreSQL trigger function (reusable across tables)
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    for tbl in ("departments", "patients", "doctors"):
        op.execute(f"""
            CREATE TRIGGER trg_{tbl}_updated_at
            BEFORE UPDATE ON {tbl}
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """)


def downgrade() -> None:
    for tbl in ("departments", "patients", "doctors"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{tbl}_updated_at ON {tbl}")

    op.drop_table("doctor_departments")
    op.drop_table("doctors")
    op.drop_table("patients")
    op.drop_table("departments")

    # Revert last_login_at to TEXT
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN last_login_at
        TYPE TEXT
        USING last_login_at::TEXT
    """)
