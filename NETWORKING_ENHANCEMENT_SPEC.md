# Networking Enhancement Specification

## Overview

This document specifies the implementation of advanced networking features that transform the existing proximity ping system into a complete networking solution with measurable outcomes.

**Current State:** Basic proximity discovery + ping + DM integration
**Target State:** Full networking lifecycle with follow-up automation, context-rich matching, and outcome tracking

---

## Architecture Context

### Existing Services
- `globalconnect/` - Next.js frontend
- `real-time-service/` - NestJS WebSocket service (proximity, DM)
- `api-gateway/` - NestJS REST API
- `shared-libs/prisma-client/` - Shared Prisma schema

### Existing Features to Build Upon
- Proximity tracking via Redis GEO (`proximity.gateway.ts`)
- Direct messaging (`use-direct-messages.ts`, `dm-container.tsx`)
- User profiles and registration
- Event/session management with agenda tracking

---

## Phase 1: Connection Tracking Foundation

### 1.1 Database Schema

Add to `shared-libs/prisma-client/prisma/schema.prisma`:

```prisma
model Connection {
  id            String    @id @default(cuid())
  userAId       String
  userBId       String
  eventId       String

  // Connection metadata
  connectedAt   DateTime  @default(now())
  connectionType ConnectionType @default(PROXIMITY_PING)
  initialMessage String?

  // Follow-up tracking
  followUpSentAt    DateTime?
  followUpOpenedAt  DateTime?
  followUpRepliedAt DateTime?

  // Outcome tracking
  meetingScheduled  Boolean @default(false)
  meetingDate       DateTime?
  outcomeType       OutcomeType?
  outcomeNotes      String?
  outcomeReportedAt DateTime?

  // Relations
  userA         UserReference @relation("ConnectionUserA", fields: [userAId], references: [id])
  userB         UserReference @relation("ConnectionUserB", fields: [userBId], references: [id])
  event         Event         @relation(fields: [eventId], references: [id])

  @@unique([userAId, userBId, eventId])
  @@index([userAId])
  @@index([userBId])
  @@index([eventId])
}

enum ConnectionType {
  PROXIMITY_PING
  DM_INITIATED
  SESSION_QA
  MANUAL_EXCHANGE
}

enum OutcomeType {
  MEETING_HELD
  JOB_REFERRAL
  PARTNERSHIP
  SALE_DEAL
  MENTORSHIP
  OTHER
}

model ConnectionContext {
  id            String   @id @default(cuid())
  connectionId  String
  contextType   ContextType
  contextValue  String

  connection    Connection @relation(fields: [connectionId], references: [id])

  @@index([connectionId])
}

enum ContextType {
  SHARED_SESSION
  SHARED_INTEREST
  MUTUAL_CONNECTION
  SAME_COMPANY_SIZE
  SAME_INDUSTRY
  QA_INTERACTION
}
```

### 1.2 Backend: Connection Service

Create `api-gateway/src/networking/connections/`:

**connections.service.ts:**
```typescript
@Injectable()
export class ConnectionsService {
  // Create connection when ping is sent/accepted
  async createConnection(data: CreateConnectionDto): Promise<Connection>

  // Get all connections for a user at an event
  async getUserEventConnections(userId: string, eventId: string): Promise<Connection[]>

  // Get connection with full context (why they should connect)
  async getConnectionWithContext(connectionId: string): Promise<ConnectionWithContext>

  // Update follow-up status
  async markFollowUpSent(connectionId: string): Promise<void>
  async markFollowUpOpened(connectionId: string): Promise<void>
  async markFollowUpReplied(connectionId: string): Promise<void>

  // Report outcome
  async reportOutcome(connectionId: string, data: ReportOutcomeDto): Promise<void>

  // Analytics
  async getEventNetworkingStats(eventId: string): Promise<EventNetworkingStats>
  async getUserNetworkingStats(userId: string): Promise<UserNetworkingStats>
}
```

### 1.3 Frontend: Update Proximity to Track Connections

Modify `real-time-service/src/networking/proximity/proximity.gateway.ts`:

When a ping is sent and responded to (via DM or reply), create a Connection record:

```typescript
@SubscribeMessage('proximity.ping')
async handleProximityPing(...) {
  // Existing ping logic...

  // After successful ping, create connection record
  await this.connectionsService.createConnection({
    userAId: sender.sub,
    userBId: dto.targetUserId,
    eventId: dto.eventId,
    connectionType: 'PROXIMITY_PING',
    initialMessage: dto.message,
  });
}
```

---

## Phase 2: Context-Rich Matching ("Why Connect")

### 2.1 Context Generation Service

Create `api-gateway/src/networking/matching/`:

**matching.service.ts:**
```typescript
@Injectable()
export class MatchingService {
  // Generate connection context for two users
  async generateConnectionContext(
    userAId: string,
    userBId: string,
    eventId: string
  ): Promise<ConnectionContext[]> {
    const contexts: ConnectionContext[] = [];

    // 1. Shared sessions attended
    const sharedSessions = await this.findSharedSessions(userAId, userBId, eventId);
    contexts.push(...sharedSessions.map(s => ({
      contextType: 'SHARED_SESSION',
      contextValue: s.title
    })));

    // 2. Shared interests from registration
    const sharedInterests = await this.findSharedInterests(userAId, userBId);
    contexts.push(...sharedInterests.map(i => ({
      contextType: 'SHARED_INTEREST',
      contextValue: i
    })));

    // 3. Mutual connections from past events
    const mutualConnections = await this.findMutualConnections(userAId, userBId);
    contexts.push(...mutualConnections.map(c => ({
      contextType: 'MUTUAL_CONNECTION',
      contextValue: c.name
    })));

    // 4. Q&A interactions (if one asked question other might answer)
    const qaInteractions = await this.findQAInteractions(userAId, userBId, eventId);
    contexts.push(...qaInteractions);

    return contexts;
  }

  // Get enhanced nearby users with context
  async getEnhancedNearbyUsers(
    userId: string,
    nearbyUserIds: string[],
    eventId: string
  ): Promise<EnhancedNearbyUser[]> {
    return Promise.all(nearbyUserIds.map(async (nearbyUserId) => {
      const user = await this.getUserProfile(nearbyUserId);
      const contexts = await this.generateConnectionContext(userId, nearbyUserId, eventId);

      return {
        ...user,
        connectionContexts: contexts,
        matchScore: this.calculateMatchScore(contexts),
      };
    }));
  }
}
```

### 2.2 Frontend: Enhanced Nearby User Card

Update `globalconnect/src/components/features/proximity/nearby-users-panel.tsx`:

```tsx
interface EnhancedNearbyUser extends NearbyUser {
  company?: string;
  role?: string;
  connectionContexts: Array<{
    type: 'SHARED_SESSION' | 'SHARED_INTEREST' | 'MUTUAL_CONNECTION' | 'QA_INTERACTION';
    value: string;
  }>;
  matchScore?: number;
}

// Render context badges
const ConnectionContextBadges = ({ contexts }) => (
  <div className="space-y-1 mt-2">
    <p className="text-xs font-medium text-muted-foreground">Why connect:</p>
    <div className="flex flex-wrap gap-1">
      {contexts.slice(0, 3).map((ctx, i) => (
        <Badge key={i} variant="secondary" className="text-xs">
          {ctx.type === 'SHARED_SESSION' && <Calendar className="h-3 w-3 mr-1" />}
          {ctx.type === 'SHARED_INTEREST' && <Sparkles className="h-3 w-3 mr-1" />}
          {ctx.type === 'MUTUAL_CONNECTION' && <Users className="h-3 w-3 mr-1" />}
          {ctx.value}
        </Badge>
      ))}
    </div>
  </div>
);
```

---

## Phase 3: Post-Event Follow-Up Automation

### 3.1 Follow-Up Email Templates

Create `api-gateway/src/networking/follow-up/`:

**follow-up.service.ts:**
```typescript
@Injectable()
export class FollowUpService {
  // Schedule follow-up emails for all connections at an event
  async scheduleEventFollowUps(eventId: string): Promise<void> {
    const connections = await this.connectionsService.getEventConnections(eventId);

    // Group by user - each user gets one email with all their connections
    const connectionsByUser = this.groupConnectionsByUser(connections);

    for (const [userId, userConnections] of connectionsByUser) {
      await this.emailQueue.add('send-follow-up', {
        userId,
        eventId,
        connections: userConnections,
        scheduledFor: this.getFollowUpTime(eventId), // 24 hours after event ends
      });
    }
  }

  // Generate personalized follow-up email
  async generateFollowUpEmail(userId: string, eventId: string): Promise<FollowUpEmail> {
    const connections = await this.getUserEventConnections(userId, eventId);
    const event = await this.getEvent(eventId);

    return {
      subject: `Your ${connections.length} connections from ${event.name}`,
      connections: connections.map(c => ({
        name: c.otherUser.name,
        company: c.otherUser.company,
        initialContext: c.initialMessage,
        suggestedMessage: this.generateSuggestedMessage(c),
        profileUrl: `/profile/${c.otherUser.id}`,
        linkedInUrl: c.otherUser.linkedInUrl,
      })),
      oneClickActions: {
        sendAllFollowUps: true,
        exportToLinkedIn: true,
      }
    };
  }

  // Generate AI-powered suggested follow-up message
  private generateSuggestedMessage(connection: Connection): string {
    const contexts = connection.contexts;

    if (contexts.find(c => c.type === 'SHARED_SESSION')) {
      return `Hi ${connection.otherUser.firstName}, great meeting you at ${connection.event.name}! I enjoyed the ${contexts[0].value} session too. Would love to continue our conversation about...`;
    }

    return `Hi ${connection.otherUser.firstName}, it was great connecting at ${connection.event.name}. ${connection.initialMessage ? `You mentioned "${connection.initialMessage}" - ` : ''}I'd love to stay in touch!`;
  }
}
```

### 3.2 Follow-Up Tracking Endpoints

**follow-up.controller.ts:**
```typescript
@Controller('follow-up')
export class FollowUpController {
  // Track email open (via pixel)
  @Get('track/open/:connectionId')
  async trackOpen(@Param('connectionId') id: string) {
    await this.followUpService.markFollowUpOpened(id);
    return this.transparentPixel();
  }

  // Track link click
  @Get('track/click/:connectionId/:action')
  async trackClick(
    @Param('connectionId') id: string,
    @Param('action') action: string,
    @Query('redirect') redirect: string,
  ) {
    await this.followUpService.trackAction(id, action);
    return { redirect };
  }

