# Frontend Roadmap - Engagement Conductor Dashboard
## Detailed Implementation Guide

**Location:** `/frontend/src/features/engagement-conductor/`
**Framework:** React + TypeScript
**State Management:** React Context / Redux (use existing pattern)
**Real-time:** Socket.io (existing WebSocket infrastructure)

---

## 📁 Project Structure

```
frontend/src/features/engagement-conductor/
├── index.ts                              # Public exports
├── EngagementDashboard.tsx               # Main dashboard component
├── components/
│   ├── EngagementScoreCard.tsx           # Big number display
│   ├── EngagementChart.tsx               # Line chart (Chart.js)
│   ├── SignalCards.tsx                   # Chat, polls, users cards
│   ├── AnomalyAlert.tsx                  # Alert when anomaly detected
│   ├── InterventionSuggestion.tsx        # Intervention approval card
│   ├── AgentActivityFeed.tsx             # History of interventions
│   ├── AgentModeToggle.tsx               # Manual/Semi-Auto/Auto
│   ├── AgentStatus.tsx                   # Status indicator
│   ├── DecisionExplainer.tsx             # Why agent made decision
│   ├── AIBadge.tsx                       # "AI-generated" badge
│   └── OnboardingTour.tsx                # First-time user tour
├── hooks/
│   ├── useEngagementStream.ts            # WebSocket connection
│   ├── useInterventions.ts               # Intervention API calls
│   ├── useAgentControl.ts                # Agent mode control
│   └── useEngagementHistory.ts           # Historical data
├── types/
│   ├── index.ts                          # Type definitions
│   ├── engagement.ts
│   ├── anomaly.ts
│   └── intervention.ts
├── utils/
│   ├── anomalyHelpers.ts                 # Anomaly formatting
│   ├── chartHelpers.ts                   # Chart configuration
│   └── formatters.ts                     # Number/time formatting
├── api/
│   ├── interventionApi.ts                # API client for interventions
│   └── agentApi.ts                       # API client for agent control
├── demo/
│   └── simulator.ts                      # Demo mode simulator
└── styles/
    └── EngagementDashboard.module.css    # Component styles
```

---

## Phase 0: Setup (Tasks 0.6 - 0.8)

### Task 0.6: Create Component Structure ⬜

**Create directories:**
```bash
cd frontend/src/features
mkdir -p engagement-conductor/{components,hooks,types,utils,api,demo,styles}
```

**File:** `frontend/src/features/engagement-conductor/index.ts`

```typescript
export { EngagementDashboard } from './EngagementDashboard';
export * from './types';
```

**File:** `frontend/src/features/engagement-conductor/types/index.ts`

```typescript
// Re-export all types
export * from './engagement';
export * from './anomaly';
export * from './intervention';
```

**File:** `frontend/src/features/engagement-conductor/types/engagement.ts`

```typescript
export interface EngagementSignals {
  chat_msgs_per_min: number;
  poll_participation: number;
  active_users: number;
  reactions_per_min: number;
  user_leave_rate: number;
}

export interface EngagementData {
  timestamp: string;
  score: number;
  signals: EngagementSignals;
  sessionId: string;
  eventId: string;
}

export interface EngagementHistory {
  data: EngagementData[];
  latestScore: number;
  trend: 'up' | 'down' | 'stable';
}
```

**File:** `frontend/src/features/engagement-conductor/types/anomaly.ts`

```typescript
export type AnomalyType =
  | 'SUDDEN_DROP'
  | 'GRADUAL_DECLINE'
  | 'LOW_ENGAGEMENT'
  | 'MASS_EXIT'
  | 'INSUFFICIENT_DATA'
  | 'UNKNOWN';

export type AnomalySeverity = 'WARNING' | 'CRITICAL';

export interface Anomaly {
  sessionId: string;
  type: AnomalyType;
  severity: AnomalySeverity;
  anomalyScore: number;
  currentEngagement: number;
  expectedEngagement: number;
  deviation: number;
  signals: EngagementSignals;
  timestamp: string;
}
```

**File:** `frontend/src/features/engagement-conductor/types/intervention.ts`

