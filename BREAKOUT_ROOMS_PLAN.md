# Breakout Rooms Implementation Plan

## Overview

Implement breakout rooms feature allowing small-group video discussions during virtual sessions. Attendees can join topic-based rooms with facilitators, timers, and the ability to recall everyone back to the main session.

## Architecture Decision

**Where to store breakout room data:**

- **Persistent data (room configuration)** → `event-lifecycle-service` (SQLAlchemy/PostgreSQL)
- **Real-time state (participants, timers)** → `real-time-service` (Prisma + Redis for presence)

This follows the existing pattern where circles (ConversationCircle) are managed in real-time-service.

---

## Phase 1: Database Schema

### 1.1 Real-Time Service (Prisma) - Primary Storage

Add to `real-time-service/prisma/schema.prisma`:

```prisma
enum BreakoutRoomStatus {
  WAITING    // Room created, waiting to start
  ACTIVE     // Room is live
  CLOSING    // Warning sent, about to close
  CLOSED     // Room ended
}

enum BreakoutParticipantRole {
  FACILITATOR
  PARTICIPANT
}

model BreakoutRoom {
  id                String              @id @default(cuid())
  createdAt         DateTime            @default(now())

  sessionId         String              // Parent session ID (from event-lifecycle-service)
  eventId           String              // Event ID for easier querying

  name              String              @db.VarChar(100)
  topic             String?             @db.VarChar(500)
  maxParticipants   Int                 @default(8)
  durationMinutes   Int                 @default(15)
  autoAssign        Boolean             @default(false)

  status            BreakoutRoomStatus  @default(WAITING)
  startedAt         DateTime?
  endedAt           DateTime?

  creatorId         String
  creator           UserReference       @relation("BreakoutRoomCreator", fields: [creatorId], references: [id])

  facilitatorId     String?
  facilitator       UserReference?      @relation("BreakoutRoomFacilitator", fields: [facilitatorId], references: [id])

  participants      BreakoutParticipant[]

  // Video room integration (external provider like Daily.co, Twilio, etc.)
  videoRoomId       String?             @db.VarChar(255)
  videoRoomUrl      String?             @db.VarChar(500)

  @@index([sessionId])
  @@index([eventId])
  @@index([status])
  @@map("breakout_rooms")
}

model BreakoutParticipant {
  id                String                    @id @default(cuid())
  joinedAt          DateTime                  @default(now())
  leftAt            DateTime?

  role              BreakoutParticipantRole   @default(PARTICIPANT)
  speakingTimeSeconds Int                     @default(0)

  userId            String
  user              UserReference             @relation(fields: [userId], references: [id], onDelete: Cascade)

  roomId            String
  room              BreakoutRoom              @relation(fields: [roomId], references: [id], onDelete: Cascade)

  @@unique([userId, roomId])
  @@index([roomId])
  @@map("breakout_participants")
}
```

### 1.2 Update UserReference Relations

Add to UserReference model:

```prisma
model UserReference {
  // ... existing fields ...

  // Breakout rooms
  createdBreakoutRooms    BreakoutRoom[]        @relation("BreakoutRoomCreator")
  facilitatedBreakoutRooms BreakoutRoom[]       @relation("BreakoutRoomFacilitator")
  breakoutParticipations  BreakoutParticipant[]
}
```

---

## Phase 2: WebSocket Gateway

### 2.1 Create Breakout Gateway

Create `real-time-service/src/networking/breakout/`:

```
breakout/
├── breakout.module.ts
├── breakout.gateway.ts
├── breakout.service.ts
└── dto/
    ├── create-room.dto.ts
    ├── join-room.dto.ts
    ├── leave-room.dto.ts
    └── close-room.dto.ts
```

### 2.2 WebSocket Events

