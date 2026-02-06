"""Create session_reminders table for automated session reminder emails

Revision ID: sr001
Revises: sp004
Create Date: 2026-02-05

This migration creates the session_reminders table for:
- Tracking reminder emails sent to registered attendees
- Storing magic link token JTIs for security tracking
- Email delivery status monitoring
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'sr001'
down_revision = 'sp004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create session_reminders table
    op.create_table(
        'session_reminders',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column(
            'registration_id',
            sa.String(),
            sa.ForeignKey('registrations.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'session_id',
            sa.String(),
            sa.ForeignKey('sessions.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('event_id', sa.String(), nullable=False),

        # Reminder type: '15_MIN', '5_MIN', etc.
        sa.Column('reminder_type', sa.String(20), nullable=False),

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

        # Magic link tracking
        sa.Column('magic_link_token_jti', sa.String(255), nullable=True),

        # Email delivery status
        sa.Column(
            'email_status',
            sa.String(20),
            nullable=False,
            server_default=sa.text("'QUEUED'"),
        ),
        sa.Column('error_message', sa.Text(), nullable=True),

        # Unique constraint to prevent duplicate reminders
        sa.UniqueConstraint(
            'registration_id',
            'session_id',
            'reminder_type',
            name='uq_session_reminder_unique',
        ),
    )

    # Add check constraint for reminder_type
    op.create_check_constraint(
        'check_reminder_type',
        'session_reminders',
        "reminder_type IN ('15_MIN', '5_MIN', '1_MIN', '30_MIN', '60_MIN')"
    )

    # Add check constraint for email_status
    op.create_check_constraint(
        'check_email_status',
        'session_reminders',
        "email_status IN ('QUEUED', 'SENT', 'DELIVERED', 'FAILED')"
    )

    # Create indexes for performance
    # Index on session_id for looking up all reminders for a session
    op.create_index(
        'idx_session_reminders_session',
        'session_reminders',
        ['session_id'],
    )

    # Index on registration_id for looking up reminders for a registration
    op.create_index(
        'idx_session_reminders_registration',
        'session_reminders',
        ['registration_id'],
    )

    # Composite index for lookup queries
    op.create_index(
        'idx_session_reminders_lookup',
        'session_reminders',
        ['session_id', 'reminder_type'],
    )

    # Index for pending reminders query (used by background task)
    op.create_index(
        'idx_session_reminders_pending',
        'session_reminders',
        ['email_status', 'scheduled_at'],
    )

    # Index on event_id for event-level queries
    op.create_index(
        'idx_session_reminders_event',
        'session_reminders',
        ['event_id'],
    )

    # Partial index for failed reminders (for retry processing)
    op.create_index(
        'idx_session_reminders_failed',
        'session_reminders',
        ['scheduled_at'],
        postgresql_where=sa.text("email_status = 'FAILED'"),
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_session_reminders_failed', table_name='session_reminders')
    op.drop_index('idx_session_reminders_event', table_name='session_reminders')
    op.drop_index('idx_session_reminders_pending', table_name='session_reminders')
    op.drop_index('idx_session_reminders_lookup', table_name='session_reminders')
    op.drop_index('idx_session_reminders_registration', table_name='session_reminders')
    op.drop_index('idx_session_reminders_session', table_name='session_reminders')

    # Drop check constraints
    op.drop_constraint('check_email_status', 'session_reminders', type_='check')
    op.drop_constraint('check_reminder_type', 'session_reminders', type_='check')

    # Drop unique constraint
    op.drop_constraint('uq_session_reminder_unique', 'session_reminders', type_='unique')

    # Drop table
    op.drop_table('session_reminders')