```typescript
export type InterventionType = 'POLL' | 'CHAT_PROMPT' | 'NUDGE' | 'QNA_PROMOTE';

export type InterventionStatus = 'SUGGESTED' | 'APPROVED' | 'EXECUTED' | 'COMPLETED' | 'DISMISSED';

export interface Intervention {
  id: string;
  sessionId: string;
  type: InterventionType;
  status: InterventionStatus;
  confidence: number;
  reasoning: string;
  params: Record<string, any>;
  timestamp: string;
  outcome?: InterventionOutcome;
}

export interface InterventionOutcome {
  success: boolean;
  engagementBefore: number;
  engagementAfter: number;
  delta: number;
  timestamp: string;
}

export interface InterventionSuggestion {
  intervention: Intervention;
  contextKey: string;
  reasoning: string;
}
```

**Verification:** Types compile without errors

---

### Task 0.7: WebSocket Hook ⬜

**File:** `frontend/src/features/engagement-conductor/hooks/useEngagementStream.ts`

```typescript
import { useEffect, useState, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';
import { EngagementData, Anomaly } from '../types';

interface UseEngagementStreamProps {
  sessionId: string;
  enabled?: boolean;
}

interface UseEngagementStreamReturn {
  currentEngagement: number;
  engagementHistory: EngagementData[];
  latestAnomaly: Anomaly | null;
  isConnected: boolean;
  error: string | null;
}

export const useEngagementStream = ({
  sessionId,
  enabled = true,
}: UseEngagementStreamProps): UseEngagementStreamReturn => {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [currentEngagement, setCurrentEngagement] = useState<number>(0);
  const [engagementHistory, setEngagementHistory] = useState<EngagementData[]>([]);
  const [latestAnomaly, setLatestAnomaly] = useState<Anomaly | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled || !sessionId) return;

    // Connect to real-time service (adjust URL based on your setup)
    const socketConnection = io('http://localhost:3000', {
      query: { sessionId },
      transports: ['websocket'],
    });

    socketConnection.on('connect', () => {
      console.log('✅ Connected to engagement stream');
      setIsConnected(true);
      setError(null);

      // Subscribe to engagement updates
      socketConnection.emit('subscribe:engagement', { sessionId });
    });

    socketConnection.on('disconnect', () => {
      console.log('❌ Disconnected from engagement stream');
      setIsConnected(false);
    });

    socketConnection.on('connect_error', (err) => {
      console.error('Connection error:', err);
      setError(err.message);
    });

    // Listen for engagement updates (every 5 seconds)
    socketConnection.on('engagement:update', (data: EngagementData) => {
      setCurrentEngagement(data.score);
      setEngagementHistory((prev) => {
        const updated = [...prev, data];
        // Keep last 5 minutes (60 data points at 5s intervals)
        return updated.slice(-60);
      });
    });

    // Listen for anomaly detections
    socketConnection.on('anomaly:detected', (anomaly: Anomaly) => {
      setLatestAnomaly(anomaly);
    });

    setSocket(socketConnection);

    return () => {
      socketConnection.disconnect();
    };
  }, [sessionId, enabled]);

  return {
    currentEngagement,
    engagementHistory,
    latestAnomaly,
    isConnected,
    error,
  };
};
```

**Verification:** Hook compiles, can create socket connection

---

### Task 0.8: Base Dashboard Layout ⬜

**File:** `frontend/src/features/engagement-conductor/EngagementDashboard.tsx`