| Event | Direction | Description |
|-------|-----------|-------------|
| `breakout.rooms.list` | Client → Server | Get available rooms for a session |
| `breakout.rooms.updated` | Server → Client | Broadcast when rooms list changes |
| `breakout.room.create` | Client → Server | Create a new breakout room |
| `breakout.room.created` | Server → Client | Broadcast new room to session |
| `breakout.room.join` | Client → Server | Join a specific room |
| `breakout.room.leave` | Client → Server | Leave current room |
| `breakout.room.close` | Client → Server | Close room (facilitator/admin) |
| `breakout.room.closed` | Server → Client | Broadcast room closure |
| `breakout.participants.update` | Server → Client | Broadcast roster changes |
| `breakout.timer.start` | Client → Server | Start room timer (facilitator) |
| `breakout.timer.tick` | Server → Client | Timer countdown updates |
| `breakout.timer.warning` | Server → Client | Time remaining alerts (5min, 1min) |
| `breakout.all.recall` | Client → Server | Recall everyone to main session |
| `breakout.recalled` | Server → Client | Notification to return to main |

### 2.3 Gateway Implementation Pattern

```typescript
// breakout.gateway.ts
@WebSocketGateway({
  cors: { origin: true, credentials: true },
  namespace: '/events',
})
export class BreakoutGateway {
  @WebSocketServer() server: Server;

  constructor(private readonly breakoutService: BreakoutService) {}

  @SubscribeMessage('breakout.room.create')
  async handleCreateRoom(
    @MessageBody() dto: CreateRoomDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    // Require breakout:manage or session ownership
    const room = await this.breakoutService.createRoom(user.sub, dto);

    // Broadcast to session
    this.server.to(`session:${dto.sessionId}`).emit('breakout.room.created', room);
    return { success: true, room };
  }

  @SubscribeMessage('breakout.room.join')
  async handleJoinRoom(
    @MessageBody() dto: JoinRoomDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const result = await this.breakoutService.joinRoom(user.sub, dto.roomId);

    // Join socket room for this breakout
    client.join(`breakout:${dto.roomId}`);

    // Broadcast roster update
    this.server.to(`breakout:${dto.roomId}`).emit('breakout.participants.update', result);
    return { success: true, ...result };
  }

  // Timer management with scheduled jobs
  @SubscribeMessage('breakout.timer.start')
  async handleStartTimer(
    @MessageBody() dto: { roomId: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    await this.breakoutService.startTimer(dto.roomId, user.sub);
    // Service will emit timer.tick events via scheduled job
    return { success: true };
  }
}
```

---

## Phase 3: Service Layer

### 3.1 Breakout Service

```typescript
// breakout.service.ts
@Injectable()
export class BreakoutService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly schedulerRegistry: SchedulerRegistry,
  ) {}

  async createRoom(creatorId: string, dto: CreateRoomDto) {
    return this.prisma.breakoutRoom.create({
      data: {
        sessionId: dto.sessionId,
        eventId: dto.eventId,
        name: dto.name,
        topic: dto.topic,
        maxParticipants: dto.maxParticipants || 8,
        durationMinutes: dto.durationMinutes || 15,
        creatorId,
        facilitatorId: dto.facilitatorId || creatorId,
        status: 'WAITING',
      },
      include: {
        creator: { select: { id: true, firstName: true, lastName: true } },
        facilitator: { select: { id: true, firstName: true, lastName: true } },
        _count: { select: { participants: true } },
      },
    });
  }

  async joinRoom(userId: string, roomId: string) {
    const room = await this.prisma.breakoutRoom.findUnique({
      where: { id: roomId },
      include: { _count: { select: { participants: true } } },
    });

    if (!room) throw new NotFoundException('Room not found');
    if (room.status === 'CLOSED') throw new BadRequestException('Room is closed');
    if (room._count.participants >= room.maxParticipants) {
      throw new BadRequestException('Room is full');
    }

    await this.prisma.breakoutParticipant.create({
      data: { userId, roomId, role: 'PARTICIPANT' },
    });

    return this.getRoomWithParticipants(roomId);
  }

  async getRoomsForSession(sessionId: string) {
    return this.prisma.breakoutRoom.findMany({
      where: { sessionId, status: { not: 'CLOSED' } },
      include: {
        facilitator: { select: { id: true, firstName: true, lastName: true } },
        _count: { select: { participants: true } },
      },
      orderBy: { createdAt: 'asc' },
    });
  }

  // Timer management
  async startTimer(roomId: string, userId: string) {
    const room = await this.prisma.breakoutRoom.update({
      where: { id: roomId },
      data: { status: 'ACTIVE', startedAt: new Date() },
    });

    // Schedule timer warnings and end
    const endTime = addMinutes(new Date(), room.durationMinutes);
    // ... schedule jobs for warnings at 5min, 1min, and room close
  }
}
```

