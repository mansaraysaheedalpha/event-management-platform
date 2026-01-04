# The Engagement Conductor: Blueprint for Launch
## Your "I Can Never Go Back" Agent

**Status:** Implementation Blueprint
**Priority:** P0 - Launch Agent
**Timeline:** 8-12 weeks to MVP
**Goal:** Create the most intelligent real-time event engagement system in the world

---

## Executive Summary

The **Engagement Conductor** is an autonomous AI agent that monitors live event sessions in real-time, detects engagement drops within seconds, and intervenes automatically with contextually appropriate actions (polls, discussion prompts, nudges) to restore and optimize attendee engagement.

### The "Wow" Moment

```
[Live Conference Session - 2:23 PM]

Organizer Dashboard:
├── 📊 Engagement Score: 0.78 → 0.54 → 0.48 (dropping fast)
├── ⚠️  Alert: "Engagement declining rapidly"
├── 🤖 Agent: "Intervention initiated - launching topic poll"
│
[2 seconds later]
│
├── 💬 Chat: Poll appears - "Which AI technique interests you most?"
├── 📈 Participation: 47% of attendees vote within 30 seconds
├── 💡 Chat lights up with discussion
├── 📊 Engagement Score: 0.48 → 0.67 → 0.82 (recovered!)
└── ✅ Agent: "Engagement restored. Session healthy."

Organizer thinks: "It just saved my session. I didn't lift a finger."
```

**That's the moment. That's the magic. That's why they'll never leave.**

---

## Why This Agent Wins

### 1. Real-Time Visibility
- Organizers *watch* it work in live dashboards
- Impact is immediate and measurable
- Creates "campfire stories" - organizers tell others about the AI that saved their event

### 2. Low Risk, High Value
- **Downside risk:** Minimal (worst case: unnecessary poll)
- **Upside value:** Massive (saved sessions = saved reputation)
- No financial risk, no data privacy concerns

### 3. Unique Differentiation
- Competitors have "analytics dashboards" (reactive, lagging)
- You have "AI that intervenes" (proactive, real-time)
- This doesn't exist anywhere else

### 4. Gateway to Full Agent Suite
- Once organizers trust this agent, they'll trust:
  - Content Maestro to write descriptions
  - Event Strategist to plan events
  - Revenue Maximizer to optimize pricing
- It's the trust builder

### 5. Leverages Your Existing Infrastructure
- You already have WebSockets, chat, polls, Q&A, reactions
- This agent is the intelligence layer connecting them
- Low infrastructure investment, high impact

---

## System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     ENGAGEMENT CONDUCTOR                     │
└───────────────────┬─────────────────────────────────────────┘
                    │
        ┌───────────┼───────────┐
        │           │           │
   ┌────▼────┐ ┌───▼────┐ ┌───▼────┐
   │ PERCEIVE│ │ DECIDE │ │  ACT   │
   └────┬────┘ └───┬────┘ └───┬────┘
        │          │          │
        │          │          │
┌───────▼──────────▼──────────▼──────────────────────────┐
│              INTELLIGENCE SUBSTRATE                      │
│  ┌────────────┐  ┌──────────┐  ┌─────────────┐        │
│  │ Stream     │  │ ML       │  │ Context     │        │
│  │ Analytics  │  │ Models   │  │ Store       │        │
│  └────────────┘  └──────────┘  └─────────────┘        │
└──────────────────────┬───────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────┐
│              REAL-TIME DATA LAYER                         │
│  ┌─────────┐ ┌──────────┐ ┌───────┐ ┌──────────┐       │
│  │ Chat    │ │ Polls    │ │ Q&A   │ │ Reactions│       │
│  │ Gateway │ │ Gateway  │ │Gateway│ │ Gateway  │       │
│  └─────────┘ └──────────┘ └───────┘ └──────────┘       │
└──────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. Perception Engine (Real-Time Signal Aggregation)

**Purpose:** Continuously monitor all engagement signals and compute engagement score

**Input Signals:**
```typescript
interface EngagementSignals {
  // Direct interaction signals
  chat_messages_per_minute: number;
  poll_participation_rate: number;
  qna_questions_submitted: number;
  reactions_per_minute: number;

  // Attention signals
  active_users_count: number;
  user_presence_duration: number;  // How long users stay
  tab_focus_rate: number;          // % of users with tab in focus

  // Behavioral signals
  user_join_rate: number;          // New users joining
  user_leave_rate: number;         // Users dropping off
  message_response_time: number;   // How fast people respond

  // Content signals
  speaker_pace: number;            // Words per minute (from transcription)
  slide_transition_rate: number;   // Slides per minute

  // Context
  session_phase: 'opening' | 'middle' | 'closing' | 'qa';
  session_duration_elapsed: number;
  expected_engagement_baseline: number;  // Based on similar sessions
}
```

**Engagement Score Formula:**
```typescript
function calculateEngagementScore(signals: EngagementSignals): number {
  // Weighted composite score (0-1 scale)
  const score = (
    signals.chat_messages_per_minute * 0.25 +
    signals.poll_participation_rate * 0.30 +
    signals.active_users_count * 0.20 +
    signals.reactions_per_minute * 0.15 +
    (1 - signals.user_leave_rate) * 0.10
  ) / weights_sum;

  // Normalize to baseline (account for session type)
  const normalized = score / signals.expected_engagement_baseline;

  return Math.min(normalized, 1.0);
}
```

**Technology:**
- **Apache Flink / Kafka Streams** for real-time stream processing
- **Redis Streams** for event buffering
- **TimescaleDB** for time-series data storage

---

#### 2. Decision Engine (AI Brain)

**Purpose:** Analyze engagement patterns, detect anomalies, and decide when/how to intervene

**Architecture:**

```python
class EngagementDecisionEngine:
    def __init__(self):
        self.anomaly_detector = AnomalyDetector()
        self.intervention_selector = InterventionSelector()
        self.context_builder = ContextBuilder()
        self.confidence_calculator = ConfidenceCalculator()

    async def decide(
        self,
        current_signals: EngagementSignals,
        historical_signals: List[EngagementSignals],
        session_context: SessionContext
    ) -> Optional[InterventionDecision]:

        # Step 1: Detect if intervention is needed
        anomaly = await self.anomaly_detector.detect(
            current=current_signals,
            history=historical_signals
        )

        if not anomaly or anomaly.severity < 0.7:
            return None  # No intervention needed

        # Step 2: Build rich context
        context = await self.context_builder.build(
            session_context=session_context,
            signals=current_signals,
            anomaly=anomaly
        )

        # Step 3: Select optimal intervention
        intervention = await self.intervention_selector.select(
            context=context,
            anomaly=anomaly,
            available_actions=['POLL', 'CHAT_PROMPT', 'NUDGE', 'QNA_PROMOTE']
        )

        # Step 4: Calculate confidence
        confidence = await self.confidence_calculator.calculate(
            intervention=intervention,
            context=context
        )

        return InterventionDecision(
            action=intervention,
            confidence=confidence,
            reasoning=self._explain_decision(context, intervention)
        )
```

**Key AI Models:**

##### A. Anomaly Detection Model
**Purpose:** Detect engagement drops before they become critical

**Approach:** Time-series anomaly detection using:
- **Statistical Methods:** Z-score, EWMA (Exponential Weighted Moving Average)
- **ML Methods:** Isolation Forest, LSTM Autoencoders

```python
from river import anomaly, preprocessing
from river import compose

# Online learning anomaly detector
model = compose.Pipeline(
    preprocessing.StandardScaler(),
    anomaly.HalfSpaceTrees(n_trees=10, height=8, window_size=100)
)

# Update model with every new engagement score
for timestamp, score in engagement_stream:
    anomaly_score = model.score_one({'engagement': score})
    model.learn_one({'engagement': score})

    if anomaly_score > threshold:
        trigger_intervention()
```

**Why River:** Online learning library perfect for streaming data

##### B. Intervention Selection Model
**Purpose:** Choose the right intervention for the context

**Approach:** Multi-Armed Bandit (Thompson Sampling)

```python
from scipy.stats import beta

class ThompsonSamplingSelector:
    def __init__(self):
        # Track success/failure for each intervention type
        self.interventions = {
            'POLL': {'success': 1, 'failure': 1},  # Beta prior
            'CHAT_PROMPT': {'success': 1, 'failure': 1},
            'NUDGE': {'success': 1, 'failure': 1},
            'QNA_PROMOTE': {'success': 1, 'failure': 1}
        }

    def select(self, context: dict) -> str:
        # Sample from Beta distributions
        samples = {}
        for intervention, stats in self.interventions.items():
            # Check if intervention is applicable in context
            if not self._is_applicable(intervention, context):
                continue

            # Thompson sampling: sample from posterior
            samples[intervention] = beta.rvs(
                stats['success'],
                stats['failure']
            )

        # Select intervention with highest sample
        return max(samples, key=samples.get)

    def update(self, intervention: str, success: bool):
        """Update model after observing outcome"""
        if success:
            self.interventions[intervention]['success'] += 1
        else:
            self.interventions[intervention]['failure'] += 1
```

