# User and Organization Service - Feature Documentation

## Overview

The **user-and-org service** is a NestJS-based microservice that handles authentication, user management, organization management, invitations, 2FA, permissions, and audit logging. It provides both REST and GraphQL APIs with Apollo Federation support.

**Tech Stack:** Node.js, NestJS, Prisma (PostgreSQL), Redis, JWT, TOTP (Speakeasy), Resend API

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [User Management](#2-user-management)
3. [Organization Management](#3-organization-management)
4. [Invitation System](#4-invitation-system)
5. [Two-Factor Authentication (2FA)](#5-two-factor-authentication-2fa)
6. [Role & Permission System](#6-role--permission-system)
7. [Audit Logging](#7-audit-logging)
8. [Email Service](#8-email-service)
9. [Internal API](#9-internal-api)
10. [Security Features](#10-security-features)

---

## 1. Authentication

**Location:** `src/auth/`

### Endpoints

| Feature | REST Endpoint | GraphQL Mutation/Query |
|---------|---------------|------------------------|
| Login | `POST /auth/login` | `login(input: LoginInput)` |
| Login with 2FA | `POST /auth/login/2fa` | `login2FA(input: Login2FAInput)` |
| Logout | `POST /auth/logout` | `logout()` |
| Refresh Token | `POST /auth/refresh` | `refreshToken()` |
| Request Password Reset | `POST /auth/password-reset-request` | `requestPasswordReset(input)` |
| Complete Password Reset | `POST /auth/password-reset` | `performPasswordReset(input)` |
| Accept Invitation | `POST /auth/invitations/:token/accept` | - |
| Switch Organization | `POST /auth/token/switch` | `switchOrganization(organizationId)` |

### Key Files

- Controller: `src/auth/auth.controller.ts`
- Resolver: `src/auth/auth.resolver.ts`
- Service: `src/auth/auth.service.ts`
- DTOs: `src/auth/dto/`
- Guards: `src/auth/guards/`
- Strategies: `src/auth/strategies/`

### Authentication Flow

1. User submits email/password
2. System validates credentials and checks for account lockout
3. If 2FA is enabled, returns `requires2FA: true` with `userIdFor2FA`
4. If 2FA not enabled, returns JWT access token + refresh token (in HTTP-only cookie)
5. Access token expires in short time, refresh token used to get new access tokens

### Security Features

- JWT-based authentication (Access + Refresh tokens)
- Refresh tokens stored in HTTP-only cookies
- Account lockout after 5 failed login attempts (15 min lockout)
- Rate limiting: 10 req/min (strict), 100 req/min (general)
- CSRF protection for GraphQL endpoints

---

## 2. User Management

**Location:** `src/users/`

### Endpoints

| Feature | REST Endpoint | GraphQL Mutation/Query |
|---------|---------------|------------------------|
| Register User (Organizer) | `POST /users` | `registerUser(input)` |
| Register Attendee | - | `registerAttendee(input)` |
| Get My Profile | `GET /users/me` | `getMyProfile()` |
| Update Profile | `PATCH /users/me` | `updateMyProfile(input)` |
| Change Password | `PUT /users/me/password` | `changePassword(input)` |
| Request Email Change | `PATCH /users/me/email` | - |
| Verify Old Email | `GET /users/email-change/verify-old/:token` | - |
| Finalize Email Change | `GET /users/email-change/finalize/:token` | - |
| Get User by ID | - | `user(id: ID!)` |

### Key Files

- Controller: `src/users/users.controller.ts`
- Resolver: `src/users/users.resolver.ts`
- Service: `src/users/users.service.ts`
- DTOs: `src/users/dto/`

### User Types

- **ORGANIZER** - Can create/manage organizations and events
- **ATTENDEE** - Can only attend events (no organization membership)

### Password Requirements

- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- At least one special character

### Email Change Flow (2-Step Verification)

1. User requests email change with new email
2. Verification email sent to OLD email
3. User confirms via old email link
4. Confirmation email sent to NEW email
5. User finalizes via new email link

---

## 3. Organization Management

**Location:** `src/organizations/`

### Endpoints

| Feature | REST Endpoint | GraphQL Mutation/Query |
|---------|---------------|------------------------|
| Create Organization | `POST /organizations` | `onboardingCreateOrganization(input)` |
| Create Additional Org | - | `createAdditionalOrganization(input)` |
| List My Organizations | `GET /organizations` | `myOrganizations()` |
| Get Organization | `GET /organizations/:orgId` | `organization(id: ID!)` |
| Update Organization | `PUT /organizations/:orgId` | `updateOrganization(input)` |
| Delete Organization | `DELETE /organizations/:orgId` | `deleteOrganization(input)` |
| Restore Organization | `GET /organizations/restore/:token` | `restoreOrganization(organizationId)` |
| List Members | `GET /organizations/:orgId/members` | `organizationMembers()` |
| Remove Member | `DELETE /organizations/:orgId/members/:memberId` | `removeMember(memberId)` |
| Update Member Role | `PUT /organizations/:orgId/members/:userId/role` | `updateMemberRole(input)` |
| List Roles | - | `listRolesForOrg()` |

### Key Files

- Controller: `src/organizations/organizations.controller.ts`
- Resolver: `src/organizations/organizations.resolver.ts`
- Service: `src/organizations/organizations.service.ts`
- DTOs: `src/organizations/dto/`

### Organization Deletion Flow

1. **Soft Delete:** Organization marked with `PENDING_DELETION` status
2. **Grace Period:** 30 days to restore via email link with single-use token
3. **Notification:** Email sent to all organization members
4. **Restore:** Click restore link or call restore endpoint within grace period
5. **Permanent Deletion:** After grace period expires

### Organization Status

- `ACTIVE` - Normal operational status
- `PENDING_DELETION` - Scheduled for deletion, can be restored

---

## 4. Invitation System

**Location:** `src/invitations/`

### Endpoints

| Feature | REST Endpoint | Purpose |
|---------|---------------|---------|
| Create Invitation | `POST /organizations/:orgId/invitations` | Send invite to email |
| Accept Invitation | `POST /auth/invitations/:token/accept` | Accept and create account |

### Key Files

- Service: `src/invitations/invitations.service.ts`
- DTOs: `src/invitations/dto/`

### Invitation Flow

1. Owner/Admin creates invitation with email + role
2. System generates 32-byte random token (bcrypt hashed)
3. Email sent with unique acceptance link
4. Invitee provides: first name, last name, password
5. If user doesn't exist, new account is created
6. Membership record created with assigned role
7. JWT tokens returned for immediate login

### Invitation Properties

- **Expiration:** 7 days from creation
- **Single-use:** Token invalidated after acceptance
- **Role assignment:** Invitee gets specified role upon joining

---

## 5. Two-Factor Authentication (2FA)

**Location:** `src/two-factor/`

### Endpoints

| Feature | REST Endpoint | GraphQL Mutation |
|---------|---------------|------------------|
| Generate 2FA Setup | `POST /2fa/generate` | `generate2FA()` |
| Enable 2FA | `POST /2fa/turn-on` | `turnOn2FA(input)` |
| Disable 2FA | - | `turnOff2FA()` |
| Login with 2FA | `POST /auth/login/2fa` | `login2FA(input)` |

### Key Files

- Controller: `src/two-factor/two-factor.controller.ts`
- Resolver: `src/two-factor/two-factor.resolver.ts`
- Service: `src/two-factor/two-factor.service.ts`
- DTOs: `src/two-factor/dto/`

### 2FA Implementation

- **Type:** TOTP (Time-based One-Time Password)
- **Library:** Speakeasy
- **Code Format:** 6 digits, 30-second window
- **Setup:** QR code generated for authenticator app scanning

### 2FA Setup Flow

1. User calls generate endpoint
2. Returns QR code URL and secret
3. User scans QR with authenticator app
4. User submits 6-digit code to enable
5. 2FA is now required for all future logins

---

## 6. Role & Permission System

**Location:** `src/permissions/`

### Key Files

- Service: `src/permissions/permissions.service.ts`
- Guard: `src/auth/guards/roles.guard.ts`

### Default System Roles

| Role | Description |
|------|-------------|
| OWNER | Full organization control |
| ADMIN | Administrative access |
| MEMBER | Standard member access |

### Permission Features

- Role-based access control (RBAC)
- System-wide and organization-specific roles
- Redis-cached permissions (1-hour TTL)
- Granular permissions (e.g., `poll:create`, `qna:moderate`)

### Permission Examples

- `poll:create` - Create polls
- `qna:moderate` - Moderate Q&A sessions
- (Additional permissions defined per feature)

---

## 7. Audit Logging

**Location:** `src/audit/`

### Key Files

- Service: `src/audit/audit.service.ts`

### Logged Actions

- Member removal
- Role updates
- Organization deletion
- Account lockout
- Password changes
- Other administrative actions

### Audit Log Fields

| Field | Description |
|-------|-------------|
| action | Action type (e.g., `MEMBER_REMOVED`) |
| actingUserId | User who performed the action |
| organizationId | Affected organization |
| targetUserId | Affected user (if applicable) |
| details | Additional JSON details |
| createdAt | Timestamp |

---

## 8. Email Service

**Location:** `src/email/`

### Key Files

- Service: `src/email/email.service.ts`

### Email Templates

| Template | Purpose |
|----------|---------|
| Password Reset | Send reset link |
| Email Change Verification | Verify old email ownership |
| Email Change Finalization | Confirm new email |
| Invitation | Invite user to organization |
| Org Deletion Scheduled | Notify of pending deletion |
| Org Permanently Deleted | Confirm permanent deletion |

### Email Configuration

- **Provider:** Resend API
- **Retry Logic:** Exponential backoff (up to 10 attempts)
- **Fallback:** Legacy SMTP support available

---

## 9. Internal API

**Location:** `src/internal/`

### Key Files

- Controller: `src/internal/internal.controller.ts`

### Endpoints

| Endpoint | Guard | Purpose |
|----------|-------|---------|
| `GET /internal/users/:id` | Internal API Key | Fetch user by ID |

### Security

- Protected by `X-Internal-API-Key` header
- Used for inter-service communication only

---

## 10. Security Features

### Authentication Security

| Feature | Implementation |
|---------|----------------|
| JWT Authentication | Access + Refresh tokens |
| Token Storage | Refresh token in HTTP-only cookie |
| Account Lockout | 5 failed attempts → 15 min lockout |
| Password Hashing | bcrypt |

### API Security

| Feature | Implementation |
|---------|----------------|
| Rate Limiting | 10 req/min (strict), 100 req/min (general) |
| CSRF Protection | Token-based for GraphQL |
| Internal API | API key validation |
| Role Guard | RBAC for protected endpoints |

### Guards

| Guard | Purpose | Location |
|-------|---------|----------|
| `GqlAuthGuard` | JWT validation for GraphQL | `src/auth/guards/gql-auth.guard.ts` |
| `RefreshTokenGuard` | Refresh token validation | `src/auth/guards/refresh-token.guard.ts` |
| `RolesGuard` | Role-based access control | `src/auth/guards/roles.guard.ts` |
| `InternalApiKeyGuard` | Internal service calls | `src/auth/guards/internal-api-key.guard.ts` |
| `CsrfGuard` | CSRF protection | `src/common/csrf/csrf.guard.ts` |
| `GqlThrottlerGuard` | GraphQL rate limiting | `src/auth/guards/gql-throttler.guard.ts` |

---

## Quick Reference: All Endpoints

### Authentication (REST)
```
POST /auth/login
POST /auth/login/2fa
POST /auth/logout
POST /auth/refresh
POST /auth/password-reset-request
POST /auth/password-reset
POST /auth/invitations/:token/accept
POST /auth/token/switch
```

### Users (REST)
```
POST /users
GET  /users/me
PATCH /users/me
PUT  /users/me/password
PATCH /users/me/email
GET  /users/email-change/verify-old/:token
GET  /users/email-change/finalize/:token
```

### Organizations (REST)
```
POST   /organizations
GET    /organizations
GET    /organizations/:orgId
PUT    /organizations/:orgId
DELETE /organizations/:orgId
GET    /organizations/restore/:token
GET    /organizations/:orgId/members
DELETE /organizations/:orgId/members/:memberId
PUT    /organizations/:orgId/members/:userId/role
POST   /organizations/:orgId/invitations
```

### 2FA (REST)
```
POST /2fa/generate
POST /2fa/turn-on
```

### Internal (REST)
```
GET /internal/users/:id
```

### Health
```
GET /health
```

---

## Database Models

### Core Tables

| Table | Purpose |
|-------|---------|
| User | User accounts (organizers & attendees) |
| Organization | Tenant organizations |
| Membership | User-Org relationships with roles |
| Role | Role definitions (system & org-specific) |
| Permission | Granular permissions |
| Invitation | Pending organization invitations |
| PasswordResetToken | Password reset token tracking |
| AuditLog | Administrative action audit trail |

---

## Feature Summary

| Category | Feature Count |
|----------|--------------|
| Authentication | 8 endpoints |
| User Management | 7 endpoints |
| Organization Management | 11 endpoints |
| Invitations | 2 endpoints |
| 2FA | 4 endpoints |
| Internal API | 1 endpoint |
| **Total** | **33 endpoints** |

---

*Generated for code exploration and feature tracing purposes.*
