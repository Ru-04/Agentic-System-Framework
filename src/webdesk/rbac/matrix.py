"""Canonical Foundation permission matrix (GOVERNANCE §11). Single normative source.

Cell rules:
- DENY: no role may perform the action in Gate 1.
- ROLE: an active role assignment is sufficient (no project membership needed).
- ASSIGNED: active role assignment AND active ProjectMembership on the resource's project.
- GRANTED: active role assignment AND active ProjectAccessGrant on the project whose
  permitted_actions include the permission key.
- ADMIN_METADATA: Administrator role; allows metadata only. Content still needs a content grant.
- ADMIN_CONTENT: Administrator role AND an explicit content grant for the resource.
- ASSIGNED_CLASSIFIED / GRANTED_CLASSIFIED: as ASSIGNED / GRANTED, plus the resource's
  DataClass must be satisfied. ``restricted`` additionally needs a RestrictedContentGrant.

Permissions whose policy is later-phase (``sow.approve``) are DENY in Gate 1.
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    ANALYST = "Analyst"
    TECHNICAL_REVIEWER = "TechnicalReviewer"
    APPROVER = "Approver"
    ADMINISTRATOR = "Administrator"


class Permission(StrEnum):
    PROJECT_CREATE = "project.create"
    PROJECT_VIEW = "project.view"
    PROJECT_EDIT = "project.edit"
    PROJECT_ARCHIVE = "project.archive"
    SOURCE_UPLOAD = "source.upload"
    SOURCE_VERSION = "source.version"
    SOURCE_REPARSE = "source.reparse"
    SOURCE_READ = "source.read"
    REQUIREMENT_VIEW = "requirement.view"
    AUDIT_VIEW = "audit.view"
    USER_MANAGE = "user.manage"
    USER_APPROVE = "user.approve"
    USER_WITHDRAW = "user.withdraw"
    ROLE_ASSIGN = "role.assign"
    MEMBERSHIP_MANAGE = "membership.manage"
    PROJECT_GRANT_MANAGE = "project.grant.manage"
    RESTRICTED_GRANT_MANAGE = "restricted.grant.manage"
    VENDOR_ALLOWLIST_CONFIGURE = "vendor_allowlist.configure"
    RUN_START = "run.start"
    RUN_CANCEL = "run.cancel"
    RUN_RETRY = "run.retry"
    RUN_RESUME = "run.resume"
    DELETION_REQUEST = "deletion.request"
    DELETION_AUTHORIZE = "deletion.authorize"
    CLASSIFICATION_REASSESS = "classification.reassess"
    SOW_APPROVE = "sow.approve"


class Rule(StrEnum):
    DENY = "deny"
    ROLE = "role"
    ASSIGNED = "assigned"
    GRANTED = "granted"
    ASSIGNED_CLASSIFIED = "assigned_classified"
    GRANTED_CLASSIFIED = "granted_classified"
    ADMIN_METADATA = "admin_metadata"
    ADMIN_CONTENT = "admin_content"


A = Role.ANALYST
R = Role.TECHNICAL_REVIEWER
P = Role.APPROVER
D = Role.ADMINISTRATOR

# Roles absent from a row are DENY.
MATRIX: dict[Permission, dict[Role, Rule]] = {
    Permission.PROJECT_CREATE: {A: Rule.ROLE, D: Rule.ROLE},
    Permission.PROJECT_VIEW: {
        A: Rule.ASSIGNED,
        R: Rule.GRANTED,
        P: Rule.GRANTED,
        D: Rule.ADMIN_METADATA,
    },
    Permission.PROJECT_EDIT: {A: Rule.ASSIGNED, D: Rule.ROLE},
    Permission.PROJECT_ARCHIVE: {D: Rule.ROLE},
    Permission.SOURCE_UPLOAD: {A: Rule.ASSIGNED, D: Rule.ADMIN_CONTENT},
    Permission.SOURCE_VERSION: {A: Rule.ASSIGNED, D: Rule.ADMIN_CONTENT},
    Permission.SOURCE_REPARSE: {D: Rule.ROLE},
    Permission.SOURCE_READ: {
        A: Rule.ASSIGNED_CLASSIFIED,
        R: Rule.GRANTED_CLASSIFIED,
        P: Rule.GRANTED_CLASSIFIED,
        D: Rule.ADMIN_CONTENT,
    },
    Permission.REQUIREMENT_VIEW: {
        A: Rule.ASSIGNED,
        R: Rule.GRANTED,
        P: Rule.GRANTED,
        D: Rule.ADMIN_METADATA,
    },
    Permission.AUDIT_VIEW: {A: Rule.ASSIGNED, R: Rule.GRANTED, P: Rule.GRANTED, D: Rule.ROLE},
    Permission.USER_MANAGE: {D: Rule.ROLE},
    Permission.USER_APPROVE: {D: Rule.ROLE},
    Permission.USER_WITHDRAW: {D: Rule.ROLE},
    Permission.ROLE_ASSIGN: {D: Rule.ROLE},
    Permission.MEMBERSHIP_MANAGE: {D: Rule.ROLE},
    Permission.PROJECT_GRANT_MANAGE: {D: Rule.ROLE},
    Permission.RESTRICTED_GRANT_MANAGE: {D: Rule.ROLE},
    Permission.VENDOR_ALLOWLIST_CONFIGURE: {D: Rule.ROLE},
    # Administrator alone never starts a run; an Analyst with membership does (C-1).
    Permission.RUN_START: {A: Rule.ASSIGNED},
    Permission.RUN_CANCEL: {D: Rule.ROLE},
    Permission.RUN_RETRY: {D: Rule.ROLE},
    Permission.RUN_RESUME: {D: Rule.ROLE},
    Permission.DELETION_REQUEST: {},
    Permission.DELETION_AUTHORIZE: {},
    Permission.CLASSIFICATION_REASSESS: {D: Rule.ROLE},
    # Later phase: no SOW output exists in Gate 1, so no role may approve one.
    Permission.SOW_APPROVE: {},
}