**Why Thompson Sampling:**
- Automatically balances exploration/exploitation
- Learns which interventions work in which contexts
- Gets smarter with every event

##### C. Context Understanding Model
**Purpose:** Build rich semantic understanding of session context

**Approach:** Use LLM (GPT-4o-mini / Claude 3.5 Haiku) for fast context analysis

```python
import anthropic

class ContextBuilder:
    def __init__(self):
        self.client = anthropic.Anthropic()

    async def build(
        self,
        session_context: SessionContext,
        signals: EngagementSignals,
        anomaly: Anomaly
    ) -> RichContext:

        # Build prompt with all available context
        prompt = f"""You are analyzing engagement in a live event session.

Session Details:
- Title: {session_context.title}
- Description: {session_context.description}
- Current speaker: {session_context.speaker}
- Duration elapsed: {session_context.elapsed_minutes} minutes
- Session phase: {session_context.phase}

Current State:
- Engagement score: {signals.engagement_score} (down from {signals.baseline})
- Chat activity: {signals.chat_messages_per_minute} msgs/min
- Active users: {signals.active_users_count}
- Recent chat messages: {self._get_recent_chat(session_context.session_id)}

Anomaly Detected:
- Type: {anomaly.type}
- Severity: {anomaly.severity}
- Description: {anomaly.description}

Based on this context, provide:
1. Why might engagement be dropping? (2-3 specific hypotheses)
2. What topic or question would re-engage attendees?
3. What intervention type would be most effective? (poll, discussion prompt, Q&A)

Respond in JSON format."""

        response = await self.client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=500,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}]
        )

        analysis = json.loads(response.content[0].text)

        return RichContext(
            hypotheses=analysis['hypotheses'],
            suggested_topic=analysis['topic'],
            recommended_intervention=analysis['intervention'],
            raw_analysis=analysis
        )
```

**Why Haiku:** Fast (<3s response), cheap ($0.25/million tokens), good enough for context understanding

---

#### 3. Action Engine (Intervention Execution)

**Purpose:** Execute interventions across multiple channels

**Intervention Types:**

##### A. Intelligent Poll Launch

```typescript
interface PollIntervention {
  type: 'POLL';
  question: string;
  options: string[];
  timing: 'IMMEDIATE' | 'NEXT_TRANSITION';
  display_duration: number;
  reason: string;
}

class PollInterventionExecutor {
  async execute(
    sessionId: string,
    intervention: PollIntervention
  ): Promise<InterventionResult> {

    // Generate contextual poll using LLM
    const poll = await this.generatePoll(sessionId, intervention);

    // Create poll via existing polls gateway
    const pollId = await this.pollsService.createPoll({
      sessionId,
      question: poll.question,
      options: poll.options,
      createdBy: 'AGENT',
      autoLaunch: true,
      displayDuration: intervention.display_duration
    });

    // Broadcast to all attendees via WebSocket
    this.socketServer.to(`session:${sessionId}`).emit('poll.launched', {
      pollId,
      question: poll.question,
      options: poll.options,
      agentMessage: '🤖 Quick check-in from your AI assistant!'
    });

    // Monitor outcome
    const outcome = await this.monitorPollOutcome(pollId, sessionId);

    return {
      interventionId: generateId(),
      type: 'POLL',
      pollId,
      outcome,
      timestamp: new Date()
    };
  }

  private async generatePoll(
    sessionId: string,
    intervention: PollIntervention
  ): Promise<GeneratedPoll> {

    const session = await this.getSession(sessionId);
    const recentChat = await this.getRecentChat(sessionId);

    const prompt = `Generate an engaging poll question for this session:

Session: "${session.title}"
Current topic: ${session.current_topic}
Recent chat discussion: ${recentChat}

Create a poll that:
1. Relates to the current topic
2. Has 3-4 clear, distinct options
3. Encourages participation
4. Sparks discussion

Format:
{
  "question": "...",
  "options": ["...", "...", "..."]
}`;

    const response = await this.llm.generate(prompt);
    return JSON.parse(response);
  }
}
```

##### B. Chat Discussion Prompt

```typescript
interface ChatPromptIntervention {
  type: 'CHAT_PROMPT';
  message: string;
  isPinned: boolean;
  mentionMode: 'BROADCAST' | 'TARGETED';
  targetUsers?: string[];
}

class ChatPromptExecutor {
  async execute(
    sessionId: string,
    intervention: ChatPromptIntervention
  ): Promise<InterventionResult> {

    // Generate contextual prompt
    const prompt = await this.generatePrompt(sessionId);

    // Send via chat gateway
    await this.chatGateway.sendAgentMessage({
      sessionId,
      content: prompt.message,
      type: 'AGENT_PROMPT',
      metadata: {
        agentName: 'Engagement Conductor',
        icon: '🤖',
        isPinned: intervention.isPinned,
        style: 'highlighted'  // Special styling for agent messages
      }
    });

    // If targeted, also send DMs
    if (intervention.mentionMode === 'TARGETED' && intervention.targetUsers) {
      await this.sendTargetedNudges(intervention.targetUsers, prompt);
    }

    // Monitor response
    const outcome = await this.monitorChatResponse(sessionId);

    return {
      interventionId: generateId(),
      type: 'CHAT_PROMPT',
      outcome,
      timestamp: new Date()
    };
  }

  private async generatePrompt(sessionId: string): Promise<GeneratedPrompt> {
    const session = await this.getSession(sessionId);
    const context = await this.contextBuilder.build(sessionId);

    const prompt = `Generate a discussion prompt for this session:

Session: "${session.title}"
Context: ${context.summary}
Goal: Re-engage attendees who seem passive

Create a prompt that:
1. Asks an open-ended question
2. Relates to practical application
3. Encourages sharing experiences
4. Is conversational and friendly

Example: "💡 Quick question: How are you currently handling [topic] in your work? Any interesting approaches?"

Your prompt:`;

    const response = await this.llm.generate(prompt);
    return { message: response };
  }
}
```

##### C. Intelligent Nudges (Personalized Notifications)

```typescript
interface NudgeIntervention {
  type: 'NUDGE';
  targetSegment: 'DISENGAGED' | 'LURKERS' | 'FIRST_TIME';
  message: string;
  action: {
    type: 'POLL' | 'QUESTION' | 'REACTION';
    cta: string;
  };
}

class NudgeExecutor {
  async execute(
    sessionId: string,
    intervention: NudgeIntervention
  ): Promise<InterventionResult> {

    // Identify target users
    const targetUsers = await this.identifyTargetUsers(
      sessionId,
      intervention.targetSegment
    );

    // Send personalized nudges
    const results = await Promise.all(
      targetUsers.map(user => this.sendPersonalizedNudge(user, intervention))
    );

    return {
      interventionId: generateId(),
      type: 'NUDGE',
      targetCount: targetUsers.length,
      outcome: this.aggregateOutcomes(results),
      timestamp: new Date()
    };
  }

  private async identifyTargetUsers(
    sessionId: string,
    segment: string
  ): Promise<User[]> {

    const analytics = await this.analyticsService.getSessionAnalytics(sessionId);

    switch (segment) {
      case 'DISENGAGED':
        // Users who haven't interacted in 10+ minutes
        return analytics.users.filter(u =>
          u.lastInteraction < Date.now() - 600000 &&
          u.presenceDuration > 300000  // Still in session
        );

      case 'LURKERS':
        // Users who never interact but are present
        return analytics.users.filter(u =>
          u.totalInteractions === 0 &&
          u.presenceDuration > 900000  // 15+ minutes
        );

      case 'FIRST_TIME':
        // First-time attendees in their first session
        return analytics.users.filter(u => u.isFirstSession);

      default:
        return [];
    }
  }

  private async sendPersonalizedNudge(
    user: User,
    intervention: NudgeIntervention
  ): Promise<NudgeResult> {

    // Personalize message
    const personalizedMessage = intervention.message
      .replace('{{name}}', user.firstName)
      .replace('{{action}}', intervention.action.cta);

    // Send in-app notification
    await this.notificationService.send({
      userId: user.id,
      type: 'ENGAGEMENT_NUDGE',
      title: '👋 Jump back in!',
      message: personalizedMessage,
      action: {
        label: intervention.action.cta,
        onClick: this.getActionHandler(intervention.action.type)
      },
      priority: 'MEDIUM',
      expiresIn: 300  // 5 minutes
    });

    return { userId: user.id, sent: true };
  }
}
```

##### D. Q&A Promotion

