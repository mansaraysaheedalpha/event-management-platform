"""Create email_preferences and pre_event_emails tables

Revision ID: ep001
Revises: sr001
Create Date: 2026-02-05

This migration creates tables for:
- Email preferences: User opt-in/opt-out settings per event
- Pre-event emails: Tracking pre-event engagement emails sent to attendees
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ep001'
down_revision = 'sr001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==== EMAIL PREFERENCES TABLE ====
    op.create_table(
        'email_preferences',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column(
            'event_id',
            sa.String(),
            sa.ForeignKey('events.id', ondelete='CASCADE'),
            nullable=True,  # NULL = global preference
        ),

        # Email type preferences
        sa.Column(
            'pre_event_agenda',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('true'),
        ),
        sa.Column(
            'pre_event_networking',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('true'),
        ),
        sa.Column(
            'session_reminders',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('true'),
        ),

        # Timestamps
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('NOW()'),
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('NOW()'),
        ),

        # Unique constraint: one preference per user per event (or global)
        sa.UniqueConstraint(
            'user_id',
            'event_id',
            name='uq_email_pref_user_event',
        ),
    )

    # Indexes for email_preferences
    op.create_index(
        'idx_email_preferences_user',
        'email_preferences',
        ['user_id'],
    )
    op.create_index(
        'idx_email_preferences_event',
        'email_preferences',
        ['event_id'],
    )

    # ==== PRE-EVENT EMAILS TABLE ====
    op.create_table(
        'pre_event_emails',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column(
            'registration_id',
            sa.String(),
            sa.ForeignKey('registrations.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'event_id',
            sa.String(),
            sa.ForeignKey('events.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('user_id', sa.String(), nullable=True),

        # Email type: AGENDA, NETWORKING
        sa.Column('email_type', sa.String(20), nullable=False),

        # Date for deduplication (the event date this email is for)
        sa.Column('email_date', sa.Date(), nullable=False),

        # Scheduling and status
        sa.Column(
            'scheduled_at',
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            'sent_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        # Email delivery tracking
        sa.Column(
            'email_status',
            sa.String(20),
            nullable=False,
            server_default=sa.text("'QUEUED'"),
        ),
        sa.Column('resend_message_id', sa.String(255), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),

        # Unique constraint to prevent duplicate emails
        sa.UniqueConstraint(
            'registration_id',
            'event_id',
            'email_type',
            'email_date',
            name='uq_pre_event_email',
        ),
    )

    # Check constraint for email_type
    op.create_check_constraint(
        'check_pre_event_email_type',
        'pre_event_emails',
        "email_type IN ('AGENDA', 'NETWORKING')"
    )

    # Check constraint for email_status
    op.create_check_constraint(
        'check_pre_event_email_status',
        'pre_event_emails',
        "email_status IN ('QUEUED', 'SENT', 'DELIVERED', 'FAILED')"
    )

    # Indexes for pre_event_emails
    op.create_index(
        'idx_pre_event_emails_event',
        'pre_event_emails',
        ['event_id'],
    )
    op.create_index(
        'idx_pre_event_emails_registration',
        'pre_event_emails',
        ['registration_id'],
    )
    op.create_index(
        'idx_pre_event_emails_user',
        'pre_event_emails',
        ['user_id'],
    )
    op.create_index(
        'idx_pre_event_emails_pending',
        'pre_event_emails',
        ['email_status', 'scheduled_at'],
    )
    op.create_index(
        'idx_pre_event_emails_lookup',
        'pre_event_emails',
        ['event_id', 'email_type', 'email_date'],
    )

    # Partial index for failed emails (for retry processing)
    op.create_index(
        'idx_pre_event_emails_failed',
        'pre_event_emails',
        ['scheduled_at'],
        postgresql_where=sa.text("email_status = 'FAILED'"),
    )


def downgrade() -> None:
    # Drop indexes for pre_event_emails
    op.drop_index('idx_pre_event_emails_failed', table_name='pre_event_emails')
    op.drop_index('idx_pre_event_emails_lookup', table_name='pre_event_emails')
    op.drop_index('idx_pre_event_emails_pending', table_name='pre_event_emails')
    op.drop_index('idx_pre_event_emails_user', table_name='pre_event_emails')
    op.drop_index('idx_pre_event_emails_registration', table_name='pre_event_emails')
    op.drop_index('idx_pre_event_emails_event', table_name='pre_event_emails')

    # Drop check constraints
    op.drop_constraint('check_pre_event_email_status', 'pre_event_emails', type_='check')
    op.drop_constraint('check_pre_event_email_type', 'pre_event_emails', type_='check')

    # Drop pre_event_emails table
    op.drop_table('pre_event_emails')

    # Drop indexes for email_preferences
    op.drop_index('idx_email_preferences_event', table_name='email_preferences')
    op.drop_index('idx_email_preferences_user', table_name='email_preferences')

    # Drop email_preferences table
    op.drop_table('email_preferences')
