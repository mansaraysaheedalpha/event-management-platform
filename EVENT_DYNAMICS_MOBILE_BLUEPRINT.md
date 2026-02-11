# Event Dynamics Mobile - Agent Execution Blueprint

> **Repo name:** `event-dynamics-mobile`
> **Stack:** React Native (Expo) + TypeScript
> **Web codebase reference:** `../globalconnect/` (the existing Next.js web app)
> **Backend:** No changes needed — the mobile app is a new client consuming the same APIs

---

## How to Use This Document

This document is divided into **13 phases**. Each phase is a **self-contained agent prompt** — copy the entire phase block and give it to an AI coding agent. The agent will:

1. Research the referenced web codebase directories to understand patterns
2. Build the mobile equivalent following enterprise best practices
3. Produce production-grade, type-safe code

**Rules for agents:**
- Phases are ordered by dependency. Phase 0 must be done first. After that, Phases 1-3 are sequential. Phases 4-10 can be parallelized across agents once Phase 3 is complete. Phases 11-12 are final polish.
- Each agent must read and study the web codebase files referenced in its prompt before writing any code.
- All code must be TypeScript with strict mode. No `any` types. No shortcuts.
- Follow the existing web app's naming conventions, file organization patterns, and architectural decisions.

---

## Phase 0 — Project Scaffold & Architecture Foundation

```prompt
You are a senior React Native engineer setting up a greenfield enterprise mobile application. This mobile app is the companion to an existing Next.js web application located at `../globalconnect/`.

## Your Task
Initialize a new Expo (managed workflow) React Native project with TypeScript in the `event-dynamics-mobile/` directory. Set up the foundational architecture that all subsequent feature work will build upon.

## Before Writing Any Code — Research First
Read and study these files from the web codebase to understand the existing patterns:

1. `../globalconnect/package.json` — understand the full dependency list and what the web app uses
2. `../globalconnect/src/store/auth.store.ts` — understand the Zustand store pattern (persisted state, interfaces, helper exports)
3. `../globalconnect/src/lib/apollo-provider.tsx` — understand the Apollo Client setup (httpLink, authLink, errorLink chain, token refresh flow, error handling patterns)
4. `../globalconnect/src/lib/socket.ts` — understand the Socket.io client pattern (singleton, room management, reconnection config)
5. `../globalconnect/src/graphql/` directory — understand how GraphQL queries are organized (one file per domain: events, attendee, payments, etc.)
6. `../globalconnect/src/components/ui/` directory — list all the reusable UI components to understand the design system scope

## What to Set Up

### 1. Expo Project Initialization
- Use the latest Expo SDK with TypeScript template
- Configure `app.json` / `app.config.ts` with proper app name ("Event Dynamics"), slug, scheme for deep linking, and placeholder icons
- Set up path aliases (`@/` mapping to `src/`) matching the web app's convention

### 2. Navigation Architecture (React Navigation)
Set up the navigation skeleton mirroring the web app's route groups. The web app has these route groups — study `../globalconnect/src/app/` directory structure:
- `(public)` — unauthenticated screens (landing, event browsing, auth)
- `(attendee)` — authenticated attendee experience
- `(platform)` — organizer/admin dashboard
- `(sponsor)` — sponsor portal

Create a navigation structure with:
- A root navigator that switches between Auth and Main stacks
- A bottom tab navigator for the main authenticated experience (Events, My Schedule, Networking, Notifications, Profile)
- Nested stack navigators within each tab for drill-down screens
- Type-safe navigation using `@react-navigation/native-stack` with full TypeScript param types for every route

### 3. Apollo Client Setup
Port the Apollo Client configuration from `../globalconnect/src/lib/apollo-provider.tsx`:
- Same httpLink pointing to the same GraphQL endpoint (use environment variables)
- Same authLink pattern that reads token from Zustand and injects Bearer header
- Same errorLink pattern that catches 401s and triggers token refresh with retry
- Same `InMemoryCache` with same `errorPolicy: "all"` defaults
- Replace `localStorage` persistence with `expo-secure-store` for tokens

### 4. Zustand Auth Store
Port `../globalconnect/src/store/auth.store.ts` to mobile:
- Same `AuthState` interface (token, user, orgId, onboardingToken, isRefreshing)
- Same `setAuth`, `logout`, `updateUser`, `isTokenExpired` logic
- Replace `localStorage` with `expo-secure-store` for persistence (use a custom Zustand storage adapter)
- Remove the cookie sync logic (not needed in mobile)
- Keep the `getAuthState()` and `isAuthenticated()` helper exports

### 5. Socket.io Client
Port `../globalconnect/src/lib/socket.ts`:
- Same singleton pattern with `initializeSocket()`, `getSocket()`, `disconnectSocket()`
- Same room management functions (`joinUserRoom`, `joinSessionWaitlistRoom`, etc.)
- Same reconnection config (1s delay, 5s max, 5 attempts)
- Environment variable for socket URL

### 6. Environment Configuration
- Set up `expo-constants` for environment variables
- Create `.env.example` with all required variables (reference the web app's `NEXT_PUBLIC_*` vars):
  - `API_URL` (GraphQL endpoint)
  - `SOCKET_URL` (Socket.io server)
  - `REALTIME_URL` (real-time service)
  - `STRIPE_PUBLISHABLE_KEY`
  - `AGENT_SERVICE_URL`

### 7. GraphQL Query Files
Copy over the GraphQL query/mutation definitions from `../globalconnect/src/graphql/` directory. These are plain GraphQL strings wrapped in `gql` tags — they are framework-agnostic and can be reused directly:
- `events.graphql.ts`
- `attendee.graphql.ts`
- `monetization.graphql.ts`
- `payments.graphql.ts`
- `speakers.graphql.ts`
- `dashboard.graphql.ts`
- `registrations.graphql.ts`
- `user.graphql.ts`
- `organization.graphql.ts`
- `public.graphql.ts`
- `security.graphql.ts`
- `blueprints.graphql.ts`
- `venues.graphql.ts`
- `queries.ts` (shared/common queries)

Also copy the `../globalconnect/src/components/features/Auth/auth.graphql.ts` file (login, register, refresh token mutations).

### 8. Base UI Theme
- Set up a theme system (colors, typography, spacing) that mirrors the web app's design tokens
- Read `../globalconnect/tailwind.config.ts` and `../globalconnect/src/app/globals.css` to extract the HSL color variables and convert them to a React Native compatible theme object
- Create a `ThemeProvider` context
- Create these foundational UI primitives: `Text`, `Button`, `Card`, `Input`, `Badge`, `Avatar`, `Separator`, `LoadingSpinner`

### 9. Project Structure
```
event-dynamics-mobile/
├── src/
│   ├── app/                    # Entry point
│   ├── navigation/             # All navigators
│   │   ├── RootNavigator.tsx
│   │   ├── AuthStack.tsx
│   │   ├── MainTabs.tsx
│   │   ├── AttendeeStack.tsx
│   │   ├── OrganizerStack.tsx
│   │   └── types.ts            # Navigation param types
│   ├── screens/                # Screen components (grouped by domain)
│   │   ├── auth/
│   │   ├── attendee/
│   │   ├── organizer/
│   │   ├── sponsor/
│   │   └── public/
│   ├── components/
│   │   ├── ui/                 # Design system primitives
│   │   └── features/           # Feature-specific components
│   ├── hooks/                  # Custom hooks (ported from web)
│   ├── store/                  # Zustand stores
│   ├── graphql/                # GraphQL queries (copied from web)
│   ├── lib/                    # Utilities (apollo, socket, etc.)
│   ├── theme/                  # Theme tokens and provider
│   └── types/                  # Shared TypeScript types
├── assets/                     # Images, fonts
├── app.config.ts
└── package.json
```

## Quality Requirements
- Every file must have proper TypeScript types — no `any`
- Navigation must be fully type-safe (use `NativeStackScreenProps` generics)
- Zustand stores must use the same interface contracts as the web app for consistency
- Apollo Client must have identical error handling and token refresh behavior as the web app
- Code must be formatted consistently (set up Prettier + ESLint with the same rules as the web app)
```