```typescript
interface QnAPromotionIntervention {
  type: 'QNA_PROMOTE';
  strategy: 'SURFACE_BEST' | 'REQUEST_NEW' | 'SEED_QUESTION';
  count?: number;
}

class QnAPromotionExecutor {
  async execute(
    sessionId: string,
    intervention: QnAPromotionIntervention
  ): Promise<InterventionResult> {

    switch (intervention.strategy) {
      case 'SURFACE_BEST':
        // Surface high-quality unanswered questions
        return await this.surfaceBestQuestions(sessionId, intervention.count || 3);

      case 'REQUEST_NEW':
        // Prompt attendees to ask questions
        return await this.requestNewQuestions(sessionId);

      case 'SEED_QUESTION':
        // Agent generates a seed question to start discussion
        return await this.seedQuestion(sessionId);
    }
  }

  private async surfaceBestQuestions(
    sessionId: string,
    count: number
  ): Promise<InterventionResult> {

    // Get all unanswered questions
    const questions = await this.qnaService.getUnansweredQuestions(sessionId);

    // Rank by quality (using ML model)
    const rankedQuestions = await this.rankQuestions(questions);

    // Surface top N to speaker
    const topQuestions = rankedQuestions.slice(0, count);

    await this.qnaGateway.promoteQuestions({
      sessionId,
      questionIds: topQuestions.map(q => q.id),
      reason: 'AGENT_RECOMMENDATION'
    });

    // Notify speaker
    await this.notificationService.notifySpeaker(sessionId, {
      title: '🤖 AI-Selected Questions',
      message: `${count} high-quality questions flagged for you`,
      questions: topQuestions
    });

    return {
      interventionId: generateId(),
      type: 'QNA_PROMOTE',
      questionsPromoted: count,
      timestamp: new Date()
    };
  }

  private async seedQuestion(sessionId: string): Promise<InterventionResult> {
    const session = await this.getSession(sessionId);
    const context = await this.contextBuilder.build(sessionId);

    // Generate thought-provoking question
    const prompt = `Generate a thought-provoking question for this session:

Session: "${session.title}"
Topic: ${context.currentTopic}
Context: ${context.summary}

Create a question that:
1. Challenges attendees to think deeper
2. Has no obvious answer
3. Sparks debate or discussion
4. Is relevant to practical application

Format: Just the question, no preamble.`;

    const question = await this.llm.generate(prompt);

    // Submit as agent-generated question
    await this.qnaService.createQuestion({
      sessionId,
      content: question,
      authorType: 'AGENT',
      authorName: 'Engagement Conductor',
      metadata: { type: 'SEED_QUESTION' }
    });

    return {
      interventionId: generateId(),
      type: 'QNA_PROMOTE',
      question,
      timestamp: new Date()
    };
  }
}
```

---

## Technology Stack

### Core Infrastructure

```yaml
Real-Time Stream Processing:
  Primary: Apache Kafka + Kafka Streams
  Alternative: Redis Streams (lighter weight, easier to start)
  Why: Need to process 1000s of events/second with low latency

Time-Series Database:
  Choice: TimescaleDB (PostgreSQL extension)
  Why: Familiar SQL, excellent time-series performance, easy integration

In-Memory State:
  Choice: Redis
  Why: Already in your stack, perfect for real-time state

Vector Database (for semantic search):
  Choice: Qdrant
  Why: Open-source, fast, excellent Python SDK
  Alternative: Pinecone (managed, easier but costs more)

Message Queue:
  Choice: Redis Pub/Sub (start) → RabbitMQ (scale)
  Why: Start simple, upgrade when needed
```

### AI/ML Stack

```yaml
LLM Provider:
  Primary: Anthropic Claude 3.5 Haiku
  Fallback: OpenAI GPT-4o-mini
  Why: Haiku is 10x faster, 5x cheaper than GPT-4o-mini for context understanding

  Cost Comparison (per 1M tokens):
  - Haiku: $0.25 input, $1.25 output
  - GPT-4o-mini: $0.15 input, $0.60 output

  Speed Comparison:
  - Haiku: ~2-3s for 500 tokens
  - GPT-4o-mini: ~3-5s for 500 tokens

Online Learning:
  Choice: River (Python)
  Why: Built for streaming data, continuously learning models
  Use: Anomaly detection, engagement prediction

Reinforcement Learning:
  Choice: Custom Thompson Sampling (lightweight)
  Alternative: Ray RLlib (if you need more sophistication)
  Why: Thompson Sampling is simple, effective, interpretable

ML Monitoring:
  Choice: Evidently AI
  Why: Detects model drift, tracks performance, open-source
```

### Agent Framework

```yaml
Agent Orchestration:
  Choice: LangGraph (LangChain)
  Why: Purpose-built for agentic workflows, excellent observability

  Architecture:
  ┌─────────────────────────────────────┐
  │        LangGraph Agent              │
  │                                     │
  │  ┌──────┐    ┌────────┐   ┌─────┐ │
  │  │Perceive───▶│ Decide │──▶│ Act │ │
  │  └──────┘    └────────┘   └─────┘ │
  │      │            │           │     │
  │      └────────────┴───────────┘     │
  │              Learn                  │
  └─────────────────────────────────────┘

Alternative: CrewAI, AutoGen (if multi-agent coordination needed later)

Observability:
  Choice: LangSmith (LangChain observability platform)
  Why: Trace every agent decision, debug issues, monitor performance
  Cost: Free tier generous, paid starts at $39/mo
```

### Development Stack

```python
# requirements.txt for agent-service

# Agent Framework
langgraph==0.2.0
langchain==0.3.0
langchain-anthropic==0.3.0
langsmith==0.3.0

# Streaming & Real-Time
kafka-python==2.0.2
redis==5.0.1
redis-streams==0.1.0

# ML & AI
river==0.21.0  # Online learning
numpy==1.26.0
pandas==2.1.0
scikit-learn==1.3.0
evidently==0.4.0  # ML monitoring

# Time-Series
psycopg2-binary==2.9.9  # PostgreSQL (TimescaleDB)
asyncpg==0.29.0

# Vector DB
qdrant-client==1.7.0

# LLM Providers
anthropic==0.39.0
openai==1.54.0

# Utilities
pydantic==2.5.0
fastapi==0.108.0
uvicorn==0.25.0
celery==5.3.4  # Background tasks
```

---

## Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)

**Goal:** Set up infrastructure and basic signal collection

#### Week 1: Infrastructure Setup

```bash
# Set up agent service
mkdir agent-service
cd agent-service
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set up Redis (if not already running)
docker run -d --name redis -p 6379:6379 redis:7-alpine

# Set up TimescaleDB
docker run -d --name timescaledb \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=yourpassword \
  timescale/timescaledb:latest-pg16

# Initialize database
psql -h localhost -U postgres -d events -f init_timescale.sql
```

```sql
-- init_timescale.sql

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Engagement metrics table
CREATE TABLE engagement_metrics (
  time TIMESTAMPTZ NOT NULL,
  session_id UUID NOT NULL,
  event_id UUID NOT NULL,
  engagement_score FLOAT NOT NULL,
  chat_msgs_per_min FLOAT,
  poll_participation FLOAT,
  active_users INT,
  reactions_per_min FLOAT,
  user_leave_rate FLOAT,
  metadata JSONB
);

-- Convert to hypertable (time-series optimization)
SELECT create_hypertable('engagement_metrics', 'time');

-- Create indexes
CREATE INDEX idx_session_time ON engagement_metrics (session_id, time DESC);
CREATE INDEX idx_engagement_score ON engagement_metrics (engagement_score);

-- Interventions table
CREATE TABLE interventions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL,
  timestamp TIMESTAMPTZ NOT NULL,
  type VARCHAR(50) NOT NULL,
  confidence FLOAT NOT NULL,
  reasoning TEXT,
  outcome JSONB,
  metadata JSONB
);

SELECT create_hypertable('interventions', 'timestamp');

-- Agent performance metrics
CREATE TABLE agent_performance (
  time TIMESTAMPTZ NOT NULL,
  agent_id VARCHAR(100) NOT NULL,
  intervention_type VARCHAR(50) NOT NULL,
  success BOOLEAN NOT NULL,
  engagement_delta FLOAT,
  confidence FLOAT,
  session_id UUID,
  metadata JSONB
);

SELECT create_hypertable('agent_performance', 'time');
```

#### Week 2: Signal Collection Pipeline