---

## Phase 4: Frontend Implementation

### 4.1 New Pages/Components

```
globalconnect/src/app/(platform)/dashboard/events/[eventId]/sessions/[sessionId]/
├── breakout-rooms/
│   └── page.tsx                    # Breakout rooms management (organizer)

globalconnect/src/app/(attendee)/attendee/events/[eventId]/sessions/[sessionId]/
├── breakout/
│   ├── page.tsx                    # Breakout room listing (attendee)
│   └── [roomId]/
│       └── page.tsx                # Inside a breakout room

globalconnect/src/components/features/breakout/
├── BreakoutRoomList.tsx            # List of available rooms
├── BreakoutRoomCard.tsx            # Single room card with join button
├── BreakoutRoomView.tsx            # Inside-room experience
├── BreakoutTimer.tsx               # Countdown timer component
├── CreateBreakoutRoomModal.tsx     # Modal to create new room
└── index.ts
```

### 4.2 Organizer Breakout Management Page

```tsx
// breakout-rooms/page.tsx
export default function BreakoutRoomsManagementPage() {
  const { sessionId, eventId } = useParams();
  const { socket, isConnected } = useSocket();
  const [rooms, setRooms] = useState<BreakoutRoom[]>([]);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  useEffect(() => {
    if (!socket || !isConnected) return;

    // Request current rooms
    socket.emit('breakout.rooms.list', { sessionId }, (response) => {
      if (response.success) setRooms(response.rooms);
    });

    // Listen for updates
    socket.on('breakout.room.created', (room) => {
      setRooms(prev => [...prev, room]);
    });
    socket.on('breakout.room.closed', ({ roomId }) => {
      setRooms(prev => prev.filter(r => r.id !== roomId));
    });
    socket.on('breakout.participants.update', (data) => {
      setRooms(prev => prev.map(r => r.id === data.roomId ? { ...r, ...data } : r));
    });

    return () => {
      socket.off('breakout.room.created');
      socket.off('breakout.room.closed');
      socket.off('breakout.participants.update');
    };
  }, [socket, isConnected, sessionId]);

  const handleRecallAll = () => {
    socket?.emit('breakout.all.recall', { sessionId });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Breakout Rooms</h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleRecallAll}>
            <Users className="h-4 w-4 mr-2" />
            Recall All
          </Button>
          <Button onClick={() => setIsCreateModalOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Create Room
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {rooms.map(room => (
          <BreakoutRoomCard key={room.id} room={room} isOrganizer />
        ))}
      </div>

      <CreateBreakoutRoomModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        sessionId={sessionId}
        eventId={eventId}
      />
    </div>
  );
}
```

### 4.3 BreakoutRoomCard Component

```tsx
// BreakoutRoomCard.tsx
interface BreakoutRoomCardProps {
  room: BreakoutRoom;
  isOrganizer?: boolean;
  onJoin?: () => void;
}

export function BreakoutRoomCard({ room, isOrganizer, onJoin }: BreakoutRoomCardProps) {
  const isFull = room.participantCount >= room.maxParticipants;
  const statusColors = {
    WAITING: 'bg-yellow-500/10 text-yellow-600',
    ACTIVE: 'bg-green-500/10 text-green-600',
    CLOSING: 'bg-orange-500/10 text-orange-600',
    CLOSED: 'bg-gray-500/10 text-gray-600',
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">{room.name}</CardTitle>
          <Badge className={statusColors[room.status]}>{room.status}</Badge>
        </div>
        {room.topic && (
          <p className="text-sm text-muted-foreground">{room.topic}</p>
        )}
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center gap-2">
            <Users className="h-4 w-4" />
            <span>{room.participantCount}/{room.maxParticipants}</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            <span>{room.durationMinutes} min</span>
          </div>
        </div>

        {room.facilitator && (
          <p className="text-xs text-muted-foreground mt-2">
            Facilitator: {room.facilitator.firstName} {room.facilitator.lastName}
          </p>
        )}

        <div className="mt-4 flex gap-2">
          {!isOrganizer && room.status !== 'CLOSED' && (
            <Button
              className="w-full"
              disabled={isFull}
              onClick={onJoin}
            >
              {isFull ? 'Room Full' : 'Join Room'}
            </Button>
          )}
          {isOrganizer && (
            <>
              <Button variant="outline" size="sm">View</Button>
              <Button variant="destructive" size="sm">Close</Button>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
```