```typescript
import React from 'react';
import { useEngagementStream } from './hooks/useEngagementStream';
import styles from './styles/EngagementDashboard.module.css';

interface EngagementDashboardProps {
  sessionId: string;
  eventId: string;
}

export const EngagementDashboard: React.FC<EngagementDashboardProps> = ({
  sessionId,
  eventId,
}) => {
  const {
    currentEngagement,
    engagementHistory,
    latestAnomaly,
    isConnected,
    error,
  } = useEngagementStream({ sessionId, enabled: true });

  if (error) {
    return (
      <div className={styles.errorState}>
        <h3>❌ Connection Error</h3>
        <p>{error}</p>
        <button onClick={() => window.location.reload()}>Retry</button>
      </div>
    );
  }

  if (!isConnected) {
    return (
      <div className={styles.loadingState}>
        <div className={styles.spinner} />
        <p>Connecting to Engagement Conductor...</p>
      </div>
    );
  }

  return (
    <div className={styles.dashboard}>
      {/* Header */}
      <div className={styles.header}>
        <h2>🤖 Engagement Conductor</h2>
        <div className={styles.statusIndicator}>
          <div className={`${styles.statusDot} ${styles.monitoring}`} />
          <span>Monitoring</span>
        </div>
      </div>

      {/* Main Content */}
      <div className={styles.mainContent}>
        <div className={styles.scoreSection}>
          <h3>Current Engagement</h3>
          <div className={styles.scorePlaceholder}>
            {currentEngagement > 0 ? (
              <span>{(currentEngagement * 100).toFixed(0)}%</span>
            ) : (
              <span>--</span>
            )}
          </div>
        </div>

        <div className={styles.chartSection}>
          <h3>Engagement Over Time</h3>
          <div className={styles.chartPlaceholder}>
            {engagementHistory.length > 0 ? (
              <p>{engagementHistory.length} data points collected</p>
            ) : (
              <p>Collecting data...</p>
            )}
          </div>
        </div>

        <div className={styles.signalsSection}>
          <h3>Live Signals</h3>
          <div className={styles.signalsPlaceholder}>
            <p>Signal cards will appear here</p>
          </div>
        </div>
      </div>
    </div>
  );
};
```

**File:** `frontend/src/features/engagement-conductor/styles/EngagementDashboard.module.css`

```css
.dashboard {
  padding: 24px;
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e5e7eb;
}

.header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #111827;
}

.statusIndicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #6b7280;
}

.statusDot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  animation: pulse 2s infinite;
}

.statusDot.monitoring {
  background-color: #10b981;
}

.statusDot.intervening {
  background-color: #f59e0b;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.mainContent {
  display: grid;
  gap: 24px;
}

.scoreSection,
.chartSection,
.signalsSection {
  background: #f9fafb;
  padding: 20px;
  border-radius: 8px;
}

.scoreSection h3,
.chartSection h3,
.signalsSection h3 {
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: 500;
  color: #374151;
}

.scorePlaceholder {
  text-align: center;
  padding: 40px;
  background: white;
  border-radius: 8px;
  font-size: 48px;
  font-weight: 700;
  color: #6b7280;
}

.chartPlaceholder,
.signalsPlaceholder {
  background: white;
  border-radius: 8px;
  padding: 40px;
  text-align: center;
  color: #9ca3af;
}

.loadingState,
.errorState {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  padding: 40px;
}

.spinner {
  width: 48px;
  height: 48px;
  border: 4px solid #e5e7eb;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.loadingState p,
.errorState p {
  color: #6b7280;
  margin: 8px 0;
}

.errorState h3 {
  color: #ef4444;
  margin: 0 0 16px 0;
}

.errorState button {
  margin-top: 16px;
  padding: 8px 16px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.errorState button:hover {
  background: #2563eb;
}
```

**Verification:**
- Dashboard renders with "Connecting..." state
- Once connected, shows "Monitoring" status
- Placeholder sections visible

---

## Phase 1: Signal Collection (Tasks 1.7 - 1.10)

### Task 1.7: Engagement Score Display ⬜

**File:** `frontend/src/features/engagement-conductor/components/EngagementScoreCard.tsx`

```typescript
import React from 'react';
import styles from './EngagementScoreCard.module.css';

interface EngagementScoreCardProps {
  score: number;
  trend?: 'up' | 'down' | 'stable';
}

export const EngagementScoreCard: React.FC<EngagementScoreCardProps> = ({
  score,
  trend = 'stable',
}) => {
  const getScoreClass = () => {
    if (score > 0.7) return styles.excellent;
    if (score > 0.5) return styles.fair;
    return styles.low;
  };

  const getScoreLabel = () => {
    if (score > 0.7) return '🎉 Excellent';
    if (score > 0.5) return '⚠️ Fair';
    return '🚨 Low';
  };

  const getTrendIcon = () => {
    if (trend === 'up') return '📈';
    if (trend === 'down') return '📉';
    return '➡️';
  };

  return (
    <div className={styles.card}>
      <div className={styles.label}>Current Engagement</div>
      <div className={`${styles.scoreValue} ${getScoreClass()}`}>
        {(score * 100).toFixed(0)}%
      </div>
      <div className={styles.scoreIndicator}>
        <span className={`${styles.badge} ${getScoreClass()}`}>
          {getScoreLabel()}
        </span>
        <span className={styles.trend}>{getTrendIcon()}</span>
      </div>
    </div>
  );
};
```