```python
# agent-service/app/pipelines/signal_collector.py

import asyncio
import redis.asyncio as redis
from typing import Dict, List
import json
from datetime import datetime

class EngagementSignalCollector:
    """
    Collects real-time signals from multiple WebSocket gateways
    and publishes to Redis Streams for processing
    """

    def __init__(self):
        self.redis = redis.from_url("redis://localhost:6379")
        self.active_sessions: Dict[str, SessionTracker] = {}

    async def start(self):
        """Start listening to all signal sources"""
        await asyncio.gather(
            self.listen_chat_events(),
            self.listen_poll_events(),
            self.listen_presence_events(),
            self.listen_reaction_events(),
            self.compute_engagement_scores()
        )

    async def listen_chat_events(self):
        """Subscribe to chat messages via Redis Pub/Sub"""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe('chat:message:new')

        async for message in pubsub.listen():
            if message['type'] == 'message':
                data = json.loads(message['data'])
                await self.process_chat_event(data)

    async def process_chat_event(self, data: dict):
        session_id = data['sessionId']

        # Update session tracker
        if session_id not in self.active_sessions:
            self.active_sessions[session_id] = SessionTracker(session_id)

        tracker = self.active_sessions[session_id]
        tracker.record_chat_message(data)

        # Publish to engagement stream
        await self.publish_signal(session_id, {
            'type': 'chat',
            'timestamp': datetime.now().isoformat(),
            'value': tracker.get_chat_rate()
        })

    async def listen_presence_events(self):
        """Monitor user presence (join/leave events)"""
        pubsub = self.redis.pubsub()
        await pubsub.psubscribe('session:*:presence')

        async for message in pubsub.listen():
            if message['type'] == 'pmessage':
                data = json.loads(message['data'])
                session_id = data['sessionId']
                event_type = data['type']  # 'join' or 'leave'

                tracker = self.active_sessions.get(session_id)
                if tracker:
                    if event_type == 'join':
                        tracker.record_user_join(data['userId'])
                    else:
                        tracker.record_user_leave(data['userId'])

                    await self.publish_signal(session_id, {
                        'type': 'presence',
                        'timestamp': datetime.now().isoformat(),
                        'active_users': tracker.get_active_users(),
                        'join_rate': tracker.get_join_rate(),
                        'leave_rate': tracker.get_leave_rate()
                    })

    async def compute_engagement_scores(self):
        """Continuously compute engagement scores for all active sessions"""
        while True:
            for session_id, tracker in self.active_sessions.items():
                score = await self.calculate_engagement_score(tracker)

                # Store in TimescaleDB
                await self.store_metric(session_id, score, tracker.get_signals())

                # Publish to engagement stream for agent
                await self.redis.xadd(
                    f'engagement:{session_id}',
                    {
                        'score': score,
                        'signals': json.dumps(tracker.get_signals()),
                        'timestamp': datetime.now().isoformat()
                    },
                    maxlen=1000  # Keep last 1000 scores
                )

            await asyncio.sleep(5)  # Compute every 5 seconds

    async def calculate_engagement_score(
        self,
        tracker: 'SessionTracker'
    ) -> float:
        signals = tracker.get_signals()

        # Weighted formula
        score = (
            signals['chat_msgs_per_min'] * 0.25 +
            signals['poll_participation'] * 0.30 +
            signals['active_users_normalized'] * 0.20 +
            signals['reactions_per_min'] * 0.15 +
            (1 - signals['leave_rate']) * 0.10
        )

        return min(score, 1.0)

    async def publish_signal(self, session_id: str, signal: dict):
        """Publish signal to Redis Stream"""
        await self.redis.xadd(
            f'signals:{session_id}',
            signal,
            maxlen=10000
        )


class SessionTracker:
    """Tracks engagement signals for a single session"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.chat_messages: List[float] = []
        self.active_users: set = set()
        self.poll_responses: Dict[str, int] = {}
        self.reactions: List[float] = []
        self.join_events: List[float] = []
        self.leave_events: List[float] = []
        self.start_time = datetime.now()

    def record_chat_message(self, data: dict):
        self.chat_messages.append(datetime.now().timestamp())

        # Keep only last 5 minutes of messages
        cutoff = datetime.now().timestamp() - 300
        self.chat_messages = [t for t in self.chat_messages if t > cutoff]

    def get_chat_rate(self) -> float:
        """Messages per minute in last 5 minutes"""
        return len(self.chat_messages) / 5.0

    def record_user_join(self, user_id: str):
        self.active_users.add(user_id)
        self.join_events.append(datetime.now().timestamp())

    def record_user_leave(self, user_id: str):
        self.active_users.discard(user_id)
        self.leave_events.append(datetime.now().timestamp())

    def get_active_users(self) -> int:
        return len(self.active_users)

    def get_leave_rate(self) -> float:
        """% of users leaving per minute"""
        recent_leaves = [
            t for t in self.leave_events
            if t > datetime.now().timestamp() - 300
        ]
        if len(self.active_users) == 0:
            return 0.0
        return len(recent_leaves) / max(len(self.active_users), 1) / 5.0

    def get_signals(self) -> dict:
        return {
            'chat_msgs_per_min': self.get_chat_rate(),
            'active_users': self.get_active_users(),
            'active_users_normalized': min(self.get_active_users() / 100, 1.0),
            'leave_rate': self.get_leave_rate(),
            'poll_participation': self.get_poll_participation(),
            'reactions_per_min': self.get_reaction_rate()
        }

    # ... implement poll_participation, reaction_rate similarly
```

---

### Phase 2: Agent Brain (Weeks 3-4)

**Goal:** Build the decision engine with anomaly detection and intervention selection

#### Week 3: Anomaly Detection

```python
# agent-service/app/agents/anomaly_detector.py

import redis.asyncio as redis
from river import anomaly, preprocessing, compose
import json
from typing import Optional, List
from datetime import datetime, timedelta

class AnomalyDetector:
    """
    Detects engagement anomalies using online learning.
    Uses River library for streaming anomaly detection.
    """

    def __init__(self):
        self.redis = redis.from_url("redis://localhost:6379")

        # One model per session (stored in memory)
        self.models: Dict[str, anomaly.HalfSpaceTrees] = {}

        # Thresholds
        self.warning_threshold = 0.6
        self.critical_threshold = 0.8

    def get_or_create_model(self, session_id: str) -> anomaly.HalfSpaceTrees:
        """Get existing model or create new one for session"""
        if session_id not in self.models:
            self.models[session_id] = compose.Pipeline(
                preprocessing.StandardScaler(),
                anomaly.HalfSpaceTrees(
                    n_trees=10,
                    height=8,
                    window_size=100
                )
            )
        return self.models[session_id]

    async def detect(
        self,
        session_id: str,
        current_score: float,
        signals: dict
    ) -> Optional['Anomaly']:
        """
        Detect if current engagement is anomalous.
        Returns Anomaly object if detected, None otherwise.
        """

        model = self.get_or_create_model(session_id)

        # Prepare features
        features = {
            'engagement_score': current_score,
            'chat_rate': signals['chat_msgs_per_min'],
            'active_users': signals['active_users_normalized'],
            'leave_rate': signals['leave_rate']
        }

        # Get anomaly score
        anomaly_score = model.score_one(features)

        # Update model with this observation
        model.learn_one(features)

        # Check if anomalous
        if anomaly_score > self.critical_threshold:
            severity = 'CRITICAL'
        elif anomaly_score > self.warning_threshold:
            severity = 'WARNING'
        else:
            return None

        # Get historical context
        historical = await self.get_historical_scores(session_id, minutes=10)

        # Determine anomaly type
        anomaly_type = self._classify_anomaly(current_score, historical, signals)

        return Anomaly(
            session_id=session_id,
            type=anomaly_type,
            severity=severity,
            anomaly_score=anomaly_score,
            current_engagement=current_score,
            expected_engagement=self._calculate_expected(historical),
            deviation=self._calculate_deviation(current_score, historical),
            signals=signals,
            timestamp=datetime.now()
        )

    def _classify_anomaly(
        self,
        current: float,
        historical: List[float],
        signals: dict
    ) -> str:
        """Classify the type of anomaly"""

        if len(historical) < 3:
            return 'INSUFFICIENT_DATA'

        # Check for sudden drop
        recent_avg = sum(historical[-3:]) / 3
        if current < recent_avg * 0.7:
            return 'SUDDEN_DROP'

        # Check for gradual decline
        if all(historical[i] > historical[i+1] for i in range(len(historical)-1)):
            return 'GRADUAL_DECLINE'

        # Check for low absolute engagement
        if current < 0.4:
            return 'LOW_ENGAGEMENT'

        # Check for high leave rate
        if signals['leave_rate'] > 0.2:
            return 'MASS_EXIT'

        return 'UNKNOWN'

    async def get_historical_scores(
        self,
        session_id: str,
        minutes: int = 10
    ) -> List[float]:
        """Get historical engagement scores from Redis Stream"""

        # Read from engagement stream
        results = await self.redis.xrevrange(
            f'engagement:{session_id}',
            count=minutes * 12  # 12 scores per minute (every 5 seconds)
        )

        scores = [float(json.loads(r[1][b'score'])) for r in results]
        return list(reversed(scores))  # Chronological order

    def _calculate_expected(self, historical: List[float]) -> float:
        """Calculate expected engagement based on history"""
        if not historical:
            return 0.7  # Default baseline
        return sum(historical) / len(historical)

    def _calculate_deviation(
        self,
        current: float,
        historical: List[float]
    ) -> float:
        """Calculate z-score deviation"""
        if len(historical) < 2:
            return 0.0

        mean = sum(historical) / len(historical)
        variance = sum((x - mean) ** 2 for x in historical) / len(historical)
        std_dev = variance ** 0.5

        if std_dev == 0:
            return 0.0

        return (current - mean) / std_dev


from dataclasses import dataclass

@dataclass
class Anomaly:
    session_id: str
    type: str
    severity: str  # 'WARNING' or 'CRITICAL'
    anomaly_score: float
    current_engagement: float
    expected_engagement: float
    deviation: float
    signals: dict
    timestamp: datetime

    def to_dict(self) -> dict:
        return {
            'session_id': self.session_id,
            'type': self.type,
            'severity': self.severity,
            'anomaly_score': self.anomaly_score,
            'current_engagement': self.current_engagement,
            'expected_engagement': self.expected_engagement,
            'deviation': self.deviation,
            'signals': self.signals,
            'timestamp': self.timestamp.isoformat()
        }
```