---

## Phase 1 — Authentication Screens

```prompt
You are building the authentication flow for the Event Dynamics mobile app (React Native/Expo). The app scaffold, navigation, Apollo Client, and Zustand auth store are already set up from Phase 0.

## Before Writing Any Code — Research First
Study these files from the web codebase to understand every detail of the auth flow:

1. `../globalconnect/src/app/auth/login/page.tsx` — the login page UI and logic
2. `../globalconnect/src/app/auth/register/page.tsx` — the registration page UI and logic
3. `../globalconnect/src/app/auth/forgot-password/page.tsx` — password reset request flow
4. `../globalconnect/src/app/auth/reset-password/page.tsx` — password reset completion flow
5. `../globalconnect/src/components/features/Auth/auth.graphql.ts` — ALL auth-related GraphQL mutations (login, register, refreshToken, forgotPassword, resetPassword, verifyTwoFactor, etc.)
6. `../globalconnect/src/store/auth.store.ts` — how auth state is managed after successful login
7. `../globalconnect/src/lib/apollo-provider.tsx` — the token refresh mechanism (understand the `getNewToken` flow and how it handles concurrent refreshes)
8. `../globalconnect/src/lib/token-refresh.ts` — if it exists, read it to understand `refreshToken`, `tokenNeedsRefresh`, `isTokenExpired`, `initializeTokenRefresh`, `cancelScheduledRefresh`
9. `../globalconnect/src/app/onboarding/create-organization/page.tsx` — the post-registration onboarding flow

## What to Build

### Screens
1. **Login Screen** — Email + password form, "Forgot password?" link, "Create account" link, social login buttons if the web app supports them
2. **Register Screen** — First name, last name, email, password form with validation matching the web app's rules
3. **Forgot Password Screen** — Email input, sends reset link
4. **Reset Password Screen** — New password + confirm, deep link support for reset tokens
5. **Two-Factor Auth Screen** — If the web app has 2FA verification (check `auth.graphql.ts` for `verifyTwoFactor` mutation), build a code input screen
6. **Onboarding Screen** — Post-registration organization creation flow (study the web app's onboarding page)

### For Each Screen
- Use `react-hook-form` with `zod` validation schemas — match the same validation rules used in the web app
- Call the same GraphQL mutations the web app uses (from `auth.graphql.ts`)
- Handle all error states (network errors, invalid credentials, account not found, etc.) with user-friendly messages
- After successful login: call `useAuthStore.getState().setAuth(token, user)`, then navigate to the main app
- After successful register: handle the onboarding token flow if the web app uses one (check how `onboardingToken` is used)
- Implement background token refresh using the same logic as the web app's `initializeTokenRefresh`

### Mobile-Specific Additions
- Biometric authentication option (Face ID / fingerprint) using `expo-local-authentication` for returning users
- Secure token storage using `expo-secure-store` (this should already be wired up from Phase 0's Zustand persistence adapter)
- Keyboard-avoiding views for all form screens
- Proper loading states and disabled button states during mutations

### Navigation Integration
- Wire up the AuthStack navigator: Login -> Register -> ForgotPassword -> ResetPassword -> TwoFactor -> Onboarding
- After successful auth, the RootNavigator should detect the token in Zustand and switch to the Main tab navigator
- Handle deep links for password reset (`globalconnect://reset-password?token=xxx`)

## Quality Requirements
- Form validation must be identical to the web app — study the web app's Zod schemas carefully
- Error messages must be user-friendly (never show raw GraphQL errors to the user)
- The token refresh mechanism must be robust — it should handle race conditions, concurrent requests, and network failures exactly like the web app does
- All screens must handle keyboard properly on both iOS and Android
- Loading and error states must be visually polished
```

---

## Phase 2 — Event Discovery & Public Screens

```prompt
You are building the event discovery and public-facing screens for the Event Dynamics mobile app. Auth is already working from Phase 1. The app uses Apollo Client for GraphQL and React Navigation.

## Before Writing Any Code — Research First
Study these files from the web codebase:

1. `../globalconnect/src/app/(public)/events/page.tsx` — event listing/browsing page
2. `../globalconnect/src/app/(public)/events/[eventId]/page.tsx` — public event detail page
3. `../globalconnect/src/app/(public)/events/[eventId]/checkout/page.tsx` — ticket checkout page
4. `../globalconnect/src/app/(public)/events/[eventId]/checkout/confirmation/page.tsx` — checkout confirmation
5. `../globalconnect/src/graphql/events.graphql.ts` — all event-related queries (getEvents, getEventById, etc.)
6. `../globalconnect/src/graphql/public.graphql.ts` — public queries available without auth
7. `../globalconnect/src/graphql/monetization.graphql.ts` — ticket/pricing queries
8. `../globalconnect/src/app/(public)/page.tsx` — the landing/home page (understand what's shown to unauthenticated users)
9. `../globalconnect/src/app/(public)/join/[sessionId]/page.tsx` — direct session join flow

## What to Build

### Screens
1. **Event Browse/Search Screen** — List of upcoming events with search, filters (date, category, location, price), and pull-to-refresh. Study how the web app queries and filters events.
2. **Event Detail Screen** — Full event information: title, description, date/time, venue, speakers, schedule/agenda, ticket tiers. This is a scrollable detail screen with sections.
3. **Ticket Selection Screen** — Display available ticket tiers with pricing (study the monetization GraphQL queries). Multi-currency support matching the web app (USD, EUR, GBP, CAD, AUD, NGN, GHS, KES).
4. **Session Schedule Screen** — Event agenda showing all sessions organized by time/day. Tappable to view session details.

### Patterns to Follow
- Use `FlatList` or `FlashList` for event lists (virtualized, performant)
- Implement pull-to-refresh on all list screens
- Use skeleton loading placeholders (not spinners) for content loading
- Images should use `expo-image` for caching and performance
- Event cards should match the visual hierarchy of the web app's event cards

### Mobile-Specific UX
- Add a "share event" action using `expo-sharing` (native share sheet)
- Swipe gestures for navigation where appropriate
- Haptic feedback on key interactions using `expo-haptics`
- Offline support: cache recently viewed events for offline reading

## Quality Requirements
- Event list must be smooth at 60fps even with hundreds of events — use proper list virtualization
- Image loading must be graceful (placeholder -> load -> display)
- Search must be debounced (300ms) to avoid excessive API calls — the web app has a `use-debounce.ts` hook, study it
- All currency formatting must match the web app exactly
- Deep linking: `globalconnect://events/{eventId}` should open the event detail screen
```

---

## Phase 3 — Attendee Event Experience (Core Hub)

```prompt
You are building the core attendee event experience — the main screen an attendee sees after joining/registering for an event. This is the most complex screen in the app.

## Before Writing Any Code — Research First
Study these files carefully — this is the heart of the attendee experience:

1. `../globalconnect/src/app/(attendee)/attendee/events/[eventId]/page.tsx` — THE main event hub page (this is ~1,663 lines, study it thoroughly)
2. `../globalconnect/src/app/(attendee)/attendee/page.tsx` — attendee dashboard/home (list of registered events)
3. `../globalconnect/src/app/(attendee)/attendee/events/[eventId]/attendees/page.tsx` — attendee list for an event
4. `../globalconnect/src/app/(attendee)/attendee/events/[eventId]/attendees/[userId]/page.tsx` — individual attendee profile
5. `../globalconnect/src/app/(attendee)/attendee/events/[eventId]/expo/page.tsx` — expo/booth browsing
6. `../globalconnect/src/app/(attendee)/attendee/events/[eventId]/networking/page.tsx` — networking features
7. `../globalconnect/src/app/(attendee)/attendee/settings/page.tsx` — user settings
8. `../globalconnect/src/app/(attendee)/attendee/tickets/page.tsx` — user's tickets
9. `../globalconnect/src/app/(attendee)/attendee/notifications/page.tsx` — notifications center
10. `../globalconnect/src/app/(attendee)/attendee/connections/page.tsx` — user's connections
11. `../globalconnect/src/app/(attendee)/attendee/my-offers/page.tsx` — user's offers
12. `../globalconnect/src/graphql/attendee.graphql.ts` — all attendee-specific queries and mutations
13. `../globalconnect/src/graphql/registrations.graphql.ts` — registration queries

## What to Build

### Screens
1. **Attendee Home** — List of events the user is registered for. Each card shows event name, date, status. Tapping navigates to the event hub.
2. **Event Hub** — The main experience screen for a specific event. Study the web app's event hub page carefully. On mobile, this should be organized as:
   - A top section showing the current/next live session with a prominent "Join" button
   - Tabs or a scrollable section navigator for: Schedule, Speakers, Attendees, Expo, Networking
   - A floating action button for quick actions (join session, scan QR, etc.)
3. **Session Detail** — When tapping a session from the schedule, show full details: title, description, speakers, time, and a "Join Session" button
4. **Attendee List** — Searchable list of fellow attendees with profile cards
5. **Attendee Profile** — Profile detail screen with connection/follow actions
6. **My Tickets** — User's purchased tickets with QR codes for check-in
7. **My Connections** — List of people the user has connected with at events
8. **My Offers** — Dynamic offers/deals available to the user
9. **Settings** — User profile editing, notification preferences, app preferences
10. **Notifications** — Notification feed (study how the web app's notification page works)

### Key Patterns to Study
- How the web app fetches and displays the current live session
- How session joining works (the flow from tapping "Join" to entering the session)
- How attendee connections are created and managed
- How the notification system works

### Mobile-Specific UX
- Bottom tab navigation: Home, Schedule, Networking, Notifications, Profile
- Pull-to-refresh on all data screens
- QR code scanner for check-in using `expo-camera` or `expo-barcode-scanner`
- QR code display for the user's own ticket using a QR generation library
- Native calendar integration — "Add to Calendar" using `expo-calendar`
- Swipe actions on list items where appropriate (e.g., swipe to connect, swipe to dismiss notification)

## Quality Requirements
- The Event Hub screen is the most important screen in the app — it must be fast, intuitive, and polished
- Navigation between sub-sections must feel fluid and native
- All list screens must use proper virtualization for performance
- Loading states should use skeleton screens, not spinners
- Error states should have clear retry actions
- The screen must handle events with 100+ sessions and 1000+ attendees without performance degradation
```

---

## Phase 4 — Real-Time Session Features (Chat, Q&A, Polls, Reactions)

```prompt
You are building the real-time interactive session features for the Event Dynamics mobile app. These features run during live event sessions and are the core engagement tools.

## Before Writing Any Code — Research First
Study these files from the web codebase — they contain the complete implementation of each feature:

### Socket Architecture
1. `../globalconnect/src/context/SessionSocketContext.tsx` — THE critical file. This is the shared WebSocket context that all session features connect through. Study the namespace (`/events`), query params (eventId, sessionId), event listeners, and how it manages connection state. Every session feature hooks into this context.
2. `../globalconnect/src/lib/socket.ts` — the general-purpose socket (separate from session socket)

### Chat
3. `../globalconnect/src/hooks/use-session-chat.ts` — complete chat hook with message sending, receiving, history loading, pinning, and moderation
4. `../globalconnect/src/components/features/chat/` — all chat UI components (message list, input, pinned messages, etc.)

### Q&A
5. `../globalconnect/src/hooks/use-session-qa.ts` — Q&A hook with question submission, upvoting, answering, and moderation
6. `../globalconnect/src/components/features/qa/` — if this directory exists, study the Q&A UI components

### Polls
7. `../globalconnect/src/hooks/use-session-polls.ts` — polls hook with poll creation, voting, and real-time results
8. `../globalconnect/src/components/features/polls/` — if this directory exists, study poll UI components

### Reactions
9. `../globalconnect/src/hooks/use-session-reactions.ts` — emoji reactions hook with real-time floating reactions
10. `../globalconnect/src/components/features/floating-reactions.tsx` — the floating emoji animation component
11. `../globalconnect/src/components/features/reaction-bar.tsx` — the reaction selection bar

## What to Build

### 1. Session Socket Provider (Mobile)
Port the `SessionSocketContext.tsx` to React Native:
- Same namespace, same query params, same event listeners
- Same connection lifecycle management (connect on session enter, disconnect on leave)
- Same reconnection handling
- Wrap the session screen in this provider

### 2. Live Chat
- Scrollable message list (inverted FlatList for chat — newest at bottom)
- Text input with send button
- Message bubbles with sender name, avatar, timestamp
- Pinned message banner at top
- Auto-scroll to newest messages
- Chat enable/disable state (organizer can turn off chat)
- Keyboard-avoiding behavior that pushes the chat input above the keyboard

### 3. Q&A
- Question submission form
- Sortable question list (by upvotes, by time)
- Upvote button with count
- Answered/unanswered filter
- Real-time new question appearance
- Q&A enable/disable state

### 4. Polls
- Active poll display with options
- Vote selection (single or multi depending on poll config)
- Real-time vote count / percentage bar animation
- Poll results view after voting
- Poll enable/disable state

### 5. Reactions
- Floating emoji reactions that animate upward and fade out (port the web app's floating-reactions component logic to `react-native-reanimated`)
- Reaction bar with emoji options at the bottom of the session view
- Haptic feedback on reaction tap
- Throttle reactions to prevent spam (study how the web app throttles)

### 6. Session View Container
- A tabbed or swipeable container that organizes Chat, Q&A, and Polls as tabs within the session view
- The reaction bar floats above the tab content
- A header showing session title, speaker(s), and live status

## Architecture Notes
- ALL real-time features must use the shared SessionSocket — do NOT create separate socket connections per feature
- Each feature should be a self-contained hook + component pair, just like the web app
- Hooks must handle: initial data loading, real-time event subscription, optimistic updates, reconnection data sync
- Every socket event handler must be idempotent (handle duplicate events gracefully)

## Quality Requirements
- Chat must feel instant — use optimistic updates (show message before server confirms)
- Reaction animations must be smooth 60fps using `react-native-reanimated` (NOT Animated API)
- Polls must update in real-time without flicker
- All features must gracefully handle socket disconnection and reconnection
- Memory management: properly clean up socket listeners on unmount
- Test with rapid interactions (fast typing, rapid reactions) to ensure no race conditions
```

---

## Phase 5 — Live Video Streaming

```prompt
You are building the live video streaming experience for the Event Dynamics mobile app. The web app uses Daily.co for video — the mobile app will use the React Native Daily.co SDK.

## Before Writing Any Code — Research First
Study these files from the web codebase:

1. `../globalconnect/src/components/features/video/` — ALL files in this directory. Understand the video player components, controls, and how Daily.co is integrated
2. `../globalconnect/src/hooks/useVirtualStage.ts` — the virtual stage hook (if it manages Daily.co call state)
3. `../globalconnect/src/components/features/breakout/` — ALL files. Breakout rooms involve video calls with multiple participants
4. `../globalconnect/src/app/(attendee)/attendee/events/[eventId]/sessions/[sessionId]/breakout-rooms/[roomId]/page.tsx` — breakout room page
5. `../globalconnect/src/app/(platform)/dashboard/events/[eventId]/sessions/[sessionId]/green-room/page.tsx` — green room (pre-session speaker staging area)
6. `../globalconnect/src/app/(platform)/dashboard/events/[eventId]/producer/page.tsx` — producer controls
7. `../globalconnect/src/components/features/subtitles/` — live subtitle rendering
8. `../globalconnect/src/hooks/use-live-subtitles.ts` — subtitle hook

## What to Build

### 1. Daily.co React Native Integration
- Install `@daily-co/react-native-daily-js` and configure native dependencies
- Create a `DailyProvider` wrapper for the mobile app
- Handle camera and microphone permissions using `expo-camera` and `expo-av`

### 2. Session Video Player (Attendee View)
- Full-screen landscape video for watching live streams
- Picture-in-picture support when navigating away (if platform supports it)
- Audio-only mode for low bandwidth
- Quality selector (auto, high, medium, low)
- Mute/unmute button
- Volume control
- Fullscreen toggle
- Connection quality indicator

### 3. Breakout Room Video
- Multi-participant video grid (study the web app's breakout room layout)
- Self-view in corner
- Mute/unmute audio toggle
- Camera on/off toggle
- Participant list overlay
- Screen sharing viewing (receiving only — mobile attendees view shared screens)
- Leave room button

### 4. Live Subtitles
Port the subtitle feature from the web app:
- Study `use-live-subtitles.ts` to understand how subtitles are received (likely via socket or API)
- Overlay translucent subtitle text at the bottom of the video view
- Subtitle language selection if multi-language is supported
- Toggle subtitles on/off

### 5. Mini Player
- When the user navigates away from the session screen while video is playing, show a floating mini player (small video thumbnail with play/pause)
- Tapping the mini player returns to the full session view
- Swipe to dismiss the mini player

### Mobile-Specific Considerations
- Handle app backgrounding (pause/resume video appropriately)
- Handle phone calls interrupting the stream
- Handle network transitions (WiFi -> cellular) gracefully
- Battery optimization: reduce frame rate when battery is low
- Orientation: support both portrait and landscape for video viewing

## Quality Requirements
- Video playback must be smooth and reliable
- Audio/video sync must be correct
- Graceful handling of poor network conditions (buffering indicator, auto quality reduction)
- Camera and microphone permissions must be requested with clear explanations before prompting
- The video grid in breakout rooms must scale properly (1, 2, 4, 6+ participants)
- Memory management: properly release Daily.co resources when leaving a session
```

---

## Phase 6 — Networking & Connections

```prompt
You are building the networking and connections features for the Event Dynamics mobile app. These features let attendees discover, connect with, and follow up with other attendees.

## Before Writing Any Code — Research First
Study these files from the web codebase:

1. `../globalconnect/src/hooks/use-connections.ts` — how connections are created, fetched, and managed
2. `../globalconnect/src/hooks/use-event-connections.ts` — event-specific connection logic
3. `../globalconnect/src/hooks/use-networking-stats.ts` — networking statistics
4. `../globalconnect/src/hooks/use-follow-up.ts` — follow-up actions after connecting
5. `../globalconnect/src/hooks/use-proximity.ts` — proximity-based networking (geolocation)
6. `../globalconnect/src/hooks/use-direct-messages.ts` — direct messaging between users
7. `../globalconnect/src/hooks/use-recommendations.ts` — AI-powered attendee recommendations
8. `../globalconnect/src/components/features/networking/` — ALL networking UI components
9. `../globalconnect/src/components/features/connections/` — ALL connection UI components
10. `../globalconnect/src/components/features/dm/` — ALL direct message components
11. `../globalconnect/src/components/features/proximity/` — proximity UI components
12. `../globalconnect/src/app/(attendee)/attendee/events/[eventId]/networking/page.tsx` — the networking page
13. `../globalconnect/src/app/(attendee)/attendee/connections/page.tsx` — the connections page

## What to Build

### 1. Attendee Discovery
- Browsable list of event attendees with search and filters
- Attendee profile cards showing name, title, company, bio, interests
- "Connect" button on each card
- AI-powered "Recommended for You" section at the top (study the recommendations hook)

### 2. Connection Management
- Send connection request
- Accept/decline incoming requests
- View pending sent/received requests
- Connection list with status indicators
- Remove connection

### 3. Direct Messages
- Conversation list showing all active DMs
- Chat screen for individual conversations
- Real-time message delivery (study how the DM hook uses sockets or polling)
- Unread message badges
- Push notification integration for new messages

### 4. Proximity Networking (Mobile Advantage)
This is where mobile excels over web. Study `use-proximity.ts` carefully:
- Use `expo-location` for background location tracking
- Show nearby attendees at the event venue
- "Bump to connect" — if two users are physically close and both opt in, suggest a connection
- Privacy controls: opt in/out of proximity features
- Battery-efficient location tracking (significant location changes, not continuous GPS)

### 5. Follow-Up Actions
- After connecting, suggest follow-up actions (study `use-follow-up.ts`)
- Schedule a follow-up meeting
- Share contact information
- Add notes to a connection

### Mobile-Specific UX
- Contact card integration — add connections to phone contacts using `expo-contacts`
- Share profile via native share sheet or QR code
- LinkedIn profile linking (study `use-linkedin.ts` hook)
- Swipe gestures on connection cards (swipe right to accept, left to decline)

## Quality Requirements
- The attendee list must handle 1000+ attendees smoothly (virtualized list)
- DM delivery must feel instant — use optimistic updates
- Proximity features must be battery-efficient — no constant GPS polling
- Location permissions must be requested with clear explanations
- All networking actions must have proper loading, success, and error states
- Privacy must be respected — users must be able to opt out of all proximity/discovery features
```

---

## Phase 7 — Payments & Ticketing

```prompt
You are building the payment and ticketing system for the Event Dynamics mobile app using Stripe's React Native SDK.

## Before Writing Any Code — Research First
Study these files from the web codebase:

1. `../globalconnect/src/hooks/use-checkout.ts` — the checkout hook (complete purchase flow logic)
2. `../globalconnect/src/hooks/use-monetization.ts` — monetization/pricing logic
3. `../globalconnect/src/hooks/use-offer-checkout.ts` — special offer checkout flow
4. `../globalconnect/src/hooks/use-offer-tracking.ts` — offer tracking
5. `../globalconnect/src/hooks/use-ticket-metrics.ts` — ticket-related data
6. `../globalconnect/src/hooks/use-ticket-validation.ts` — ticket validation logic
7. `../globalconnect/src/components/features/checkout/` — ALL checkout UI components
8. `../globalconnect/src/components/features/offers/` — offer components
9. `../globalconnect/src/graphql/monetization.graphql.ts` — pricing/ticket GraphQL queries
10. `../globalconnect/src/graphql/payments.graphql.ts` — payment-related queries/mutations
11. `../globalconnect/src/app/(public)/events/[eventId]/checkout/page.tsx` — checkout page
12. `../globalconnect/src/app/(public)/events/[eventId]/checkout/confirmation/page.tsx` — confirmation page
13. `../globalconnect/src/app/(platform)/checkout/success/page.tsx` — success page
14. `../globalconnect/src/app/(platform)/checkout/cancel/page.tsx` — cancel page

## What to Build

### 1. Stripe React Native Integration
- Install and configure `@stripe/stripe-react-native`
- Set up `StripeProvider` with the publishable key
- Configure Apple Pay and Google Pay support

### 2. Ticket Selection Screen
- Display ticket tiers from the event's monetization config
- Ticket card UI: name, description, price, availability count, features included
- Quantity selector per ticket type
- Multi-currency support — study the web app's currency handling (USD, EUR, GBP, CAD, AUD, NGN, GHS, KES)
- Price breakdown: subtotal, fees, taxes, total
- "Sold out" state for unavailable tiers
- Promo code / discount code input

### 3. Checkout Screen
- Order summary at top
- Payment method selection:
  - Credit/debit card (Stripe CardField)
  - Apple Pay (iOS)
  - Google Pay (Android)
- Billing information form if required
- Terms and conditions acceptance
- "Pay" button with amount and currency
- Loading state during payment processing

### 4. Payment Confirmation Screen
- Success animation
- Order details (event name, ticket type, quantity, amount paid)
- Ticket QR code(s) for check-in
- "Add to Calendar" action
- "Share with friends" action
- "View My Tickets" navigation

### 5. My Tickets Screen
- List of all purchased tickets across events
- Each ticket shows: event name, date, ticket type, QR code
- Upcoming vs past tickets tabs
- Ticket detail with full QR code for scanning

### 6. Dynamic Offers
Study the web app's offer system:
- Special offers/discounts that appear based on conditions
- Offer modal with countdown timer
- One-tap purchase for offers

### Mobile-Specific Advantages
- Native Apple Pay / Google Pay for frictionless checkout
- Ticket QR codes available offline (cache in secure storage)
- Wallet integration — add tickets to Apple Wallet / Google Wallet if possible
- Receipt saved to the device

## Quality Requirements
- Payment flow must be PCI compliant — never handle raw card numbers, always use Stripe's tokenization
- Currency formatting must be exact (correct symbol, decimal places, thousands separators for each currency)
- The checkout flow must handle all edge cases: network failure during payment, duplicate payment prevention, session expiry
- Minimum payment amount validation per currency (study the web app's validation)
- All monetary calculations must match the backend — never calculate totals client-side for final charges
- Apple Pay / Google Pay should be shown only when available on the device
```

---

## Phase 8 — Notifications & Push Notifications

```prompt
You are building the notification system for the Event Dynamics mobile app, including real-time in-app notifications and native push notifications.

## Before Writing Any Code — Research First
Study these files from the web codebase:

1. `../globalconnect/src/hooks/use-notifications.ts` — the notification hook (how notifications are fetched, marked as read, real-time updates)
2. `../globalconnect/src/components/features/notifications/` — ALL notification UI components
3. `../globalconnect/src/app/(attendee)/attendee/notifications/page.tsx` — the notifications page
4. `../globalconnect/src/hooks/use-toast.ts` — the toast notification hook (in-app transient notifications)
5. `../globalconnect/src/lib/socket.ts` — how real-time notifications arrive via socket (look for notification-related events, the `joinUserRoom` pattern)
6. `../globalconnect/src/context/SessionSocketContext.tsx` — session-specific notifications (chat mentions, poll starts, Q&A answered, etc.)

## What to Build

### 1. Push Notification Infrastructure
- Set up `expo-notifications` for push notifications
- Configure notification channels (Android):
  - `event-updates` (high priority) — session starting, event changes
  - `messages` (high priority) — DMs, chat mentions
  - `networking` (default priority) — connection requests, recommendations
  - `offers` (default priority) — special offers, ticket deals
  - `general` (low priority) — general updates
- Register for push tokens and send to backend (study if the backend has an endpoint for registering device tokens)
- Handle notification permissions gracefully (explain why notifications matter before requesting)

### 2. In-App Notification Center
- Notification list screen with sections: Today, Earlier, This Week
- Notification types (study the web app's notification types):
  - Session starting soon / now live
  - New DM received
  - Connection request received / accepted
  - Q&A answer to your question
  - Poll started
  - New offer available
  - Event schedule change
  - Gamification achievement unlocked
- Mark as read (individual and mark all)
- Tap notification to navigate to the relevant screen (deep linking within app)
- Unread count badge on the tab bar notification icon
- Pull-to-refresh

### 3. Real-Time In-App Toasts
- Port the toast system to mobile using a notification banner at the top of the screen
- Toast types: success, error, info, warning
- Auto-dismiss after 4 seconds
- Tap to navigate to relevant screen
- Swipe to dismiss
- Stack multiple toasts (show newest, queue others)

### 4. Notification Preferences
- Per-category toggle (event updates, messages, networking, offers)
- Quiet hours setting
- Per-event notification override
- Global mute toggle

### Mobile-Specific Features
- Badge count on app icon (update when unread notifications change)
- Notification grouping (stack multiple notifications from same event)
- Rich notifications (show event images in notification)
- Notification actions (e.g., "Accept" / "Decline" on connection requests directly from notification)
- Background notification handling (update badge count even when app is closed)

## Quality Requirements
- Push notifications must be delivered reliably — handle token refresh and re-registration
- Tapping a notification must always navigate to the correct screen, even if the app was closed
- In-app notification list must be fast even with hundreds of notifications (virtualized)
- Real-time socket notifications and push notifications must not create duplicates
- Notification preferences must be respected — never send a notification the user has opted out of
- Battery-efficient: socket connection management should not drain battery
```

---

## Phase 9 — Gamification & Leaderboard

```prompt
You are building the gamification system for the Event Dynamics mobile app — points, achievements, leaderboards, and team competitions.

## Before Writing Any Code — Research First
Study these files from the web codebase:

1. `../globalconnect/src/hooks/use-gamification.ts` — the main gamification hook (points, achievements, leaderboard queries, real-time point updates)
2. `../globalconnect/src/hooks/use-teams.ts` — team-based gamification (team creation, joining, team leaderboard)
3. `../globalconnect/src/components/features/gamification/` — ALL gamification UI components (leaderboard, achievement cards, point displays, etc.)
4. `../globalconnect/src/app/(platform)/dashboard/events/[eventId]/leaderboard/page.tsx` — the leaderboard page
5. `../globalconnect/src/app/(attendee)/attendee/events/[eventId]/page.tsx` — look for gamification elements embedded in the event hub (points display, achievement toasts, etc.)

Also study the real-time service for gamification socket events:
6. `../real-time-service/src/gamification/` — the entire gamification directory to understand what socket events are emitted (point awards, leaderboard updates, achievement unlocks)
7. `../real-time-service/src/gamification/gamification.gateway.ts` — the WebSocket gateway for gamification events
8. `../real-time-service/src/gamification/teams/` — team-related socket events

## What to Build

### 1. Points System
- Points display widget (show current points with animated counter)
- Points history — list of actions that earned points with timestamps
- Point award animation (floating "+10 pts" when points are earned during the event)
- Real-time point updates via socket (study the gamification gateway events)

### 2. Achievements
- Achievement grid showing all available achievements for the event
- Locked vs unlocked visual states
- Achievement unlock animation (confetti + modal — the web app uses `canvas-confetti`, use `react-native-reanimated` for mobile)
- Achievement detail: name, description, points value, unlock criteria
- Push notification when a new achievement is unlocked

### 3. Leaderboard
- Individual leaderboard showing top attendees by points
- Team leaderboard showing top teams
- Current user's rank highlighted
- Real-time position updates (animate rank changes)
- Time filter: Today, This Session, All Time
- Pull-to-refresh
- Tap on a user to view their profile

### 4. Teams
- Team creation flow (study `use-teams.ts`)
- Join existing team (with invite code or browse)
- Team dashboard: members, total points, rank
- Team chat or team feed
- Leave team

### 5. Gamification Integration Points
These aren't standalone screens but integrations with other features:
- Show a points badge on the user's profile
- After sending a chat message, joining a session, answering a poll — show "+X pts" toast
- On the event hub screen, show a mini leaderboard widget
- Achievement progress bars embedded in relevant screens

### Mobile-Specific UX
- Haptic feedback when earning points or unlocking achievements
- Rich push notifications for achievements (with achievement icon)
- Widget on home screen showing current rank (if React Native supports widgets via Expo)
- Share achievements to social media via native share sheet

## Quality Requirements
- Leaderboard must update in real-time without full re-renders (animate individual position changes)
- Point counter animations must be smooth (use `react-native-reanimated` for spring animations)
- Achievement unlock must feel rewarding (combine animation + haptics + sound)
- The gamification system must not degrade performance of other features — point award events arrive frequently during active sessions
- All socket event listeners must be properly cleaned up on unmount
```

---

## Phase 10 — Sponsor & Expo Portal

```prompt
You are building the sponsor and expo features for the Event Dynamics mobile app — virtual booths, sponsor content, lead capture, and the sponsor management portal.

## Before Writing Any Code — Research First
Study these files from the web codebase:

### Attendee-Facing Expo
1. `../globalconnect/src/app/(attendee)/attendee/events/[eventId]/expo/page.tsx` — expo browsing page
2. `../globalconnect/src/hooks/use-expo.ts` — expo hook
3. `../globalconnect/src/hooks/use-booth-chat.ts` — booth chat hook
4. `../globalconnect/src/components/features/expo/` — ALL expo/booth UI components
5. `../globalconnect/src/components/features/sponsors/` — sponsor display components
6. `../globalconnect/src/components/features/ads/` — sponsor ad components

### Sponsor Portal
7. `../globalconnect/src/app/(sponsor)/sponsor/page.tsx` — sponsor dashboard home
8. `../globalconnect/src/app/(sponsor)/sponsor/booth/page.tsx` — booth management
9. `../globalconnect/src/app/(sponsor)/sponsor/booth/live/page.tsx` — live booth view
10. `../globalconnect/src/app/(sponsor)/sponsor/leads/page.tsx` — lead capture list
11. `../globalconnect/src/app/(sponsor)/sponsor/leads/all/page.tsx` — all leads view
12. `../globalconnect/src/app/(sponsor)/sponsor/leads/starred/page.tsx` — starred/priority leads
13. `../globalconnect/src/app/(sponsor)/sponsor/analytics/page.tsx` — sponsor analytics
14. `../globalconnect/src/app/(sponsor)/sponsor/messages/page.tsx` — sponsor messaging
15. `../globalconnect/src/app/(sponsor)/sponsor/export/page.tsx` — data export
16. `../globalconnect/src/app/(sponsor)/sponsor/team/page.tsx` — sponsor team management
17. `../globalconnect/src/hooks/use-leads.ts` — lead management hook
18. `../globalconnect/src/hooks/use-sponsor-management.ts` — sponsor management hook
19. `../globalconnect/src/hooks/use-sponsors.ts` — sponsor data hook
20. `../globalconnect/src/hooks/use-expo-staff.ts` — expo staff hook
21. `../globalconnect/src/store/leads.store.ts` — leads Zustand store
22. `../globalconnect/src/store/sponsor.store.ts` — sponsor Zustand store

## What to Build

### Attendee Side
1. **Expo Hall** — Grid/list of sponsor booths with logos, names, and categories. Search and filter.
2. **Booth Detail** — Sponsor booth page: company info, description, resources/documents, videos, team members, live chat
3. **Booth Live Chat** — Real-time chat with booth staff (port `use-booth-chat.ts`)
4. **Sponsor Ads** — Sponsored content cards that appear in the event feed / between sessions
5. **Resource Downloads** — Download sponsor PDFs, brochures using native file handling

### Sponsor Portal (Separate Navigation Stack)
6. **Sponsor Dashboard** — Overview: booth visitors count, leads captured, messages
7. **Lead Capture** —
   - QR code scanner to capture attendee badge scans
   - Manual lead entry form
   - Lead list with search, filter, star/unstar
   - Lead detail with notes and follow-up actions
   - Export leads (CSV via email or share)
8. **Booth Management** — Edit booth content, upload resources, manage team access
9. **Sponsor Analytics** — Booth visits, resource downloads, chat engagement metrics
10. **Sponsor Messages** — View and respond to booth chat messages

### Mobile-Specific Advantages
- QR code scanning for instant lead capture (huge mobile advantage over web)
- Business card scanning using camera + OCR (if feasible with `expo-camera`)
- Offline lead capture — save leads locally when offline, sync when back online
- Push notifications for new booth visitors and messages
- One-tap to call or email a lead from the lead detail screen

## Quality Requirements
- Lead capture must work offline — this is critical for expo floors with poor WiFi
- Booth chat must be real-time and reliable
- The expo hall must load quickly even with 50+ sponsors
- Sponsor analytics must display clearly on mobile screen sizes (responsive charts)
- Lead data must be handled securely — no plaintext PII in local storage
- Export functionality must work reliably (generate CSV, share via native share sheet)
```

---

## Phase 11 — Organizer Dashboard (Mobile-Lite)

```prompt
You are building a lightweight organizer dashboard for the Event Dynamics mobile app. This is NOT a full port of the web dashboard — it's a mobile-optimized subset focused on real-time event monitoring and quick actions that organizers need on-the-go.

## Before Writing Any Code — Research First
Study these files from the web codebase to understand what the full dashboard offers, then decide what's mobile-essential:

1. `../globalconnect/src/app/(platform)/dashboard/page.tsx` — main dashboard home
2. `../globalconnect/src/app/(platform)/dashboard/events/page.tsx` — event list
3. `../globalconnect/src/app/(platform)/dashboard/events/[eventId]/page.tsx` — event detail/management
4. `../globalconnect/src/app/(platform)/dashboard/events/[eventId]/analytics/page.tsx` — event analytics
5. `../globalconnect/src/app/(platform)/dashboard/events/[eventId]/engagement/page.tsx` — engagement tracking
6. `../globalconnect/src/app/(platform)/dashboard/events/[eventId]/producer/page.tsx` — producer controls
7. `../globalconnect/src/hooks/use-live-dashboard.ts` — real-time dashboard data hook
8. `../globalconnect/src/hooks/use-incident-reporting.ts` — incident reporting
9. `../globalconnect/src/hooks/use-incident-management.ts` — incident management
10. `../globalconnect/src/hooks/use-export-analytics.ts` — analytics export
11. `../globalconnect/src/graphql/dashboard.graphql.ts` — dashboard queries
12. `../globalconnect/src/store/incident.store.ts` — incident Zustand store

## What to Build (Mobile-Essential Features Only)

### 1. Event Overview Dashboard
- List of organizer's events with status (draft, published, live, ended)
- Quick stats per event: registered count, checked-in count, live viewers
- Tap to drill into event detail

### 2. Live Event Monitor
- Real-time attendee count (online now)
- Active session indicator
- Chat activity level (messages/minute)
- Engagement score
- Quick alerts for issues (high disconnect rate, reported incidents)

### 3. Quick Actions
- Start/end a session
- Enable/disable chat, Q&A, polls for active sessions
- Send push notification to all event attendees
- Pin/unpin a chat message

### 4. Incident Management
- View reported incidents
- Assign priority (study the incident store and hooks)
- Mark as resolved
- Push notification when new incident is reported

### 5. Analytics Snapshot
- Key metrics cards: total registrations, revenue, check-in rate, engagement score
- Simple charts: attendance over time, revenue by ticket type
- Export option (send full report to email)

### 6. Check-In Scanner
- QR code scanner for checking in attendees at the door
- Manual search by name/email for check-in
- Check-in count display
- This is a HIGH VALUE mobile feature — many organizers use their phone for check-in

### What NOT to Build for Mobile
- Full event creation wizard (too complex for mobile, keep on web)
- Session scheduling/editing (use web)
- Detailed sponsor management (use web)
- Blueprint/template management (use web)
- A/B test configuration (use web)
- The mobile dashboard should focus on MONITORING and QUICK ACTIONS, not configuration

## Quality Requirements
- Live data must update in real-time without manual refresh
- The check-in scanner must be fast — scan to confirmation in under 1 second
- Analytics charts must be readable on small screens (use appropriate chart types)
- The dashboard must work well under stress — during a live event with 1000+ attendees
- Incident alerts must be prominent and impossible to miss
```

---

## Phase 12 — Polish, Performance & App Store Readiness

```prompt
You are doing the final polish pass on the Event Dynamics mobile app to prepare it for app store submission. The core features are all built. Your job is performance optimization, UX polish, and production hardening.

## Before Starting — Audit the Entire Mobile Codebase
Go through every screen and feature in the mobile app. For each, verify:
1. Loading states exist and use skeleton placeholders (not generic spinners)
2. Error states exist with clear messages and retry actions
3. Empty states exist (e.g., "No events yet", "No connections")
4. Keyboard handling works on both iOS and Android
5. The screen looks correct on small phones (iPhone SE / small Android) and large phones/tablets
6. Dark mode works if implemented
7. Accessibility: all interactive elements have accessibility labels

## Also Study From the Web Codebase
1. `../globalconnect/src/app/layout.tsx` — how the web app handles global error boundaries, loading states, and metadata
2. `../globalconnect/src/components/ui/` — every UI primitive, ensure the mobile equivalents are consistent in behavior
3. `../globalconnect/src/app/globals.css` — the design token variables, verify the mobile theme matches exactly

## Performance Optimization

### 1. List Performance
- Audit all FlatList/FlashList usages
- Ensure `keyExtractor` is stable (no index-based keys)
- Ensure `renderItem` functions are memoized with `useCallback`
- Add `getItemLayout` where item heights are fixed for instant scroll-to-index
- Use `FlashList` from Shopify for the most performance-critical lists (event list, attendee list, chat messages)

### 2. Image Optimization
- All images must use `expo-image` with proper caching
- Add placeholder/blur hash for images
- Lazy load images below the fold
- Compress and resize images before upload (profile pictures)

### 3. Bundle Size
- Run `npx expo-doctor` and fix all issues
- Analyze bundle with `npx react-native-bundle-visualizer`
- Lazy load heavy screens (video, maps) using React.lazy or dynamic imports
- Tree-shake unused dependencies

### 4. Memory Management
- Profile the app for memory leaks (especially around socket connections and video)
- Ensure all `useEffect` cleanup functions properly dispose of listeners, timers, and subscriptions
- Verify no memory leaks when rapidly navigating between screens

### 5. Network Optimization
- Implement proper Apollo cache policies (cache-first for stable data, network-first for real-time data)
- Add offline support where it makes sense (cached events, cached tickets, cached connections)
- Handle slow/offline network gracefully on every screen
- Show network status bar when offline

## App Store Preparation

### 1. App Icon & Splash Screen
- Generate app icon in all required sizes using `expo-asset`
- Configure animated splash screen with the Event Dynamics logo

### 2. Deep Linking
- Configure universal links (iOS) and app links (Android)
- Support deep links for: events, sessions, user profiles, password reset
- Test deep link handling from closed, background, and foreground states

### 3. Error Tracking
- Set up Sentry (`sentry-expo`) for crash reporting
- Add breadcrumbs for key user actions
- Configure source maps upload for readable stack traces

### 4. Analytics
- Set up basic screen tracking (which screens users visit)
- Track key events: login, event registration, session join, connection made, purchase completed

### 5. App Store Metadata
- Prepare app store screenshots for multiple device sizes
- Write app store description
- Configure app privacy details (what data is collected and why)
- Set up TestFlight (iOS) and internal testing track (Android) for beta distribution

### 6. Security Hardening
- Verify all tokens are stored in `expo-secure-store`, not AsyncStorage
- Verify no sensitive data is logged in production
- Verify SSL pinning is configured for API calls
- Verify biometric auth uses secure enclave

## Quality Requirements
- The app must start (cold launch to interactive) in under 2 seconds
- All screen transitions must be 60fps
- The app must not crash — zero tolerance for unhandled exceptions
- The app must work offline gracefully (not crash, show cached data where possible, queue actions for when online)
- The app must pass both Apple and Google's review guidelines
- Accessibility: the app must be usable with VoiceOver (iOS) and TalkBack (Android)
```

---

## Dependency Graph

```
Phase 0 (Scaffold)
  └── Phase 1 (Auth)
       └── Phase 2 (Event Discovery)
            └── Phase 3 (Attendee Hub)
                 ├── Phase 4 (Chat/Q&A/Polls) ─── can run in parallel
                 ├── Phase 5 (Video) ──────────── can run in parallel
                 ├── Phase 6 (Networking) ─────── can run in parallel
                 ├── Phase 7 (Payments) ───────── can run in parallel
                 ├── Phase 8 (Notifications) ──── can run in parallel
                 ├── Phase 9 (Gamification) ────── can run in parallel
                 ├── Phase 10 (Sponsor/Expo) ──── can run in parallel
                 └── Phase 11 (Organizer Lite) ── can run in parallel
                      └── Phase 12 (Polish & Store Readiness) ── LAST
```

## Agent Assignment Strategy

| Agent | Phases | Notes |
|-------|--------|-------|
| Agent 1 | Phase 0 → 1 → 2 → 3 | Foundation agent — must go first, sequential |
| Agent 2 | Phase 4 | Real-time specialist |
| Agent 3 | Phase 5 | Video specialist (Daily.co native SDK knowledge needed) |
| Agent 4 | Phase 6 + 8 | Social features (networking + notifications are related) |
| Agent 5 | Phase 7 | Payments specialist (Stripe RN knowledge needed) |
| Agent 6 | Phase 9 | Gamification specialist |
| Agent 7 | Phase 10 | Sponsor portal |
| Agent 8 | Phase 11 | Organizer dashboard |
| Agent 9 | Phase 12 | QA/polish specialist — runs last |