---

## Phase 5: Integration Points

### 5.1 Session Page Integration

Add breakout rooms section to the virtual session view for attendees:

```tsx
// In VirtualSessionView.tsx or session page
{session.sessionType === 'BREAKOUT' || breakoutRoomsEnabled ? (
  <Card>
    <CardHeader>
      <CardTitle className="flex items-center gap-2">
        <DoorOpen className="h-5 w-5" />
        Breakout Rooms
      </CardTitle>
    </CardHeader>
    <CardContent>
      <BreakoutRoomList sessionId={session.id} />
    </CardContent>
  </Card>
) : null}
```

### 5.2 Producer Dashboard Integration

Add breakout rooms tab to producer dashboard:

```tsx
// In producer/page.tsx - Add new tab
<TabsTrigger value="breakout" className="flex items-center gap-2">
  <DoorOpen className="h-4 w-4" />
  Breakout Rooms
</TabsTrigger>

<TabsContent value="breakout">
  <BreakoutRoomsControl sessions={sessions} eventId={eventId} />
</TabsContent>
```

---

## Phase 6: Video Integration (Future)

For actual video conferencing in breakout rooms, integrate with:

1. **Daily.co** - Recommended for simplicity
2. **Twilio Video** - Enterprise option
3. **LiveKit** - Open source option

The `videoRoomId` and `videoRoomUrl` fields in the model support this integration.

Initial implementation will use the existing session chat within breakout rooms, with video integration as a follow-up.

---

## Implementation Order

### Step 1: Database (Day 1)
- [ ] Add Prisma models to real-time-service
- [ ] Run migration: `npx prisma migrate dev --name add_breakout_rooms`
- [ ] Update UserReference relations

### Step 2: Backend Service (Day 1-2)
- [ ] Create breakout module structure
- [ ] Implement BreakoutService with CRUD operations
- [ ] Implement BreakoutGateway with WebSocket handlers
- [ ] Add timer management with scheduled jobs
- [ ] Register module in app.module.ts

### Step 3: Frontend - Organizer (Day 2-3)
- [ ] Create breakout-rooms management page
- [ ] Create CreateBreakoutRoomModal component
- [ ] Create BreakoutRoomCard component
- [ ] Add breakout tab to producer dashboard

### Step 4: Frontend - Attendee (Day 3-4)
- [ ] Create attendee breakout room listing page
- [ ] Create BreakoutRoomView for inside-room experience
- [ ] Add BreakoutTimer component
- [ ] Integrate with virtual session view

### Step 5: Polish (Day 4)
- [ ] Add recall functionality
- [ ] Add auto-assign option
- [ ] Test end-to-end flow
- [ ] Add loading states and error handling

---

## Files to Create/Modify

### New Files
1. `real-time-service/src/networking/breakout/breakout.module.ts`
2. `real-time-service/src/networking/breakout/breakout.gateway.ts`
3. `real-time-service/src/networking/breakout/breakout.service.ts`
4. `real-time-service/src/networking/breakout/dto/*.ts`
5. `globalconnect/src/app/(platform)/dashboard/events/[eventId]/sessions/[sessionId]/breakout-rooms/page.tsx`
6. `globalconnect/src/components/features/breakout/*.tsx`

### Modified Files
1. `real-time-service/prisma/schema.prisma` - Add models
2. `real-time-service/src/app.module.ts` - Register module
3. `globalconnect/src/app/(platform)/dashboard/events/[eventId]/producer/page.tsx` - Add tab
4. `globalconnect/src/components/features/virtual-session/VirtualSessionView.tsx` - Add breakout section

---

## Permissions Required

Add to `user-and-org-service/seed.ts`:

```typescript
{ name: 'breakout:manage', description: 'Can create, close, and manage breakout rooms' },
{ name: 'breakout:join', description: 'Can join breakout rooms' },
```

Assign `breakout:manage` to OWNER, ADMIN, MODERATOR roles.
Assign `breakout:join` to all roles including ATTENDEE.
