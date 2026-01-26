# app/core/sponsor_roles.py
"""
Centralized role-to-permission mapping for sponsor users.

This ensures consistency across invitation creation, acceptance, and permission checks.
"""

from typing import Dict, Literal

# Type for sponsor roles
SponsorRole = Literal["admin", "representative", "booth_staff", "viewer"]

# Role descriptions for documentation
ROLE_DESCRIPTIONS = {
    "admin": "Full access to all sponsor features including team management",
    "representative": "Can view and manage leads, send campaigns, and manage booth",
    "booth_staff": "Can view leads and manage booth during the event",
    "viewer": "Read-only access to leads and booth information",
}

# Centralized role-to-permission mapping
ROLE_PERMISSIONS: Dict[SponsorRole, Dict[str, bool]] = {
    "admin": {
        "can_view_leads": True,
        "can_export_leads": True,
        "can_message_attendees": True,
        "can_manage_booth": True,
        "can_invite_others": True,
    },
    "representative": {
        "can_view_leads": True,
        "can_export_leads": True,
        "can_message_attendees": True,  # KEY: Representatives CAN send campaigns
        "can_manage_booth": True,
        "can_invite_others": False,  # Only admins can invite others
    },
    "booth_staff": {
        "can_view_leads": True,
        "can_export_leads": False,
        "can_message_attendees": False,
        "can_manage_booth": True,
        "can_invite_others": False,
    },
    "viewer": {
        "can_view_leads": True,
        "can_export_leads": False,
        "can_message_attendees": False,
        "can_manage_booth": False,
        "can_invite_others": False,
    },
}


def get_permissions_for_role(role: str) -> Dict[str, bool]:
    """
    Get the permission set for a given role.

    Args:
        role: The sponsor user role (admin, representative, booth_staff, viewer)

    Returns:
        Dictionary of permission flags

    Raises:
        ValueError: If role is not recognized
    """
    role_lower = role.lower()

    if role_lower not in ROLE_PERMISSIONS:
        raise ValueError(
            f"Invalid role '{role}'. Must be one of: {', '.join(ROLE_PERMISSIONS.keys())}"
        )

    return ROLE_PERMISSIONS[role_lower].copy()


def apply_role_permissions(role: str, override_permissions: Dict[str, bool] = None) -> Dict[str, bool]:
    """
    Get permissions for a role, optionally overriding specific permissions.

    This allows organizers to grant custom permissions beyond the role defaults
    (e.g., a booth_staff who can also export leads).

    Args:
        role: The sponsor user role
        override_permissions: Optional dict of permissions to override

    Returns:
        Final permission set with overrides applied

    Example:
        >>> apply_role_permissions("representative", {"can_invite_others": True})
        {'can_view_leads': True, 'can_export_leads': True, 'can_message_attendees': True,
         'can_manage_booth': True, 'can_invite_others': True}
    """
    permissions = get_permissions_for_role(role)

    if override_permissions:
        permissions.update(override_permissions)

    return permissions


def validate_role(role: str) -> bool:
    """
    Check if a role is valid.

    Args:
        role: The role to validate

    Returns:
        True if valid, False otherwise
    """
    return role.lower() in ROLE_PERMISSIONS


def get_all_roles() -> list[str]:
    """
    Get a list of all valid roles.

    Returns:
        List of role names
    """
    return list(ROLE_PERMISSIONS.keys())