#### Week 4: Intervention Selection (Thompson Sampling)

```python
# agent-service/app/agents/intervention_selector.py

import redis.asyncio as redis
from scipy.stats import beta
import numpy as np
import json
from typing import Dict, List, Optional

class InterventionSelector:
    """
    Selects optimal intervention using Thompson Sampling.
    Learns which interventions work best in which contexts.
    """

    def __init__(self):
        self.redis = redis.from_url("redis://localhost:6379")

        # Intervention types
        self.interventions = [
            'POLL',
            'CHAT_PROMPT',
            'NUDGE',
            'QNA_PROMOTE'
        ]

        # Context features that affect intervention success
        self.context_features = [
            'session_phase',  # opening, middle, closing
            'session_type',   # keynote, workshop, panel
            'audience_size',  # small, medium, large
            'anomaly_type'    # sudden_drop, gradual_decline, etc.
        ]

    async def select(
        self,
        session_id: str,
        anomaly: 'Anomaly',
        context: dict
    ) -> 'SelectedIntervention':
        """
        Select the best intervention for this context using Thompson Sampling
        """

        # Get context key (e.g., "middle_workshop_large_sudden_drop")
        context_key = self._build_context_key(context, anomaly)

        # Load historical performance for this context
        stats = await self._load_stats(context_key)

        # Thompson Sampling: Sample from Beta distributions
        samples = {}
        applicable_interventions = self._filter_applicable(
            self.interventions,
            context,
            anomaly
        )

        for intervention in applicable_interventions:
            # Get alpha (successes) and beta (failures) parameters
            alpha = stats.get(intervention, {}).get('success', 1)
            beta_param = stats.get(intervention, {}).get('failure', 1)

            # Sample from Beta distribution
            samples[intervention] = np.random.beta(alpha, beta_param)

        # Select intervention with highest sample
        selected = max(samples, key=samples.get)
        confidence = samples[selected]

        # Generate specific intervention parameters
        params = await self._generate_params(selected, session_id, anomaly, context)

        return SelectedIntervention(
            type=selected,
            params=params,
            confidence=confidence,
            context_key=context_key,
            reasoning=self._explain_selection(selected, context, anomaly)
        )

    def _build_context_key(self, context: dict, anomaly: 'Anomaly') -> str:
        """Build context key for storing stats"""
        return f"{context['phase']}_{context['type']}_{context['size']}_{anomaly.type}"

    async def _load_stats(self, context_key: str) -> dict:
        """Load intervention statistics for this context from Redis"""
        data = await self.redis.get(f'intervention_stats:{context_key}')
        if data:
            return json.loads(data)
        return {}

    async def save_outcome(
        self,
        context_key: str,
        intervention: str,
        success: bool
    ):
        """Update statistics after observing outcome"""

        # Load current stats
        stats = await self._load_stats(context_key)

        # Initialize if not exists
        if intervention not in stats:
            stats[intervention] = {'success': 1, 'failure': 1}  # Beta(1,1) prior

        # Update based on outcome
        if success:
            stats[intervention]['success'] += 1
        else:
            stats[intervention]['failure'] += 1

        # Save back to Redis
        await self.redis.set(
            f'intervention_stats:{context_key}',
            json.dumps(stats)
        )

    def _filter_applicable(
        self,
        interventions: List[str],
        context: dict,
        anomaly: 'Anomaly'
    ) -> List[str]:
        """Filter interventions that are applicable in this context"""

        applicable = []

        for intervention in interventions:
            if intervention == 'POLL':
                # Polls work best in middle of session, not too early or late
                if context['phase'] in ['middle', 'opening']:
                    applicable.append(intervention)

            elif intervention == 'CHAT_PROMPT':
                # Chat prompts work anytime
                applicable.append(intervention)

            elif intervention == 'NUDGE':
                # Nudges work best for gradual decline or low engagement
                if anomaly.type in ['GRADUAL_DECLINE', 'LOW_ENGAGEMENT']:
                    applicable.append(intervention)

            elif intervention == 'QNA_PROMOTE':
                # Q&A works in workshops and panels, not keynotes
                if context['type'] in ['workshop', 'panel']:
                    applicable.append(intervention)

        return applicable if applicable else ['CHAT_PROMPT']  # Default fallback

    async def _generate_params(
        self,
        intervention_type: str,
        session_id: str,
        anomaly: 'Anomaly',
        context: dict
    ) -> dict:
        """Generate specific parameters for the intervention"""

        if intervention_type == 'POLL':
            return {
                'timing': 'IMMEDIATE',
                'display_duration': 60,
                'reason': f'Engagement dropping: {anomaly.type}'
            }

        elif intervention_type == 'CHAT_PROMPT':
            return {
                'isPinned': True,
                'mentionMode': 'BROADCAST'
            }

        elif intervention_type == 'NUDGE':
            # Target specific user segment based on anomaly
            target = 'DISENGAGED' if anomaly.type == 'GRADUAL_DECLINE' else 'LURKERS'
            return {
                'targetSegment': target,
                'action': {'type': 'POLL', 'cta': 'Share your thoughts!'}
            }

        elif intervention_type == 'QNA_PROMOTE':
            return {
                'strategy': 'SURFACE_BEST',
                'count': 3
            }

        return {}

    def _explain_selection(
        self,
        intervention: str,
        context: dict,
        anomaly: 'Anomaly'
    ) -> str:
        """Generate human-readable explanation for why this intervention was selected"""

        reasons = {
            'POLL': f"Launching a poll because engagement dropped {abs(anomaly.deviation):.1f} standard deviations below expected. Polls typically recover engagement by 15-25% in {context['phase']} sessions.",

            'CHAT_PROMPT': f"Injecting a discussion prompt to spark conversation. Chat activity is at {anomaly.signals['chat_msgs_per_min']:.1f} msgs/min (low). Prompts typically increase chat activity by 40%.",

            'NUDGE': f"Sending personalized nudges to {self._estimate_target_size(context, anomaly)} disengaged attendees. {anomaly.type} patterns respond well to gentle reminders.",

            'QNA_PROMOTE': f"Surfacing high-quality questions to re-engage attendees. Q&A promotion works well in {context['type']} formats."
        }

        return reasons.get(intervention, "Selected based on historical performance")

    def _estimate_target_size(self, context: dict, anomaly: 'Anomaly') -> int:
        """Estimate how many users will be targeted by nudge"""
        total_users = anomaly.signals.get('active_users', 50)
        return int(total_users * 0.3)  # Rough estimate: 30% are disengaged


@dataclass
class SelectedIntervention:
    type: str
    params: dict
    confidence: float
    context_key: str
    reasoning: str

    def to_dict(self) -> dict:
        return {
            'type': self.type,
            'params': self.params,
            'confidence': self.confidence,
            'context_key': self.context_key,
            'reasoning': self.reasoning
        }
```

---

### Phase 3: LLM Integration (Week 5)

**Goal:** Add intelligence for content generation using Claude/GPT

