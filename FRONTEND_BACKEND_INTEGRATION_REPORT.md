# Frontend-Backend Integration Report

> **For:** Frontend Engineer
> **Generated:** December 2025
> **Purpose:** Complete mapping of frontend GraphQL queries/mutations to backend APIs with mismatches and integration requirements

---

## Table of Contents
1. [API Configuration](#api-configuration)
2. [Phase 1: Authentication & User Management](#phase-1-authentication--user-management)
3. [Phase 2: Organization Management](#phase-2-organization-management)
4. [Phase 3: Events & Blueprints Management](#phase-3-events--blueprints-management)
5. [Phase 4: Sessions, Speakers & Venues](#phase-4-sessions-speakers--venues)
6. [Phase 5: Registrations & Public Pages](#phase-5-registrations--public-pages)
7. [Phase 6: Real-time Features (WebSocket)](#phase-6-real-time-features-websocket)
8. [Critical Mismatches Summary](#critical-mismatches-summary)
9. [Missing Frontend Features](#missing-frontend-features)

---

## API Configuration

### Environment Variables Required
```env
NEXT_PUBLIC_API_URL=http://localhost:4000/graphql    # Apollo Gateway
NEXT_PUBLIC_REALTIME_URL=http://localhost:3002/events # WebSocket (Socket.IO)
```

### Backend Services Architecture
| Service | Port | Purpose |
|---------|------|---------|
| Apollo Gateway | 4000 | GraphQL Federation (routes to subgraphs) |
| user-and-org-service | 3001 | Auth, Users, Organizations, 2FA |
| event-lifecycle-service | 8000 | Events, Sessions, Speakers, Venues, Registrations |
| real-time-service | 3002 | WebSocket (Live Dashboard, Chat, Q&A, Polls) |

---

## Phase 1: Authentication & User Management

### 1.1 Login
| Frontend | Backend | Status |
|----------|---------|--------|
| `mutation Login($input: LoginInput!)` | `login(input: LoginInput)` | ✅ MATCH |

**Frontend expects:**
```graphql
mutation Login($input: LoginInput!) {
  login(input: $input) {
    token
    user { id, email, first_name }
    requires2FA
    userIdFor2FA
  }
}
```

**Backend provides:** ✅ All fields available

**Notes:**
- Backend also returns `onboardingToken` for users without organizations (new user flow)
- Refresh token is set as HTTP-only cookie automatically

---

### 1.2 Registration
| Frontend | Backend | Status |
|----------|---------|--------|
| `mutation RegisterUser($input: RegisterUserInput!)` | `registerUser(input: RegisterUserInput)` | ✅ MATCH |

**Frontend expects:**
```graphql
mutation RegisterUser($input: RegisterUserInput!) {
  registerUser(input: $input) {
    token
    user { id, email, first_name }
  }
}
```

**Backend provides:** ✅ All fields available

**Note:** New users without an organization will need to go through onboarding flow.

---

### 1.3 Two-Factor Authentication (2FA)

| Frontend | Backend | Status |
|----------|---------|--------|
| `mutation Login2FA($input: Login2FAInput!)` | `login2FA(input: Login2FAInput)` | ✅ MATCH |
| `mutation Generate2FA` | `generate2FA` | ✅ MATCH |
| `mutation TurnOn2FA($input: TurnOn2FAInput!)` | `turnOn2FA(input: TurnOn2FAInput)` | ✅ MATCH |
| `mutation TurnOff2FA` | `turnOff2FA` | ✅ MATCH |
| `query GetMyProfile { isTwoFactorEnabled }` | `getMyProfile` | ✅ MATCH |

**All 2FA operations are fully supported.**

---

### 1.4 Password Management

| Frontend | Backend | Status |
|----------|---------|--------|
| `mutation ChangePassword($input: ChangePasswordInput!)` | `changePassword(input: ChangePasswordInput)` | ✅ MATCH |
| `mutation PerformPasswordReset($input: PerformResetInput!)` | `performPasswordReset(input: PerformResetInput)` | ✅ MATCH |

**MISSING in Frontend:**
- `requestPasswordReset(input: RequestResetInput)` - Backend has this, frontend forgot-password page needs to call it

**Action Required:** Add `REQUEST_PASSWORD_RESET_MUTATION` to auth.graphql.ts:
```graphql
export const REQUEST_PASSWORD_RESET_MUTATION = gql`
  mutation RequestPasswordReset($input: RequestResetInput!) {
    requestPasswordReset(input: $input)
  }
`;
```

---

### 1.5 User Profile

| Frontend | Backend | Status |
|----------|---------|--------|
| `query GetMyProfile` | `getMyProfile` | ✅ MATCH |
| `mutation UpdateMyProfile($input: UpdateMyProfileInput!)` | `updateMyProfile(input: UpdateMyProfileInput)` | ✅ MATCH |

---

### 1.6 Logout

| Frontend | Backend | Status |
|----------|---------|--------|
| `mutation Logout` | `logout` | ✅ MATCH |

---

## Phase 2: Organization Management

### 2.1 Organization Queries

| Frontend | Backend | Status |
|----------|---------|--------|
| `query GetMyOrgs` | `myOrganizations` | ✅ MATCH |
| `query GetOrganization($organizationId: ID!)` | `organization(id: ID!)` | ✅ MATCH |

---

### 2.2 Organization Mutations

| Frontend | Backend | Status |
|----------|---------|--------|
| `mutation SwitchOrg($organizationId: ID!)` | `switchOrganization(organizationId: ID!)` | ✅ MATCH |
| `mutation OnboardingCreateOrganization($input)` | `onboardingCreateOrganization(input)` | ✅ MATCH |
| `mutation CreateAdditionalOrganization($input)` | `createAdditionalOrganization(input)` | ✅ MATCH |
| `mutation UpdateOrganization($input)` | `updateOrganization(input)` | ✅ MATCH |
| `mutation DeleteOrganization($input)` | `deleteOrganization(input)` | ✅ MATCH |
| `mutation RestoreOrganization($organizationId)` | `restoreOrganization(organizationId)` | ✅ MATCH |

---

### 2.3 Team Management

| Frontend | Backend | Status |
|----------|---------|--------|
| `query GetTeamData` | `organizationMembers` + `listRolesForOrg` | ✅ MATCH |
| `mutation CreateInvitation($input)` | `createInvitation(input)` | ✅ MATCH |
| `mutation UpdateMemberRole($input)` | `updateMemberRole(input)` | ✅ MATCH |
| `mutation RemoveMember($memberId)` | `removeMember(memberId)` | ✅ MATCH |

---

## Phase 3: Events & Blueprints Management

### 3.1 Event Queries

| Frontend | Backend | Status |
|----------|---------|--------|
| `query GetEventById($id: ID!)` | `event(id: ID!)` | ✅ MATCH |
| `query GetEventsByOrganization(...)` | `eventsByOrganization(...)` | ✅ MATCH |
| `query GetArchivedEventsCount($status)` | `eventsByOrganization(status)` | ✅ MATCH |
| `query GetEventHistory($eventId)` | `eventHistory(eventId)` | ✅ MATCH |

**Frontend GetEventById expects:**
```graphql
{
  id, organizationId, ownerId, name, description, status,
  startDate, endDate, isPublic, imageUrl, registrationsCount,
  venue { id, name, address }
}
```

**Backend provides:** ✅ All fields available (including nested venue via federation)

---

### 3.2 Event Mutations

| Frontend | Backend | Status |
|----------|---------|--------|
| `mutation CreateEvent($eventIn)` | `createEvent(eventIn)` | ✅ MATCH |
| `mutation UpdateEvent($id, $eventIn)` | `updateEvent(id, eventIn)` | ✅ MATCH |
| `mutation ArchiveEvent($id)` | `archiveEvent(id)` | ✅ MATCH |
| `mutation RestoreEvent($id)` | `restoreEvent(id)` | ✅ MATCH |
| `mutation PublishEvent($id)` | `publishEvent(id)` | ✅ MATCH |

---

### 3.3 Blueprints

| Frontend | Backend | Status |
|----------|---------|--------|
| `query GetOrganizationBlueprints` | `organizationBlueprints` | ✅ MATCH |
| `mutation CreateBlueprint($blueprintIn)` | `createBlueprint(blueprintIn)` | ✅ MATCH |
| `mutation InstantiateBlueprint($id, $blueprintIn)` | `instantiateBlueprint(id, blueprintIn)` | ✅ MATCH |

---

## Phase 4: Sessions, Speakers & Venues

### 4.1 Sessions

| Frontend | Backend | Status |
|----------|---------|--------|
| `query GetSessionsByEvent($eventId)` | `sessionsByEvent(eventId)` | ✅ MATCH |
| `mutation CreateSession($sessionIn)` | `createSession(sessionIn)` | ⚠️ MISMATCH |
| `mutation UpdateSession($id, $sessionIn)` | `updateSession(id, sessionIn)` | ⚠️ MISMATCH |
| `mutation ArchiveSession($id)` | `archiveSession(id)` | ✅ MATCH |

**MISMATCH - CreateSession:**

Frontend sends:
```graphql
mutation CreateSession($sessionIn: SessionCreateInput!) {
  createSession(sessionIn: $sessionIn) {
    id, title, startTime, endTime, speakers { id, name }
  }
}
```

Backend expects `SessionCreateInput`:
```python
@strawberry.input
class SessionCreateInput:
    eventId: str          # Required
    title: str            # Required
    sessionDate: str      # Required (YYYY-MM-DD format)
    startTime: str        # Required (HH:MM format, e.g., "09:00")
    endTime: str          # Required (HH:MM format, e.g., "10:00")
    speakerIds: Optional[List[str]] = None
```

**Action Required:** Ensure frontend `add-session-modal.tsx` sends:
- `sessionDate` as separate field (YYYY-MM-DD)
- `startTime` and `endTime` as HH:MM strings (not full ISO timestamps)

---

### 4.2 Speakers

| Frontend | Backend | Status |
|----------|---------|--------|
| `query GetOrganizationSpeakers` | `organizationSpeakers` | ✅ MATCH |
| `mutation CreateSpeaker($speakerIn)` | `createSpeaker(speakerIn)` | ✅ MATCH |
| `mutation UpdateSpeaker($id, $speakerIn)` | `updateSpeaker(id, speakerIn)` | ✅ MATCH |
| `mutation ArchiveSpeaker($id)` | `archiveSpeaker(id)` | ✅ MATCH |

---

### 4.3 Venues

| Frontend | Backend | Status |
|----------|---------|--------|
| `query GetOrganizationVenues` | `organizationVenues` | ✅ MATCH |
| `mutation CreateVenue($venueIn)` | `createVenue(venueIn)` | ✅ MATCH |
| `mutation UpdateVenue($id, $venueIn)` | `updateVenue(id, venueIn)` | ✅ MATCH |
| `mutation ArchiveVenue($id)` | `archiveVenue(id)` | ✅ MATCH |

---

## Phase 5: Registrations & Public Pages

### 5.1 Registrations (Admin View)

| Frontend | Backend | Status |
|----------|---------|--------|
| `query GetRegistrationsByEvent($eventId)` | `registrationsByEvent(eventId)` | ✅ MATCH |
| `query GetAttendeesByEvent($eventId)` | Same as above | ✅ MATCH |

**Frontend expects:**
```graphql
{
  id, status, ticketCode, checkedInAt, guestEmail, guestName,
  user { id, first_name, last_name, email }
}
```

**Backend provides:** ✅ All fields (user resolved via GraphQL Federation)

---

### 5.2 Public Event Registration

| Frontend | Backend | Status |
|----------|---------|--------|
| `mutation CreateRegistration($registrationIn, $eventId)` | `createRegistration(registrationIn, eventId)` | ⚠️ MISMATCH |

**MISMATCH - RegistrationCreateInput:**

Frontend likely sends (based on typical patterns):
```typescript
{
  userId?: string;     // For logged-in users
  email?: string;      // For guest registration
  firstName?: string;  // For guest registration
  lastName?: string;   // For guest registration
}
```

Backend expects (note the field names):
```python
@strawberry.input
class RegistrationCreateInput:
    user_id: Optional[str] = None      # snake_case!
    email: Optional[str] = None
    first_name: Optional[str] = None   # snake_case!
    last_name: Optional[str] = None    # snake_case!
```

**Action Required:** Verify field names in `registration-model.tsx`. GraphQL typically converts to camelCase, so this might work automatically, but verify.

---

### 5.3 Public Event Details

| Frontend | Backend | Status |
|----------|---------|--------|
| `query GetPublicEventDetails($eventId)` | `event(id)` + `publicSessionsByEvent(eventId)` | ✅ MATCH |

**Note:** This query fetches both event details AND sessions in a single request. Backend supports this.

---

## Phase 6: Real-time Features (WebSocket)

### 6.1 Connection Setup

**Frontend (use-live-dashboard.ts):**
```typescript
const realtimeUrl = process.env.NEXT_PUBLIC_REALTIME_URL || "http://localhost:3002/events";

const newSocket = io(realtimeUrl, {
  query: { eventId },
  auth: { token },
});
```

**Backend expects:**
- Namespace: `/events`
- Query parameter: `eventId` (required for dashboard)
- Auth: `token` in auth object (JWT Bearer token from auth store)

✅ **This matches correctly.**

---

### 6.2 Dashboard Events

| Frontend Event | Backend Event | Status |
|----------------|---------------|--------|
| `dashboard.join` (emit) | `@SubscribeMessage('dashboard.join')` | ✅ MATCH |
| `dashboard.update` (listen) | `dashboard.update` (broadcast) | ✅ MATCH |
| `connectionAcknowledged` (listen) | `connectionAcknowledged` (emit) | ✅ MATCH |
| `systemError` (listen) | `systemError` (emit) | ✅ MATCH |

---

### 6.3 Dashboard Data Structure

**Frontend expects (LiveDashboardData):**
```typescript
interface LiveDashboardData {
  totalMessages: number;
  totalVotes: number;
  totalQuestions: number;
  totalUpvotes: number;
  totalReactions: number;
  liveCheckInFeed: { id: string; name: string }[];
}
```

**Backend provides (DashboardData):**
```typescript
interface DashboardData {
  totalMessages: number;
  totalVotes: number;
  totalQuestions: number;
  totalUpvotes: number;
  totalReactions: number;
  liveCheckInFeed: CheckInFeedItem[];  // { id: string; name: string }
}
```

✅ **Perfect match!**

---

### 6.4 Required Permission

To join the dashboard, the user must have permission: `dashboard:read:live`

**Frontend must ensure:**
- User has this permission in their JWT token
- This is typically assigned to ADMIN or OWNER roles

---

### 6.5 Missing Real-time Features in Frontend

The backend supports these additional real-time features that are **NOT implemented in frontend:**

| Feature | Backend Support | Frontend Status |
|---------|-----------------|-----------------|
| Chat (Messages) | ✅ Full implementation | ❌ NOT IMPLEMENTED |
| Q&A (Questions) | ✅ Full implementation | ❌ NOT IMPLEMENTED |
| Polls (Voting) | ✅ Full implementation | ❌ NOT IMPLEMENTED |
| Capacity Updates | ✅ Broadcast events | ❌ NOT IMPLEMENTED |

**Backend Events Available:**
- `chat.sendMessage` - Send a chat message
- `chat.message` - Receive new messages
- `qna.askQuestion` - Submit a question
- `qna.upvoteQuestion` - Upvote a question
- `polls.castVote` - Cast a vote on a poll
- `dashboard.capacity.updated` - Resource capacity changes

---

## Critical Mismatches Summary

### High Priority (Will cause errors)

| Issue | Location | Fix Required |
|-------|----------|--------------|
| Session date/time format | `add-session-modal.tsx` | Send `sessionDate` (YYYY-MM-DD) and times as HH:MM |
| Missing password reset request | `forgot-password/page.tsx` | Add `REQUEST_PASSWORD_RESET_MUTATION` |

### Medium Priority (May cause issues)

| Issue | Location | Fix Required |
|-------|----------|--------------|
| Registration field names | `registration-model.tsx` | Verify snake_case conversion works |

---

## Missing Frontend Features

### Must Implement

1. **Password Reset Request**
   - File: `src/app/auth/forgot-password/page.tsx`
   - Add mutation: `requestPasswordReset(input: { email: string })`

### Should Implement (Backend Ready)

1. **Real-time Chat**
   - Backend service: `real-time-service/src/comm/chat/`
   - Events: `chat.sendMessage`, `chat.message`, `chat.typing`

2. **Real-time Q&A**
   - Backend service: `real-time-service/src/comm/qna/`
   - Events: `qna.askQuestion`, `qna.upvoteQuestion`, `qna.question`

3. **Real-time Polls**
   - Backend service: `real-time-service/src/comm/polls/`
   - Events: `polls.castVote`, `polls.results`

4. **Event Statistics Dashboard**
   - Backend query: `eventStats` returns `{ totalEvents, upcomingEvents, upcomingRegistrations }`
   - Could enhance dashboard home page

5. **Presentation Upload/View**
   - Files exist: `upload-presentation-modal.tsx`, `presentation-viewer.tsx`
   - Backend: Uses MinIO/S3 for file storage
   - Need to verify upload endpoint integration

---

## Environment Setup Checklist

```bash
# Frontend .env.local
NEXT_PUBLIC_API_URL=http://localhost:4000/graphql
NEXT_PUBLIC_REALTIME_URL=http://localhost:3002/events

# For production
NEXT_PUBLIC_API_URL=https://api.yourdomain.com/graphql
NEXT_PUBLIC_REALTIME_URL=https://realtime.yourdomain.com/events
```

---

## Quick Reference: GraphQL Input Types

### Auth Inputs (user-and-org-service)
```graphql
input LoginInput {
  email: String!
  password: String!
}

input RegisterUserInput {
  email: String!
  password: String!
  first_name: String!
  last_name: String!
}

input Login2FAInput {
  userId: ID!
  code: String!
}

input TurnOn2FAInput {
  code: String!
}

input ChangePasswordInput {
  currentPassword: String!
  newPassword: String!
}

input RequestResetInput {
  email: String!
}

input PerformResetInput {
  resetToken: String!
  newPassword: String!
}
```

### Event Inputs (event-lifecycle-service)
```graphql
input EventCreateInput {
  name: String!
  description: String
  startDate: String!  # ISO format
  endDate: String!    # ISO format
  venueId: String
  imageUrl: String
}

input SessionCreateInput {
  eventId: String!
  title: String!
  sessionDate: String!    # YYYY-MM-DD
  startTime: String!      # HH:MM
  endTime: String!        # HH:MM
  speakerIds: [String]
}

input RegistrationCreateInput {
  user_id: String      # For logged-in users
  email: String        # For guest
  first_name: String   # For guest
  last_name: String    # For guest
}
```

---

**Report End**