  // Send follow-up message
  @Post(':connectionId/send')
  async sendFollowUp(
    @Param('connectionId') id: string,
    @Body() body: SendFollowUpDto,
  ) {
    return this.followUpService.sendFollowUpMessage(id, body.message);
  }
}
```

### 3.3 Frontend: Follow-Up Dashboard

Create `globalconnect/src/app/(attendee)/attendee/connections/page.tsx`:

```tsx
export default function ConnectionsPage() {
  const { data: connections } = useConnections();

  return (
    <div className="container py-8">
      <h1 className="text-2xl font-bold mb-6">Your Event Connections</h1>

      {/* Pending follow-ups */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Pending Follow-ups
          </CardTitle>
          <CardDescription>
            These connections are waiting to hear from you
          </CardDescription>
        </CardHeader>
        <CardContent>
          {connections.filter(c => !c.followUpSent).map(connection => (
            <ConnectionFollowUpCard
              key={connection.id}
              connection={connection}
              onSendFollowUp={handleSendFollowUp}
            />
          ))}
        </CardContent>
      </Card>

      {/* Connection history by event */}
      <ConnectionHistory connections={connections} />
    </div>
  );
}
```

---

## Phase 4: Outcome Tracking & Analytics

### 4.1 Outcome Reporting

**Frontend Component:** `globalconnect/src/components/features/connections/outcome-reporter.tsx`

```tsx
export const OutcomeReporter = ({ connectionId, otherUserName }) => {
  const [outcome, setOutcome] = useState<OutcomeType | null>(null);

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Trophy className="h-4 w-4 mr-1" />
          Report Outcome
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Did this connection lead to something?</DialogTitle>
          <DialogDescription>
            Help us measure networking impact and improve recommendations
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-2 py-4">
          {[
            { type: 'MEETING_HELD', icon: Calendar, label: 'Had a meeting' },
            { type: 'JOB_REFERRAL', icon: Briefcase, label: 'Job referral' },
            { type: 'PARTNERSHIP', icon: Handshake, label: 'Partnership' },
            { type: 'SALE_DEAL', icon: DollarSign, label: 'Sale/Deal' },
            { type: 'MENTORSHIP', icon: GraduationCap, label: 'Mentorship' },
            { type: 'OTHER', icon: Star, label: 'Other' },
          ].map(({ type, icon: Icon, label }) => (
            <Button
              key={type}
              variant={outcome === type ? 'default' : 'outline'}
              className="h-auto py-3 flex-col"
              onClick={() => setOutcome(type)}
            >
              <Icon className="h-5 w-5 mb-1" />
              {label}
            </Button>
          ))}
        </div>

        <Textarea
          placeholder="Tell us more (optional)..."
          className="mb-4"
        />

        <Button onClick={handleSubmit} className="w-full">
          Submit Outcome
        </Button>
      </DialogContent>
    </Dialog>
  );
};
```

### 4.2 Organizer Analytics Dashboard

**Frontend:** `globalconnect/src/app/(organizer)/organizer/events/[eventId]/networking/page.tsx`

```tsx
export default function EventNetworkingAnalytics({ params }) {
  const { data: stats } = useEventNetworkingStats(params.eventId);

  return (
    <div className="container py-8">
      <h1 className="text-2xl font-bold mb-6">Networking Analytics</h1>

      {/* Key metrics */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <MetricCard
          title="Connections Made"
          value={stats.totalConnections}
          icon={Users}
          trend={stats.connectionsTrend}
        />
        <MetricCard
          title="Follow-ups Sent"
          value={stats.followUpsSent}
          icon={Mail}
          percentage={stats.followUpRate}
        />
        <MetricCard
          title="Meetings Scheduled"
          value={stats.meetingsScheduled}
          icon={Calendar}
        />
        <MetricCard
          title="Reported Outcomes"
          value={stats.reportedOutcomes}
          icon={Trophy}
        />
      </div>

      {/* Outcome breakdown */}
      <Card className="mb-8">
        <CardHeader>
          <CardTitle>Outcome Types</CardTitle>
        </CardHeader>
        <CardContent>
          <OutcomesPieChart data={stats.outcomeBreakdown} />
        </CardContent>
      </Card>

      {/* Connection graph */}
      <Card>
        <CardHeader>
          <CardTitle>Connection Network</CardTitle>
          <CardDescription>
            Visualize how attendees connected at your event
          </CardDescription>
        </CardHeader>
        <CardContent className="h-[400px]">
          <ConnectionNetworkGraph eventId={params.eventId} />
        </CardContent>
      </Card>
    </div>
  );
}
```

### 4.3 Analytics API

**api-gateway/src/networking/analytics/analytics.service.ts:**

```typescript
@Injectable()
export class NetworkingAnalyticsService {
  async getEventStats(eventId: string): Promise<EventNetworkingStats> {
    const connections = await this.prisma.connection.findMany({
      where: { eventId },
      include: { contexts: true }
    });

    return {
      totalConnections: connections.length,
      uniqueNetworkers: new Set([
        ...connections.map(c => c.userAId),
        ...connections.map(c => c.userBId)
      ]).size,
      followUpsSent: connections.filter(c => c.followUpSentAt).length,
      followUpRate: this.calculateRate(
        connections.filter(c => c.followUpSentAt).length,
        connections.length
      ),
      meetingsScheduled: connections.filter(c => c.meetingScheduled).length,
      reportedOutcomes: connections.filter(c => c.outcomeType).length,
      outcomeBreakdown: this.groupByOutcome(connections),
      connectionsByType: this.groupByConnectionType(connections),
      topConnectors: await this.getTopConnectors(eventId),
      networkingNPS: await this.calculateNetworkingNPS(eventId),
    };
  }

  async getUserStats(userId: string): Promise<UserNetworkingStats> {
    const connections = await this.prisma.connection.findMany({
      where: { OR: [{ userAId: userId }, { userBId: userId }] },
      include: { event: true, contexts: true }
    });

    return {
      totalConnections: connections.length,
      eventCount: new Set(connections.map(c => c.eventId)).size,
      followUpRate: this.calculateFollowUpRate(connections),
      outcomeRate: this.calculateOutcomeRate(connections),
      connectionsByEvent: this.groupByEvent(connections),
      recentConnections: connections.slice(0, 10),
    };
  }
}
```

---

## Phase 5: LinkedIn Integration (Optional Enhancement)

### 5.1 LinkedIn OAuth

Add LinkedIn OAuth to enable:
- Pull profile data (headline, company, photo)
- Show mutual LinkedIn connections
- One-click "Connect on LinkedIn" with context message
- Export event attendance to LinkedIn activity

### 5.2 Implementation Notes

```typescript
// LinkedIn OAuth config
const linkedInConfig = {
  clientId: process.env.LINKEDIN_CLIENT_ID,
  clientSecret: process.env.LINKEDIN_CLIENT_SECRET,
  scope: ['r_liteprofile', 'r_emailaddress', 'w_member_social'],
  callbackUrl: '/api/auth/linkedin/callback',
};

// After OAuth, store LinkedIn profile URL in UserReference
model UserReference {
  // ... existing fields
  linkedInUrl     String?
  linkedInId      String?
  linkedInHeadline String?
}
```

---

## Implementation Order

### Sprint 1: Foundation (1-2 weeks)
1. Add Connection model to Prisma schema
2. Create ConnectionsService with basic CRUD
3. Update proximity ping to create connections
4. Basic connections list page

### Sprint 2: Context (1-2 weeks)
1. Create MatchingService
2. Add context generation (shared sessions, interests)
3. Update nearby users UI with context badges
4. Store contexts in ConnectionContext table

### Sprint 3: Follow-Up (1-2 weeks)
1. Create FollowUpService
2. Email templates and queue system
3. Follow-up tracking (opens, clicks)
4. Follow-up dashboard UI

### Sprint 4: Analytics (1-2 weeks)
1. Outcome reporting UI and API
2. Organizer analytics dashboard
3. Connection network visualization
4. Export functionality

### Sprint 5: Polish (1 week)
1. LinkedIn integration (if desired)
2. Mobile optimization
3. Performance optimization
4. Testing and bug fixes

---

## API Endpoints Summary

```
POST   /api/connections                    - Create connection
GET    /api/connections/user/:userId       - Get user's connections
GET    /api/connections/event/:eventId     - Get event connections
GET    /api/connections/:id                - Get connection with context
PATCH  /api/connections/:id/outcome        - Report outcome

GET    /api/matching/nearby/:eventId       - Get enhanced nearby users
GET    /api/matching/context/:userAId/:userBId - Get connection context

POST   /api/follow-up/schedule/:eventId    - Schedule follow-ups for event
POST   /api/follow-up/:connectionId/send   - Send follow-up message
GET    /api/follow-up/track/open/:id       - Track email open
GET    /api/follow-up/track/click/:id/:action - Track action

GET    /api/analytics/event/:eventId       - Get event networking stats
GET    /api/analytics/user/:userId         - Get user networking stats
GET    /api/analytics/outcomes/:eventId    - Get outcome breakdown
```

---

## Files to Create/Modify

### New Files
```
api-gateway/src/networking/
├── connections/
│   ├── connections.module.ts
│   ├── connections.service.ts
│   ├── connections.controller.ts
│   └── dto/
├── matching/
│   ├── matching.module.ts
│   └── matching.service.ts
├── follow-up/
│   ├── follow-up.module.ts
│   ├── follow-up.service.ts
│   ├── follow-up.controller.ts
│   └── templates/
└── analytics/
    ├── analytics.module.ts
    ├── analytics.service.ts
    └── analytics.controller.ts

globalconnect/src/
├── app/(attendee)/attendee/connections/
│   └── page.tsx
├── app/(organizer)/organizer/events/[eventId]/networking/
│   └── page.tsx
├── components/features/connections/
│   ├── connection-card.tsx
│   ├── outcome-reporter.tsx
│   ├── follow-up-card.tsx
│   └── connection-network-graph.tsx
└── hooks/
    ├── use-connections.ts
    └── use-networking-stats.ts
```

### Files to Modify
```
shared-libs/prisma-client/prisma/schema.prisma  - Add Connection models
real-time-service/src/networking/proximity/proximity.gateway.ts - Track connections
globalconnect/src/components/features/proximity/nearby-users-panel.tsx - Add context
```