```python
# agent-service/app/agents/content_generator.py

import anthropic
from typing import Optional
import json

class ContentGenerator:
    """
    Generates contextual content for interventions using LLMs.
    Uses Claude 3.5 Haiku for speed and cost-efficiency.
    """

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-3-5-haiku-20241022"

    async def generate_poll(
        self,
        session: dict,
        context: dict,
        recent_chat: List[dict]
    ) -> dict:
        """Generate contextual poll question and options"""

        prompt = self._build_poll_prompt(session, context, recent_chat)

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=300,
            temperature=0.7,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        content = response.content[0].text
        poll_data = json.loads(content)

        return {
            'question': poll_data['question'],
            'options': poll_data['options'],
            'reasoning': poll_data.get('reasoning', '')
        }

    def _build_poll_prompt(
        self,
        session: dict,
        context: dict,
        recent_chat: List[dict]
    ) -> str:

        chat_summary = self._summarize_chat(recent_chat) if recent_chat else "No recent chat activity"

        return f"""You are an AI assistant helping to re-engage attendees in a live event session.

**Session Details:**
- Title: {session['title']}
- Description: {session['description']}
- Speaker: {session['speaker_name']}
- Current phase: {context['phase']} (duration: {context['elapsed_minutes']} minutes)
- Session type: {context['type']}

**Current Situation:**
- Engagement has dropped to {context['current_engagement']:.0%}
- Recent chat activity: {chat_summary}
- Audience size: {context['attendee_count']} attendees

**Your Task:**
Create a poll question that will:
1. Re-engage attendees who are losing interest
2. Be directly relevant to the session topic
3. Have clear, distinct answer options (3-4 options)
4. Spark discussion and curiosity
5. Be answerable in 10 seconds

**Guidelines:**
- Make it practical, not theoretical
- Relate to real-world application
- Avoid yes/no questions
- Include a "fun" or surprising option if appropriate

**Output Format (JSON only, no markdown):**
{{
  "question": "Your engaging poll question here",
  "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
  "reasoning": "Why this poll will re-engage attendees"
}}"""

    def _summarize_chat(self, recent_chat: List[dict], limit: int = 5) -> str:
        """Summarize recent chat messages"""
        if not recent_chat:
            return "No recent messages"

        messages = recent_chat[-limit:]
        summary = " | ".join([f"{msg['user']}: {msg['content'][:50]}" for msg in messages])
        return summary

    async def generate_chat_prompt(
        self,
        session: dict,
        context: dict,
        anomaly: 'Anomaly'
    ) -> str:
        """Generate discussion prompt for chat"""

        prompt = f"""You are an AI assistant for a live event session. Generate a discussion prompt to re-engage attendees.

**Session:** {session['title']}
**Topic:** {session['description'][:200]}
**Current phase:** {context['phase']}
**Issue:** Engagement dropped {abs(anomaly.deviation):.1f}σ below expected

**Generate a chat message that:**
1. Is conversational and friendly (use "we" or "you")
2. Asks an open-ended question about practical application
3. Encourages people to share experiences
4. Is 1-2 sentences max
5. Includes a relevant emoji

**Examples:**
- "💡 Quick question: How are you currently handling API rate limiting in production? Any clever workarounds?"
- "🤔 Curious: What's been your biggest challenge with microservices? Let's learn from each other!"

**Your prompt (just the message, no explanation):**"""

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=150,
            temperature=0.8,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text.strip()

    async def generate_nudge_message(
        self,
        session: dict,
        user_segment: str
    ) -> str:
        """Generate personalized nudge message"""

        segment_context = {
            'DISENGAGED': "hasn't interacted in 10+ minutes but is still in the session",
            'LURKERS': "has been present for 15+ minutes but never interacted",
            'FIRST_TIME': "is attending their first session on this platform"
        }

        prompt = f"""Generate a friendly notification message to re-engage an attendee.

**Session:** {session['title']}
**User segment:** {user_segment} ({segment_context.get(user_segment, '')})

**Message requirements:**
1. Personalized (use "{{{{name}}}}" placeholder)
2. Encouraging, not pushy
3. Includes a clear call-to-action
4. 1-2 sentences
5. Relevant emoji

**Examples:**
- "👋 Hey {{{{name}}}}! This session is heating up. Jump into the chat - we'd love to hear your take!"
- "💬 {{{{name}}}}, great discussion happening in chat right now. What's your experience with this?"

**Your message:**"""

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=100,
            temperature=0.9,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text.strip()
```

---

### Phase 4: Complete Agent Loop (Week 6)

**Goal:** Tie everything together into the main agent loop

```python
# agent-service/app/agents/engagement_conductor.py

from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator
from datetime import datetime

class AgentState(TypedDict):
    """State passed between agent steps"""
    session_id: str
    engagement_score: float
    signals: dict
    anomaly: Optional['Anomaly']
    context: dict
    intervention: Optional['SelectedIntervention']
    outcome: Optional[dict]
    messages: Annotated[list, operator.add]


class EngagementConductor:
    """
    Main agent orchestrator using LangGraph.
    Implements Perceive -> Decide -> Act -> Learn loop.
    """

    def __init__(
        self,
        anomaly_detector: 'AnomalyDetector',
        intervention_selector: 'InterventionSelector',
        content_generator: 'ContentGenerator',
        action_executor: 'ActionExecutor'
    ):
        self.anomaly_detector = anomaly_detector
        self.intervention_selector = intervention_selector
        self.content_generator = content_generator
        self.action_executor = action_executor

        # Build agent graph
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build LangGraph workflow"""

        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("perceive", self.perceive)
        workflow.add_node("detect_anomaly", self.detect_anomaly)
        workflow.add_node("decide_intervention", self.decide_intervention)
        workflow.add_node("generate_content", self.generate_content)
        workflow.add_node("execute_action", self.execute_action)
        workflow.add_node("monitor_outcome", self.monitor_outcome)
        workflow.add_node("learn", self.learn)

        # Define edges
        workflow.set_entry_point("perceive")
        workflow.add_edge("perceive", "detect_anomaly")

        # Conditional: Only intervene if anomaly detected
        workflow.add_conditional_edges(
            "detect_anomaly",
            self.should_intervene,
            {
                "intervene": "decide_intervention",
                "monitor": "perceive"  # Loop back
            }
        )

        workflow.add_edge("decide_intervention", "generate_content")
        workflow.add_edge("generate_content", "execute_action")
        workflow.add_edge("execute_action", "monitor_outcome")
        workflow.add_edge("monitor_outcome", "learn")
        workflow.add_edge("learn", "perceive")  # Loop back

        return workflow.compile()

    async def perceive(self, state: AgentState) -> AgentState:
        """Gather current engagement signals"""

        # Get latest engagement data from Redis
        engagement_data = await self._get_latest_engagement(state['session_id'])

        state['engagement_score'] = engagement_data['score']
        state['signals'] = engagement_data['signals']
        state['messages'].append({
            'type': 'perceive',
            'timestamp': datetime.now().isoformat(),
            'engagement_score': engagement_data['score']
        })

        return state

    async def detect_anomaly(self, state: AgentState) -> AgentState:
        """Check if engagement is anomalous"""

        anomaly = await self.anomaly_detector.detect(
            session_id=state['session_id'],
            current_score=state['engagement_score'],
            signals=state['signals']
        )

        state['anomaly'] = anomaly

        if anomaly:
            state['messages'].append({
                'type': 'anomaly_detected',
                'anomaly': anomaly.to_dict()
            })

        return state

    def should_intervene(self, state: AgentState) -> str:
        """Decide if intervention is needed"""

        # No anomaly = no intervention
        if not state['anomaly']:
            return "monitor"

        # Critical anomalies always intervene
        if state['anomaly'].severity == 'CRITICAL':
            return "intervene"

        # Warning anomalies: intervene if score < 0.5
        if state['engagement_score'] < 0.5:
            return "intervene"

        return "monitor"

    async def decide_intervention(self, state: AgentState) -> AgentState:
        """Select optimal intervention"""

        # Build context
        context = await self._build_context(state['session_id'])
        state['context'] = context

        # Select intervention using Thompson Sampling
        intervention = await self.intervention_selector.select(
            session_id=state['session_id'],
            anomaly=state['anomaly'],
            context=context
        )

        state['intervention'] = intervention
        state['messages'].append({
            'type': 'intervention_selected',
            'intervention': intervention.to_dict()
        })

        return state

    async def generate_content(self, state: AgentState) -> AgentState:
        """Generate content for intervention using LLM"""

        intervention = state['intervention']
        session = await self._get_session_details(state['session_id'])

        if intervention.type == 'POLL':
            # Generate poll question and options
            poll_data = await self.content_generator.generate_poll(
                session=session,
                context=state['context'],
                recent_chat=await self._get_recent_chat(state['session_id'])
            )
            intervention.params['question'] = poll_data['question']
            intervention.params['options'] = poll_data['options']

        elif intervention.type == 'CHAT_PROMPT':
            # Generate discussion prompt
            prompt = await self.content_generator.generate_chat_prompt(
                session=session,
                context=state['context'],
                anomaly=state['anomaly']
            )
            intervention.params['message'] = prompt

        elif intervention.type == 'NUDGE':
            # Generate nudge message
            message = await self.content_generator.generate_nudge_message(
                session=session,
                user_segment=intervention.params['targetSegment']
            )
            intervention.params['message'] = message

        state['messages'].append({
            'type': 'content_generated',
            'content': intervention.params
        })

        return state

    async def execute_action(self, state: AgentState) -> AgentState:
        """Execute the intervention"""

        result = await self.action_executor.execute(
            session_id=state['session_id'],
            intervention=state['intervention']
        )

        state['messages'].append({
            'type': 'action_executed',
            'result': result
        })

        return state

    async def monitor_outcome(self, state: AgentState) -> AgentState:
        """Monitor the outcome of intervention"""

        # Wait 2 minutes to measure impact
        await asyncio.sleep(120)

        # Get new engagement score
        new_data = await self._get_latest_engagement(state['session_id'])
        new_score = new_data['score']

        # Calculate impact
        engagement_delta = new_score - state['engagement_score']
        success = engagement_delta > 0.1  # 10% improvement = success

        outcome = {
            'success': success,
            'engagement_before': state['engagement_score'],
            'engagement_after': new_score,
            'delta': engagement_delta,
            'timestamp': datetime.now().isoformat()
        }

        state['outcome'] = outcome
        state['messages'].append({
            'type': 'outcome_measured',
            'outcome': outcome
        })

        return state

    async def learn(self, state: AgentState) -> AgentState:
        """Update models based on outcome"""

        # Update intervention selector (Thompson Sampling)
        await self.intervention_selector.save_outcome(
            context_key=state['intervention'].context_key,
            intervention=state['intervention'].type,
            success=state['outcome']['success']
        )

        # Store intervention and outcome in database for analysis
        await self._store_intervention_result(state)

        state['messages'].append({
            'type': 'learned',
            'success': state['outcome']['success']
        })

        return state

    async def run(self, session_id: str):
        """Start monitoring session"""

        initial_state = {
            'session_id': session_id,
            'engagement_score': 0.0,
            'signals': {},
            'anomaly': None,
            'context': {},
            'intervention': None,
            'outcome': None,
            'messages': []
        }

        # Run agent graph (loops continuously)
        async for state in self.graph.astream(initial_state):
            # Log state transitions
            print(f"Agent state: {state['messages'][-1]}")

            # Can add monitoring/observability here
```

