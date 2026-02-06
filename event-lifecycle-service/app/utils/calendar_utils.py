"""
Calendar utilities for generating ICS files and calendar event data.

This module provides functions to generate RFC 5545 compliant ICS files
for sessions and events with embedded join links and reminder alarms.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from icalendar import Calendar, Event, Alarm


def generate_session_ics(
    session_id: str,
    session_title: str,
    session_description: str,
    start_time: datetime,
    end_time: datetime,
    event_name: str,
    organizer_name: str,
    organizer_email: str,
    join_url: str,
    speakers: list[str],
) -> bytes:
    """
    Generate ICS file for a session with embedded join URL and reminders.

    Args:
        session_id: Unique identifier for the session
        session_title: Title of the session
        session_description: Description of the session
        start_time: Session start time (timezone-aware)
        end_time: Session end time (timezone-aware)
        event_name: Name of the parent event
        organizer_name: Name of the event organizer
        organizer_email: Email of the event organizer
        join_url: Magic link URL for joining the session
        speakers: List of speaker names

    Returns:
        bytes: ICS file content as bytes
    """
    cal = Calendar()
    cal.add("prodid", "-//Event Dynamics//Virtual Events//EN")
    cal.add("version", "2.0")
    cal.add("method", "REQUEST")
    cal.add("calscale", "GREGORIAN")

    event = Event()
    event.add("uid", f"{session_id}@eventdynamics.io")
    event.add("dtstamp", datetime.now(timezone.utc))

    # Ensure timezone-aware datetimes
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)

    event.add("dtstart", start_time)
    event.add("dtend", end_time)
    event.add("summary", f"{session_title} - {event_name}")

    # Build description with join link prominently displayed
    speakers_text = ", ".join(speakers) if speakers else "TBA"
    description = f"""Join this session instantly:
{join_url}

Session: {session_title}
Event: {event_name}
Speaker(s): {speakers_text}

{session_description if session_description else ''}

Powered by Event Dynamics"""

    event.add("description", description.strip())
    event.add("url", join_url)
    event.add("location", "Virtual Event - Click link to join")
    event.add("status", "CONFIRMED")
    event.add("transp", "OPAQUE")
    event.add("sequence", 0)

    # Add organizer
    event.add(
        "organizer",
        f"mailto:{organizer_email}",
        parameters={"cn": organizer_name},
    )

    # 15-minute reminder alarm
    alarm_15 = Alarm()
    alarm_15.add("action", "DISPLAY")
    alarm_15.add("trigger", timedelta(minutes=-15))
    alarm_15.add("description", f"Session starting in 15 minutes: {session_title}")
    event.add_component(alarm_15)

    # 5-minute reminder alarm
    alarm_5 = Alarm()
    alarm_5.add("action", "DISPLAY")
    alarm_5.add("trigger", timedelta(minutes=-5))
    alarm_5.add("description", f"Session starting in 5 minutes: {session_title} - Click to join!")
    event.add_component(alarm_5)

    cal.add_component(event)
    return cal.to_ical()


def generate_event_ics(
    event_id: str,
    event_name: str,
    event_description: str,
    sessions: list[dict],
    organizer_name: str,
    organizer_email: str,
    base_join_url: Optional[str] = None,
) -> bytes:
    """
    Generate ICS file for an entire event with all its sessions.

    Args:
        event_id: Unique identifier for the event
        event_name: Name of the event
        event_description: Description of the event
        sessions: List of session dictionaries containing:
            - id: Session ID
            - title: Session title
            - description: Session description
            - start_time: Session start time
            - end_time: Session end time
            - speakers: List of speaker names
            - join_url: Optional personalized join URL
        organizer_name: Name of the event organizer
        organizer_email: Email of the event organizer
        base_join_url: Optional base URL for the event

    Returns:
        bytes: ICS file content as bytes
    """
    cal = Calendar()
    cal.add("prodid", "-//Event Dynamics//Virtual Events//EN")
    cal.add("version", "2.0")
    cal.add("method", "REQUEST")
    cal.add("calscale", "GREGORIAN")
    cal.add("x-wr-calname", event_name)

    for session in sessions:
        event = Event()
        session_id = session.get("id", "")
        event.add("uid", f"{session_id}@eventdynamics.io")
        event.add("dtstamp", datetime.now(timezone.utc))

        start_time = session.get("start_time")
        end_time = session.get("end_time")

        # Ensure timezone-aware datetimes
        if start_time and start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        if end_time and end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)

        if start_time:
            event.add("dtstart", start_time)
        if end_time:
            event.add("dtend", end_time)

        session_title = session.get("title", "Untitled Session")
        event.add("summary", f"{session_title} - {event_name}")

        # Build description
        join_url = session.get("join_url", base_join_url or "")
        speakers = session.get("speakers", [])
        speakers_text = ", ".join(speakers) if speakers else "TBA"
        session_desc = session.get("description", "")

        description_parts = []
        if join_url:
            description_parts.append(f"Join this session:\n{join_url}")
        description_parts.append(f"\nSession: {session_title}")
        description_parts.append(f"Event: {event_name}")
        description_parts.append(f"Speaker(s): {speakers_text}")
        if session_desc:
            description_parts.append(f"\n{session_desc}")
        description_parts.append("\nPowered by Event Dynamics")

        event.add("description", "\n".join(description_parts))

        if join_url:
            event.add("url", join_url)

        event.add("location", "Virtual Event - Click link to join")
        event.add("status", "CONFIRMED")
        event.add("transp", "OPAQUE")
        event.add("sequence", 0)

        # Add organizer
        event.add(
            "organizer",
            f"mailto:{organizer_email}",
            parameters={"cn": organizer_name},
        )

        # 15-minute reminder
        alarm_15 = Alarm()
        alarm_15.add("action", "DISPLAY")
        alarm_15.add("trigger", timedelta(minutes=-15))
        alarm_15.add("description", f"Session starting in 15 minutes: {session_title}")
        event.add_component(alarm_15)

        # 5-minute reminder
        alarm_5 = Alarm()
        alarm_5.add("action", "DISPLAY")
        alarm_5.add("trigger", timedelta(minutes=-5))
        alarm_5.add("description", f"Session starting in 5 minutes: {session_title}")
        event.add_component(alarm_5)

        cal.add_component(event)

    return cal.to_ical()


def generate_ics_filename(title: str, is_session: bool = True) -> str:
    """
    Generate a sanitized filename for ICS download.

    Args:
        title: Title to use in filename
        is_session: Whether this is a session (True) or event (False)

    Returns:
        str: Sanitized filename with .ics extension
    """
    # Remove special characters and limit length
    sanitized = "".join(c if c.isalnum() or c in " -_" else "" for c in title)
    sanitized = sanitized.strip().replace(" ", "-")[:50]
    prefix = "session" if is_session else "event"
    return f"{prefix}-{sanitized}.ics"