**File:** `frontend/src/features/engagement-conductor/components/EngagementScoreCard.module.css`

```css
.card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 32px;
  border-radius: 16px;
  box-shadow: 0 4px 16px rgba(102, 126, 234, 0.3);
}

.label {
  font-size: 14px;
  opacity: 0.9;
  margin-bottom: 8px;
  font-weight: 500;
}

.scoreValue {
  font-size: 72px;
  font-weight: 700;
  line-height: 1;
  margin-bottom: 16px;
}

.scoreValue.excellent {
  color: #10b981;
}

.scoreValue.fair {
  color: #f59e0b;
}

.scoreValue.low {
  color: #ef4444;
}

.scoreIndicator {
  display: flex;
  align-items: center;
  gap: 12px;
}

.badge {
  display: inline-block;
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 600;
}

.badge.excellent {
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
}

.badge.fair {
  background: rgba(245, 158, 11, 0.2);
  color: #f59e0b;
}

.badge.low {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.trend {
  font-size: 20px;
}
```

**Integration:** Update EngagementDashboard.tsx to use EngagementScoreCard

**Verification:** Score displays with correct color/badge based on value

---

### Task 1.8 - 1.10: [Will be detailed when we start Phase 1]

---

## Phase 2: Anomaly Detection (Tasks 2.6 - 2.8)

### Task 2.6 - 2.8: [Will be detailed when we start Phase 2]

---

## Phase 3: Basic Intervention (Tasks 3.8 - 3.12)

### Task 3.8 - 3.12: [Will be detailed when we start Phase 3]

---

## Phase 4: LLM Integration (Tasks 4.5 - 4.6)

### Task 4.5 - 4.6: [Will be detailed when we start Phase 4]

---

## Phase 5: Full Agent Loop (Tasks 5.7 - 5.10)

### Task 5.7 - 5.10: [Will be detailed when we start Phase 5]

---

## Phase 6: Polish & Demo (Tasks 6.4 - 6.7)

### Task 6.4 - 6.7: [Will be detailed when we start Phase 6]

---

## Dependencies to Install

```bash
cd frontend

# Chart library
npm install react-chartjs-2 chart.js

# Socket.io client (if not already installed)
npm install socket.io-client

# Date utilities
npm install date-fns

# Toast notifications (for agent actions)
npm install react-hot-toast

# Icons (if not using existing icon library)
npm install lucide-react
```

---

## Integration with Existing App

**Add route:** (Location depends on your routing setup)

```typescript
// In your routes file
import { EngagementDashboard } from '@/features/engagement-conductor';

// Add route
{
  path: '/events/:eventId/sessions/:sessionId/engagement',
  element: <EngagementDashboard sessionId={sessionId} eventId={eventId} />
}
```

**Add to session dashboard:** (Show engagement conductor in organizer view)

```typescript
// In session organizer view
<Tab label="Engagement Conductor">
  <EngagementDashboard sessionId={sessionId} eventId={eventId} />
</Tab>
```

---

## Testing Strategy

For each component:

1. **Visual Tests**: Renders correctly with different props
2. **Interaction Tests**: Buttons/controls work as expected
3. **Real-time Tests**: Updates correctly when WebSocket data arrives

**Example test:**
```typescript
// EngagementScoreCard.test.tsx
import { render, screen } from '@testing-library/react';
import { EngagementScoreCard } from './EngagementScoreCard';

describe('EngagementScoreCard', () => {
  it('shows excellent badge for high score', () => {
    render(<EngagementScoreCard score={0.85} />);
    expect(screen.getByText('🎉 Excellent')).toBeInTheDocument();
  });

  it('shows low badge for low score', () => {
    render(<EngagementScoreCard score={0.35} />);
    expect(screen.getByText('🚨 Low')).toBeInTheDocument();
  });
});
```

---

**Next Steps:** Complete Phase 0 tasks, then move to Phase 1.