---

### Phase 5: Frontend Dashboard (Week 7-8)

**Goal:** Build organizer dashboard to watch agent in action

```typescript
// real-time-service/src/components/EngagementDashboard.tsx

import React, { useEffect, useState } from 'react';
import { Line } from 'react-chartjs-2';
import { io, Socket } from 'socket.io-client';

interface EngagementData {
  timestamp: string;
  score: number;
  signals: {
    chat_msgs_per_min: number;
    active_users: number;
    poll_participation: number;
  };
}

interface AgentAction {
  type: string;
  reasoning: string;
  confidence: number;
  timestamp: string;
  outcome?: {
    success: boolean;
    delta: number;
  };
}

export const EngagementDashboard: React.FC<{ sessionId: string }> = ({ sessionId }) => {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [engagementHistory, setEngagementHistory] = useState<EngagementData[]>([]);
  const [currentScore, setCurrentScore] = useState<number>(0);
  const [agentActions, setAgentActions] = useState<AgentAction[]>([]);
  const [isAgentActive, setIsAgentActive] = useState(false);

  useEffect(() => {
    // Connect to real-time service
    const socketConnection = io('http://localhost:3000', {
      query: { sessionId }
    });

    socketConnection.on('connect', () => {
      console.log('Connected to engagement monitoring');

      // Subscribe to engagement updates
      socketConnection.emit('subscribe:engagement', { sessionId });
    });

    // Real-time engagement updates (every 5 seconds)
    socketConnection.on('engagement:update', (data: EngagementData) => {
      setCurrentScore(data.score);
      setEngagementHistory(prev => [...prev.slice(-60), data]); // Keep last 5 minutes
    });

    // Agent action notifications
    socketConnection.on('agent:action', (action: AgentAction) => {
      setAgentActions(prev => [action, ...prev]);
      setIsAgentActive(true);

      // Show toast notification
      showToast(`🤖 Agent: ${action.type}`, action.reasoning);
    });

    // Agent outcome updates
    socketConnection.on('agent:outcome', (outcome: any) => {
      setAgentActions(prev => {
        const updated = [...prev];
        updated[0] = { ...updated[0], outcome };
        return updated;
      });
      setIsAgentActive(false);

      // Show result toast
      const emoji = outcome.success ? '✅' : '⚠️';
      showToast(
        `${emoji} Intervention ${outcome.success ? 'Successful' : 'Completed'}`,
        `Engagement ${outcome.success ? 'increased' : 'changed'} by ${Math.abs(outcome.delta * 100).toFixed(1)}%`
      );
    });

    setSocket(socketConnection);

    return () => {
      socketConnection.disconnect();
    };
  }, [sessionId]);

  // Engagement score chart data
  const chartData = {
    labels: engagementHistory.map(d => new Date(d.timestamp).toLocaleTimeString()),
    datasets: [
      {
        label: 'Engagement Score',
        data: engagementHistory.map(d => d.score),
        borderColor: currentScore > 0.7 ? '#10b981' : currentScore > 0.5 ? '#f59e0b' : '#ef4444',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        tension: 0.4,
      },
      {
        label: 'Threshold',
        data: engagementHistory.map(() => 0.6),
        borderColor: '#6b7280',
        borderDash: [5, 5],
        pointRadius: 0,
      }
    ]
  };

  return (
    <div className="engagement-dashboard">
      {/* Header */}
      <div className="dashboard-header">
        <h2>🤖 Engagement Conductor</h2>
        <div className="status-indicator">
          <div className={`status-dot ${isAgentActive ? 'active' : 'monitoring'}`} />
          <span>{isAgentActive ? 'Intervening...' : 'Monitoring'}</span>
        </div>
      </div>

      {/* Current Engagement Score (Big Number) */}
      <div className="engagement-score-card">
        <div className="score-label">Current Engagement</div>
        <div className={`score-value ${getScoreClass(currentScore)}`}>
          {(currentScore * 100).toFixed(0)}%
        </div>
        <div className="score-indicator">
          {currentScore > 0.7 && <span className="badge badge-success">🎉 Excellent</span>}
          {currentScore >= 0.5 && currentScore <= 0.7 && <span className="badge badge-warning">⚠️ Fair</span>}
          {currentScore < 0.5 && <span className="badge badge-danger">🚨 Low</span>}
        </div>
      </div>

      {/* Engagement Chart */}
      <div className="chart-container">
        <h3>Engagement Over Time</h3>
        <Line data={chartData} options={{
          responsive: true,
          plugins: {
            legend: { display: true },
            tooltip: { mode: 'index', intersect: false }
          },
          scales: {
            y: { min: 0, max: 1, ticks: { callback: (value) => `${(value * 100)}%` } }
          }
        }} />
      </div>

      {/* Agent Actions Feed */}
      <div className="agent-actions-feed">
        <h3>Agent Activity</h3>
        {agentActions.length === 0 && (
          <div className="empty-state">
            <p>🤖 Agent is monitoring. No interventions needed yet.</p>
          </div>
        )}
        {agentActions.map((action, idx) => (
          <div key={idx} className="action-card">
            <div className="action-header">
              <span className="action-type">{getActionIcon(action.type)} {action.type}</span>
              <span className="action-time">{formatTime(action.timestamp)}</span>
            </div>
            <p className="action-reasoning">{action.reasoning}</p>
            <div className="action-confidence">
              <span>Confidence: {(action.confidence * 100).toFixed(0)}%</span>
              <div className="confidence-bar">
                <div
                  className="confidence-fill"
                  style={{ width: `${action.confidence * 100}%` }}
                />
              </div>
            </div>
            {action.outcome && (
              <div className={`action-outcome ${action.outcome.success ? 'success' : 'neutral'}`}>
                {action.outcome.success ? '✅' : '⚪'}
                Engagement {action.outcome.delta > 0 ? 'increased' : 'changed'} by {Math.abs(action.outcome.delta * 100).toFixed(1)}%
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Real-Time Signals */}
      <div className="signals-grid">
        <SignalCard
          icon="💬"
          label="Chat Activity"
          value={`${engagementHistory[engagementHistory.length - 1]?.signals.chat_msgs_per_min.toFixed(1) || 0} msgs/min`}
        />
        <SignalCard
          icon="👥"
          label="Active Users"
          value={engagementHistory[engagementHistory.length - 1]?.signals.active_users || 0}
        />
        <SignalCard
          icon="📊"
          label="Poll Participation"
          value={`${((engagementHistory[engagementHistory.length - 1]?.signals.poll_participation || 0) * 100).toFixed(0)}%`}
        />
      </div>
    </div>
  );
};

const SignalCard: React.FC<{ icon: string; label: string; value: string | number }> = ({ icon, label, value }) => (
  <div className="signal-card">
    <div className="signal-icon">{icon}</div>
    <div className="signal-label">{label}</div>
    <div className="signal-value">{value}</div>
  </div>
);

function getScoreClass(score: number): string {
  if (score > 0.7) return 'excellent';
  if (score > 0.5) return 'fair';
  return 'low';
}

function getActionIcon(type: string): string {
  const icons = {
    'POLL': '📊',
    'CHAT_PROMPT': '💬',
    'NUDGE': '📩',
    'QNA_PROMOTE': '❓'
  };
  return icons[type] || '🤖';
}

function formatTime(timestamp: string): string {
  return new Date(timestamp).toLocaleTimeString();
}

function showToast(title: string, message: string) {
  // Implement toast notification
  // Could use react-hot-toast, react-toastify, etc.
}
```

---

## Success Metrics & Monitoring

### Key Performance Indicators

```yaml
Agent Health Metrics:
  - Uptime: >99.9%
  - Decision latency (p95): <200ms
  - Intervention success rate: >70%
  - False positive rate: <10%

Engagement Impact Metrics:
  - Engagement score improvement after intervention: +25% avg
  - Session completion rate: +15%
  - Attendee satisfaction (NPS): +10 points
  - "Saved sessions" (score recovered from <0.5): Track count

Business Metrics:
  - Organizer adoption rate: 60% of events enable agent
  - Retention uplift: +30% for agent users
  - Feature stickiness (DAU/MAU): >0.6
  - Upgrade conversion: 2x (free to paid)

Learning Metrics:
  - Interventions performed: Track total count
  - Contexts explored: Unique context_keys in Thompson Sampling
  - Model convergence: Beta distribution variance decreasing
  - Cross-event learning: Success rate improving over time
```

### Observability Stack

```yaml
Tracing:
  Tool: LangSmith (built into LangChain/LangGraph)
  What: Trace every agent decision, LLM call, intervention
  Why: Debug failures, understand decision paths

Metrics:
  Tool: Prometheus + Grafana
  What: Engagement scores, intervention rates, latency, success rates
  Why: Real-time monitoring, alerting

Logging:
  Tool: Elasticsearch + Kibana (ELK stack)
  What: Agent logs, interventions, outcomes
  Why: Historical analysis, debugging

Alerts:
  Tool: PagerDuty / Opsgenie
  Triggers:
    - Agent error rate >1%
    - Intervention success rate <50%
    - Decision latency >500ms (p95)
    - LLM API failures >5%
```

---

## Demo Strategy (POC for "Wow" Moment)

### Week 8: Create Knockout Demo

**Objective:** Create a self-contained demo that shows the "magic moment" in 60 seconds

**Demo Flow:**

```
1. [0:00 - 0:10] Show live session dashboard
   - Engagement score: 0.75 (healthy)
   - Chat active, attendees engaged

2. [0:10 - 0:20] Simulate engagement drop
   - Reduce chat activity (simulate)
   - Engagement drops to 0.48
   - Dashboard shows warning: "⚠️ Engagement declining"

3. [0:20 - 0:25] Agent activates
   - Dashboard shows: "🤖 Agent: Intervention initiated"
   - Agent decision appears: "Launching poll to re-engage attendees"
   - Confidence: 87%

4. [0:25 - 0:35] Watch poll appear in "live" session
   - Poll question generated by AI appears
   - "Which AI technique interests you most?"
   - Options: RAG, Fine-tuning, Agents, Prompt Engineering

5. [0:35 - 0:50] Simulate recovery
   - Poll participation: 47%
   - Chat lights up with discussion
   - Engagement score: 0.48 → 0.67 → 0.82

6. [0:50 - 1:00] Show outcome
   - "✅ Intervention successful"
   - "Engagement increased by 71%"
   - "Session saved"

**Tagline:** "Your AI co-pilot that never lets your event fail."
```

**Technical Implementation:**

```python
# demo/engagement_simulator.py

import asyncio
import random
from datetime import datetime, timedelta

class EngagementSimulator:
    """Simulates engagement drop and recovery for demo"""

    async def run_demo(self):
        # Phase 1: Healthy engagement
        print("📊 Session healthy - engagement at 75%")
        await self.simulate_healthy_engagement(duration=10)

        # Phase 2: Simulate drop
        print("⚠️  Simulating engagement drop...")
        await self.simulate_engagement_drop(duration=10)

        # Phase 3: Agent intervenes
        print("🤖 Agent activated - analyzing situation")
        await self.simulate_agent_decision()

        print("🤖 Launching intervention: Contextual poll")
        await self.simulate_poll_launch()

        # Phase 4: Recovery
        print("📈 Monitoring recovery...")
        await self.simulate_recovery(duration=15)

        print("✅ Intervention successful - engagement at 82%")
        print("🎉 Session saved!")

    async def simulate_healthy_engagement(self, duration: int):
        for i in range(duration):
            score = 0.75 + random.uniform(-0.05, 0.05)
            await self.publish_engagement(score, signals={
                'chat_msgs_per_min': random.uniform(8, 12),
                'active_users': random.randint(45, 55),
                'poll_participation': 0.6
            })
            await asyncio.sleep(1)

    async def simulate_engagement_drop(self, duration: int):
        for i in range(duration):
            # Gradual decline
            score = 0.75 - (i / duration) * 0.27  # Drop to 0.48
            await self.publish_engagement(score, signals={
                'chat_msgs_per_min': max(0, 10 - i * 1.2),
                'active_users': max(20, 50 - i * 3),
                'poll_participation': 0.3
            })
            await asyncio.sleep(1)

    async def simulate_agent_decision(self):
        await asyncio.sleep(2)  # Agent "thinking"

        decision = {
            'type': 'POLL',
            'confidence': 0.87,
            'reasoning': 'Launching a poll because engagement dropped 2.1 standard deviations below expected. Polls typically recover engagement by 15-25% in middle sessions.'
        }

        await self.publish_agent_action(decision)

    async def simulate_poll_launch(self):
        poll = {
            'question': '🤔 Which AI technique are you most interested in?',
            'options': ['RAG', 'Fine-tuning', 'Agents', 'Prompt Engineering']
        }

        await self.publish_poll(poll)
        await asyncio.sleep(2)

        # Simulate voting
        for i in range(10):
            await self.publish_poll_vote(random.choice(poll['options']))
            await asyncio.sleep(0.3)

    async def simulate_recovery(self, duration: int):
        for i in range(duration):
            # Gradual recovery
            score = 0.48 + (i / duration) * 0.34  # Recover to 0.82
            await self.publish_engagement(score, signals={
                'chat_msgs_per_min': 3 + (i / duration) * 11,
                'active_users': 25 + int((i / duration) * 28),
                'poll_participation': 0.47
            })
            await asyncio.sleep(1)

# Run demo
if __name__ == '__main__':
    simulator = EngagementSimulator()
    asyncio.run(simulator.run_demo())
```

---

## Cost Analysis

### Per-Event Cost Estimates

```yaml
Infrastructure Costs (per 1-hour session, 100 attendees):
  Redis Streams: $0.001
  TimescaleDB storage: $0.002
  Compute (agent service): $0.01
  Total infrastructure: $0.013

AI/ML Costs (per session):
  LLM API calls:
    - Haiku calls: 3-5 per intervention @ $0.0025 each = $0.0075-$0.0125
    - Interventions per session: 0-3 avg = 1.5
    - Total LLM cost: $0.01125 - $0.01875

  Total AI cost: ~$0.015

Total Cost Per Session: ~$0.028
Revenue Per Session (assuming $99/mo plan, 40 events/mo): $2.48
Gross Margin: 98.9%

Scale Economics (10,000 events/day):
  Daily cost: $280
  Monthly cost: ~$8,400
  With 2,000 customers @ $99/mo: $198,000 revenue
  Gross margin on agent feature: 95.8%
```

**Conclusion:** Economics are extremely favorable. Agent costs <$0.03 per session, enabling aggressive pricing.

---

## Go-To-Market Strategy

### Launch Plan

**Week 1-2: Private Alpha**
- 5 hand-picked customers
- Dedicated Slack channel for feedback
- Daily check-ins
- Goal: Validate "wow" moment, collect testimonials

**Week 3-4: Closed Beta**
- 50 customers (invite-only)
- Self-service onboarding
- Weekly feedback surveys
- Goal: Stress-test at scale, refine UX

**Week 5-6: Public Launch**
- Announce on Product Hunt
- Blog post: "Meet the AI that never lets your event fail"
- Demo video (60 seconds, showing the magic moment)
- PR outreach: TechCrunch, VentureBeat

### Pricing Strategy

```yaml
Free Plan:
  - Manual approval mode only
  - 5 agent interventions/month
  - Basic analytics

Pro Plan ($99/mo):
  - Semi-auto mode
  - Unlimited interventions
  - Advanced analytics
  - Priority support

Enterprise ($499/mo):
  - Full autopilot mode
  - Custom agent training
  - Dedicated success manager
  - White-glove onboarding
```

### Messaging

**Headline:** "The AI that never lets your event fail"

**Subheadline:** "Watch as our Engagement Conductor detects dropping engagement in real-time and intervenes automatically—saving your sessions before attendees even notice."

**Social Proof:**
- "We saw engagement increase 34% on average when the AI stepped in" - Customer X
- "It's like having a co-pilot who never sleeps" - Customer Y

**Call-to-Action:** "Try it free at your next event"

---

## Next Steps: Your Week 1 Checklist

```
✅ Day 1-2: Set up infrastructure
   □ Spin up Redis, TimescaleDB
   □ Initialize agent-service repo
   □ Install dependencies

✅ Day 3-4: Implement signal collection
   □ Build EngagementSignalCollector
   □ Test with existing WebSocket gateways
   □ Verify engagement scores are calculated correctly

✅ Day 5: Build basic anomaly detector
   □ Implement simple z-score detection (start simple)
   □ Test with historical data

✅ Day 6-7: Create first intervention (manual)
   □ Build "Launch Poll" action
   □ Test end-to-end: signal → detect → act
   □ Verify poll appears in session

🎯 Week 1 Goal: Have a working (manual) prototype that detects low engagement and launches a poll
```

**By Week 8, you'll have:**
- A fully autonomous agent that monitors, decides, and acts
- A beautiful dashboard showing it in action
- A demo that makes jaws drop
- 5 alpha customers ready to pay

---

## The Bottom Line

**This agent is your iPhone moment.**

Just like the iPhone wasn't the first smartphone but was the first to feel *magical*, the Engagement Conductor won't be the first event analytics tool—but it will be the first that *acts* on your behalf in real-time.

**The "I can never go back" moment happens when:**
1. An organizer watches their engagement drop
2. Gets nervous ("Oh no, my session is dying")
3. Sees the agent activate: "🤖 Intervention initiated"
4. Watches the poll appear, chat light up
5. Sees engagement recover in real-time
6. Thinks: "Holy shit. It just saved my session."

**That's the moment they'll tell every other organizer about.**

**That's your wedge. That's your moat. That's your Salesforce moment.**

Let's build it. 🚀
