# Session & Speaker Recommendations - Implementation Specification

**Document Version:** 1.0
**Date:** February 7, 2026
**Status:** Implementation Ready
**Priority:** High - Industry Standard Feature

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Research & Business Case](#research--business-case)
3. [Current State Analysis](#current-state-analysis)
4. [Feature Specifications](#feature-specifications)
5. [Technical Architecture](#technical-architecture)
6. [Implementation Phases](#implementation-phases)
7. [API Specifications](#api-specifications)
8. [Database Schema](#database-schema)
9. [Algorithm Details](#algorithm-details)
10. [Integration with Existing Systems](#integration-with-existing-systems)
11. [Success Metrics & Analytics](#success-metrics--analytics)
12. [Competitive Analysis](#competitive-analysis)
13. [Risk Mitigation](#risk-mitigation)
14. [Future Enhancements](#future-enhancements)
15. [References](#references)

---

## Executive Summary

### Recommendation: IMPLEMENT IMMEDIATELY ✅

Session and speaker recommendations are **table stakes** for competitive event platforms in 2026. This document provides a complete implementation specification based on industry research, competitive analysis, and proven best practices.

### Key Statistics
- **40%** of event professionals deploying AI-powered personalized agendas in 2026
- **340%** average ROI for conferences using engagement apps effectively
- **80%** of content consumed through recommendations (Netflix model applied to events)
- **25%** higher attendance for recommended sessions vs. manual discovery
- **88%** completion rate for personalized event content

### Strategic Value
1. **Competitive Parity:** All major platforms (Swapcard, Brella, Whova) offer this
2. **User Pain Point:** Session discovery is a documented problem for attendees
3. **Low Implementation Cost:** Reuse existing AI infrastructure (Oracle AI Service)
4. **High ROI:** Proven 340% ROI, 30% engagement increase
5. **Unique Opportunity:** Integrate with existing strong networking features

### Implementation Timeline
- **Phase 1 (MVP):** 2-3 weeks - Basic session recommendations
- **Phase 2 (Production):** 4-6 weeks - Full feature parity
- **Phase 3 (Competitive Advantage):** 8-12 weeks - Advanced features

---

## Research & Business Case

### Industry Trends (2026)

#### AI-Powered Personalization is Standard
- 50% of event professionals embracing AI throughout entire meetings journey
- 40% planning AI-powered event apps with personalized agendas
- AI acts as "event co-pilot" - automating workflows, analyzing behavior, powering recommendations

#### Proven ROI Metrics
| Metric | Impact | Source |
|--------|--------|--------|
| Average ROI for engagement apps | 340% | Engineerica Research |
| Content discovery rate | 80% | Netflix Model |
| Click-through rate increase | +30% | Personalized thumbnails |
| Session attendance increase | +25% | Interactive workshops |
| Video completion rate | 88% | Boomtown Festival |
| Share/download rate | 40% | Boomtown Festival |

#### Attendee Pain Points

**Session Discovery Challenges:**
- Attendees miss entire event areas/floors due to poor discovery
- Overwhelmed by 100+ session agendas
- Confusion over session timing and conflicts
- Suboptimal session selection leading to lower satisfaction
- Manual discovery yields only ~30% of relevant content found

**Research Finding:** "A significant portion of attendees never discovered a second floor exhibition area" - highlighting critical navigation and discovery failures.

#### Competitive Landscape

**All major platforms now offer AI-powered recommendations:**

| Platform | Session Recs | Speaker Recs | Technology |
|----------|--------------|--------------|------------|
| Swapcard | ✅ AI-powered | ✅ Contextual | AI matchmaking |
| Brella | ✅ Interest-based | ✅ Goal-based | AI + mutual goals |
| Whova | ✅ Discovery app | ✅ Interest-based | Community + algorithms |
| EventDex | ✅ AI-driven | ✅ Matchmaking | AI engine |
| Cvent | ✅ Personalized | ✅ Profile-based | AI-powered |

**Key Insight:** Not having this feature creates a competitive disadvantage.

### Business Value Breakdown

#### 1. Attendee Satisfaction & Retention
- Reduces "session FOMO" and decision paralysis
- 80% discovery rate vs. 30% manual discovery
- 25% higher attendance for recommended sessions
- 30% more engagement with personalized agendas

#### 2. Organizer Value
- Real-time analytics on content popularity
- Data-driven insights for future programming
- Ability to promote sponsor content/speakers
- Reduces support burden ("which session?" questions)

#### 3. Speaker/Sponsor ROI
- Right audiences find right speakers
- Increases niche topic attendance
- Better lead generation for sponsors
- Higher speaker satisfaction scores

#### 4. Revenue Impact
- 340% average ROI
- 40% share rate drives viral marketing
- Increases future ticket sales
- Justifies premium pricing

---

## Current State Analysis

### Existing Infrastructure (Advantages)

#### ✅ Production-Ready AI Matching Engine
- **Oracle AI Service** with LLM-based matchmaking
- Anthropic Claude integration for semantic understanding
- Proven fallback algorithms (Jaccard similarity)
- Circuit breaker pattern for resilience

#### ✅ Robust Caching Strategy
- Three-tier caching (Redis → PostgreSQL → Fresh generation)
- TTL management (5min Redis, 24h DB)
- Optimized for cost and performance

#### ✅ Event-Driven Architecture
- Kafka integration for async processing
- Real-time service orchestration
- Background job scheduling

#### ✅ User Profiling System
- Rich user profiles (interests, goals, skills)
- Behavioral tracking infrastructure
- Analytics and engagement tracking

### Current Gaps

#### ❌ Session Recommendations
**Status:** Prototype/placeholder only

**Location:** `/oracle-ai-service/app/features/recommendations/service.py`

**Current Implementation:**
```python
# Basic Jaccard similarity on tags
def get_content_recommendations(user_profile, num_recommendations=5):
    # Uses mock session data
    # Simple tag overlap calculation
    # NOT production ready
```

**Issues:**
- Not integrated into main app flow
- Uses placeholder data
- No LLM-based matching
- No caching or persistence
- No API endpoints exposed

#### ❌ Speaker Recommendations
**Status:** Prototype/placeholder only

**Location:** `/oracle-ai-service/app/features/recommendations/service.py` (lines 140-179)

**Current Implementation:**
```python
# Weighted binary scoring
WEIGHTS = {
    "expertise": 0.7,
    "audience": 0.3
}

# Binary 1.0 or 0.0 scoring - too simplistic
```

**Issues:**
- Basic binary scoring (not nuanced)
- Not integrated with real speaker data
- No LLM-based matching
- No conversation starters
- Not exposed via API

---

## Feature Specifications

### Session Recommendations

#### Must-Have Features (MVP - Phase 1)

**1. AI-Based Interest Matching**
- Input: User profile (interests, goals, skills, role)
- Algorithm: LLM-based semantic matching + fallback Jaccard
- Output: Top 5-10 recommended sessions with match scores

**2. Match Reasoning**
- Explain WHY each session is recommended
- Examples:
  - "Based on your interest in Machine Learning"
  - "Aligns with your goal to learn about AI"
  - "Matches your role as Product Manager"

**3. Session Metadata Enrichment**
- Session title, description, speakers
- Time, location, track
- Tags, topics, difficulty level
- Capacity and current attendance

**4. Basic Filtering**
- Filter by track, time slot, difficulty
- Exclude already-attended sessions
- Respect user preferences (saved/dismissed)

**5. Caching & Performance**
- Redis cache (5min TTL)
- Database persistence (24h TTL)
- Lazy regeneration on expiry

#### Should-Have Features (Phase 2)

**6. Personalized Agenda Builder**
- Auto-generate suggested daily schedule
- Resolve time conflicts automatically
- Suggest alternatives for conflicts
- Allow manual overrides

**7. Real-Time Re-Ranking**
- Update recommendations based on:
  - Session bookmarks/saves
  - Actual attendance patterns
  - Live session popularity
  - Behavioral signals

**8. Session Reminders**
- Push notifications 15min before session
- Email digest of daily recommended schedule
- In-app reminders for bookmarked sessions

**9. Collaborative Filtering**
- "Attendees similar to you also liked..."
- "Your connections are attending..."
- Trending sessions among similar profiles

**10. Analytics for Organizers**
- Recommendation acceptance rate
- Session discovery metrics
- Popular recommendation paths
- Underperforming session alerts

#### Nice-to-Have Features (Phase 3)

**11. Multi-Format Recommendations**
- Mix live sessions, on-demand content, workshops
- Hybrid event support (virtual + in-person)
- Cross-format discovery

**12. Contextual Timing**
- Recommend sessions based on:
  - Current time of day
  - User's physical location (if on-site)
  - Energy levels (morning vs. afternoon)

**13. Social Proof Integration**
- "3 of your connections attending"
- "Highly rated by similar attendees"
- Speaker credibility indicators

**14. Content Similarity Engine**
- "If you liked Session A, you'll like Session B"
- Build session similarity graph
- Sequential recommendation chains

**15. Predictive Capacity Management**
- Alert when recommended session near capacity
- Suggest similar sessions with availability
- Help organizers optimize room sizes

---

### Speaker Recommendations

#### Must-Have Features (MVP - Phase 1)

**1. Expertise-Based Matching**
- Match attendee needs/interests to speaker expertise
- Semantic understanding of expertise domains
- Multi-dimensional scoring (not binary)

**2. Goal Alignment**
- Match attendee goals to speaker profiles
- Examples:
  - HIRE goal → speakers with hiring experience
  - GET_MENTORED → speakers offering mentorship
  - LEARN_ABOUT_X → speakers expert in X

**3. Speaker Discovery**
- Surface lesser-known speakers with relevant expertise
- Avoid echo chamber (not just popular speakers)
- Diversity in recommendations

**4. Connection Suggestions**
- Recommend 1:1 meeting requests
- Generate conversation starters
- Suggest networking touchpoints

**5. Speaker Metadata**
- Name, title, company, bio
- Expertise areas, topics
- Sessions they're presenting
- Availability for meetings

#### Should-Have Features (Phase 2)

**6. 1:1 Meeting Scheduling**
- Recommend optimal meeting times
- Integrate with calendar availability
- Auto-generate meeting requests

**7. Post-Session Follow-Ups**
- Suggest connecting after their session
- Generate context-aware follow-up messages
- Track speaker-attendee connections

**8. Speaker Session Cross-Promotion**
- "This speaker is also presenting at..."
- Build speaker-session recommendation graph
- Multi-session speaker discovery

**9. Complementary Speaker Suggestions**
- "If you're meeting Speaker A, also consider Speaker B"
- Find speakers with complementary expertise
- Build speaker network graphs

**10. Speaker Analytics**
- Most recommended speakers
- Speaker-attendee match quality
- Connection acceptance rates
- Meeting completion rates

#### Nice-to-Have Features (Phase 3)

**11. AI-Powered Speaker Intros**
- Generate personalized introduction emails
- Context from both profiles
- Mutual value propositions

**12. Speaker Portfolio Recommendations**
- Recommend content from speaker's portfolio
- Blog posts, papers, previous talks
- Deep-dive learning paths

**13. Group Meeting Suggestions**
- Recommend group sessions with multiple speakers
- "These 3 speakers + you would make a great panel discussion"
- Facilitate emergent programming

**14. Speaker Reputation Signals**
- Session ratings, attendee feedback
- Social proof (LinkedIn, Twitter)
- Past event performance

**15. Video/Content Recommendations**
- Past session recordings from speaker
- Related content in event library
- On-demand learning paths

---

## Technical Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (GlobalConnect)                  │
│  - Session/Speaker Recommendation UI                         │
│  - Personalized Agenda Builder                               │
│  - Bookmark/Save/Dismiss Actions                             │
└────────────────────┬────────────────────────────────────────┘
                     │ REST API
                     │
┌────────────────────▼────────────────────────────────────────┐
│              Real-Time Service (NestJS)                      │
│  - Recommendations Controller & Service                      │
│  - Caching Layer (Redis + PostgreSQL)                        │
│  - Event Listeners (check-in, session-join)                 │
│  - Background Jobs (refresh, cleanup)                        │
│  - Analytics & Tracking                                      │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP/REST
                     │
┌────────────────────▼────────────────────────────────────────┐
│              Oracle AI Service (Python/FastAPI)              │
│  - Session Matchmaking Engine                                │
│  - Speaker Matchmaking Engine                                │
│  - LLM-based Semantic Matching (Claude)                      │
│  - Fallback Algorithmic Matching                             │
│  - Reason Generation                                         │
│  - Conversation Starter Generation                           │
└──────────────────────────────────────────────────────────────┘
```

### Service Responsibilities

#### Frontend (GlobalConnect - React/Next.js)

**New Components:**
```
/src/components/features/session-recommendations/
  ├── SessionRecommendations.tsx          # Main component
  ├── SessionRecommendationCard.tsx       # Individual session card
  ├── PersonalizedAgenda.tsx              # Agenda builder
  ├── SessionFilters.tsx                  # Filter controls
  └── SessionBookmarkActions.tsx          # Save/dismiss actions

/src/components/features/speaker-recommendations/
  ├── SpeakerRecommendations.tsx          # Main component
  ├── SpeakerRecommendationCard.tsx       # Individual speaker card
  ├── SpeakerProfileModal.tsx             # Speaker details
  └── MeetingRequestButton.tsx            # 1:1 meeting request

/src/hooks/
  ├── use-session-recommendations.ts      # Session recs hook
  └── use-speaker-recommendations.ts      # Speaker recs hook
```

**State Management:**
```typescript
interface SessionRecommendation {
  id: string;
  sessionId: string;
  matchScore: number;                    // 0-100
  reasons: string[];                     // ["Interest match: AI", ...]
  session: {
    id: string;
    title: string;
    description: string;
    startTime: DateTime;
    endTime: DateTime;
    location: string;
    track: string;
    speakers: Speaker[];
    tags: string[];
    capacity: number;
    currentAttendance: number;
  };

  // User actions
  bookmarked: boolean;
  dismissed: boolean;
  attended: boolean;

  // Metadata
  generatedAt: DateTime;
  expiresAt: DateTime;
}

interface SpeakerRecommendation {
  id: string;
  speakerId: string;
  matchScore: number;                    // 0-100
  reasons: string[];                     // ["Expertise match: ML", ...]
  conversationStarters: string[];        // Generated icebreakers
  speaker: {
    id: string;
    name: string;
    title: string;
    company: string;
    bio: string;
    expertise: string[];
    sessions: Session[];                 // Sessions they're presenting
    availableForMeetings: boolean;
  };

  // User actions
  contacted: boolean;
  meetingScheduled: boolean;
  dismissed: boolean;

  // Metadata
  generatedAt: DateTime;
  expiresAt: DateTime;
}
```

#### Real-Time Service (NestJS)

**New Modules:**
```
/src/recommendations/
  ├── sessions/
  │   ├── sessions-recommendations.controller.ts
  │   ├── sessions-recommendations.service.ts
  │   ├── sessions-recommendations.listener.ts
  │   ├── sessions-recommendations.scheduler.ts
  │   └── dto/
  │       ├── session-recommendation.dto.ts
  │       └── session-filters.dto.ts
  │
  └── speakers/
      ├── speakers-recommendations.controller.ts
      ├── speakers-recommendations.service.ts
      ├── speakers-recommendations.listener.ts
      └── dto/
          ├── speaker-recommendation.dto.ts
          └── meeting-request.dto.ts
```

**Key Services:**

**SessionsRecommendationsService:**
```typescript
class SessionsRecommendationsService {
  // Main methods
  async getRecommendations(userId, eventId, filters?): Promise<SessionRecommendation[]>
  async generateAndStore(userId, eventId): Promise<SessionRecommendation[]>
  async bookmarkSession(recommendationId): Promise<void>
  async dismissSession(recommendationId): Promise<void>
  async trackAttendance(recommendationId): Promise<void>

  // Analytics
  async getAnalytics(eventId): Promise<RecommendationAnalytics>

  // Cache management
  private async getCachedRecommendations(userId, eventId)
  private async cacheRecommendations(userId, eventId, recs)
  private async invalidateCache(userId, eventId)
}
```

**SpeakersRecommendationsService:**
```typescript
class SpeakersRecommendationsService {
  // Main methods
  async getRecommendations(userId, eventId): Promise<SpeakerRecommendation[]>
  async generateAndStore(userId, eventId): Promise<SpeakerRecommendation[]>
  async requestMeeting(recommendationId, message?): Promise<void>
  async dismissSpeaker(recommendationId): Promise<void>

  // Analytics
  async getAnalytics(eventId): Promise<SpeakerAnalytics>
}
```

**Caching Strategy:**
```typescript
// Three-tier caching (same as networking recommendations)

// 1. Redis Cache (5min TTL)
const cacheKey = `session-recs:${userId}:${eventId}`;
const cached = await redis.get(cacheKey);
if (cached) return JSON.parse(cached);

// 2. Database (24h valid recommendations)
const dbRecs = await prisma.sessionRecommendation.findMany({
  where: {
    userId,
    eventId,
    expiresAt: { gte: new Date() }
  }
});
if (dbRecs.length > 0) {
  await redis.set(cacheKey, JSON.stringify(dbRecs), 'EX', 300);
  return dbRecs;
}

// 3. Generate fresh via Oracle AI
const freshRecs = await this.generateAndStore(userId, eventId);
await redis.set(cacheKey, JSON.stringify(freshRecs), 'EX', 300);
return freshRecs;
```

**Event Listeners:**
```typescript
// Trigger session recommendations on check-in
@EventPattern('platform.analytics.check-in.v1')
async handleCheckIn(payload: CheckInEvent) {
  // Generate session recommendations asynchronously
  await this.sessionsService.generateAndStore(
    payload.userId,
    payload.eventId
  );

  // Also generate speaker recommendations
  await this.speakersService.generateAndStore(
    payload.userId,
    payload.eventId
  );
}

// Re-rank on session join
@EventPattern('platform.analytics.session-join.v1')
async handleSessionJoin(payload: SessionJoinEvent) {
  // Invalidate cache to trigger re-ranking
  await this.sessionsService.invalidateCache(
    payload.userId,
    payload.eventId
  );
}
```

**Background Schedulers:**
```typescript
// Daily refresh for active events
@Cron('0 2 * * *') // 2 AM daily
async refreshRecommendations() {
  const activeEvents = await this.getActiveEvents();

  for (const event of activeEvents) {
    const users = await this.getActiveUsersForEvent(event.id);

    for (const user of users) {
      await this.sessionsService.generateAndStore(user.id, event.id);
      await this.speakersService.generateAndStore(user.id, event.id);

      // Stagger to avoid overwhelming Oracle AI
      await sleep(500);
    }
  }
}

// Cleanup expired recommendations
@Cron('0 */6 * * *') // Every 6 hours
async cleanupExpired() {
  await prisma.sessionRecommendation.deleteMany({
    where: { expiresAt: { lt: new Date() } }
  });

  await prisma.speakerRecommendation.deleteMany({
    where: { expiresAt: { lt: new Date() } }
  });
}
```

#### Oracle AI Service (Python/FastAPI)

**New Modules:**
```
/app/features/
  ├── session_recommendations/
  │   ├── router.py                      # FastAPI routes
  │   ├── service.py                     # Business logic
  │   ├── llm_matcher.py                 # LLM-based matching
  │   ├── algorithms.py                  # Fallback algorithms
  │   └── schemas.py                     # Pydantic models
  │
  └── speaker_recommendations/
      ├── router.py
      ├── service.py
      ├── llm_matcher.py
      ├── algorithms.py
      └── schemas.py
```

**Key Components:**

**Session Matching Service:**
```python
class SessionMatchmakingService:
    """
    Matches users to sessions using dual-strategy approach.
    """

    async def match_sessions(
        self,
        user_profile: UserProfile,
        sessions: list[Session],
        max_matches: int = 10
    ) -> list[SessionMatch]:
        """
        Primary: LLM-based semantic matching
        Fallback: Algorithmic matching
        """
        try:
            # Try LLM first
            matches = await self.llm_match_sessions(
                user_profile,
                sessions,
                max_matches
            )
        except Exception as e:
            logger.warning(f"LLM matching failed: {e}, using fallback")
            # Fallback to algorithmic
            matches = self.algorithmic_match_sessions(
                user_profile,
                sessions,
                max_matches
            )

        return matches

    async def llm_match_sessions(
        self,
        user_profile: UserProfile,
        sessions: list[Session],
        max_matches: int
    ) -> list[SessionMatch]:
        """
        Use Claude to semantically understand:
        - User interests, goals, learning objectives
        - Session content, topics, outcomes
        - Match quality and reasoning
        """
        prompt = self._build_matching_prompt(user_profile, sessions)

        response = await anthropic_client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )

        # Parse structured output
        matches = self._parse_llm_response(response.content[0].text)
        return matches[:max_matches]

    def algorithmic_match_sessions(
        self,
        user_profile: UserProfile,
        sessions: list[Session],
        max_matches: int
    ) -> list[SessionMatch]:
        """
        Fallback algorithm:
        - Jaccard similarity on tags/topics
        - Goal alignment scoring
        - Role/track matching
        - Difficulty level matching
        """
        matches = []

        for session in sessions:
            score = 0.0
            reasons = []

            # Interest/tag overlap (40% weight)
            interest_score = self._jaccard_similarity(
                user_profile.interests,
                session.tags
            )
            score += interest_score * 0.4
            if interest_score > 0.3:
                reasons.append(f"Shared interests: {self._get_overlap(user_profile.interests, session.tags)}")

            # Goal alignment (30% weight)
            goal_score = self._match_goals(user_profile.goals, session.outcomes)
            score += goal_score * 0.3
            if goal_score > 0:
                reasons.append(f"Aligns with your learning goals")

            # Role/track matching (20% weight)
            if user_profile.role.lower() in session.target_audience:
                score += 0.2
                reasons.append(f"Designed for {user_profile.role}s")

            # Difficulty matching (10% weight)
            if session.difficulty == user_profile.preferred_difficulty:
                score += 0.1
                reasons.append(f"Matches your {session.difficulty} level preference")

            matches.append(SessionMatch(
                session_id=session.id,
                match_score=int(score * 100),
                reasons=reasons,
                session=session
            ))

        # Sort by score and return top matches
        matches.sort(key=lambda m: m.match_score, reverse=True)
        return matches[:max_matches]

    def _jaccard_similarity(self, set1: list[str], set2: list[str]) -> float:
        """Calculate Jaccard index between two sets."""
        s1 = set(item.lower() for item in set1)
        s2 = set(item.lower() for item in set2)

        if not s1 or not s2:
            return 0.0

        intersection = len(s1 & s2)
        union = len(s1 | s2)

        return intersection / union if union > 0 else 0.0
```

**Speaker Matching Service:**
```python
class SpeakerMatchmakingService:
    """
    Matches users to speakers using dual-strategy approach.
    """

    async def match_speakers(
        self,
        user_profile: UserProfile,
        speakers: list[Speaker],
        max_matches: int = 10
    ) -> list[SpeakerMatch]:
        """
        Primary: LLM-based semantic matching
        Fallback: Algorithmic matching
        """
        try:
            matches = await self.llm_match_speakers(
                user_profile,
                speakers,
                max_matches
            )
        except Exception as e:
            logger.warning(f"LLM matching failed: {e}, using fallback")
            matches = self.algorithmic_match_speakers(
                user_profile,
                speakers,
                max_matches
            )

        return matches

    async def llm_match_speakers(
        self,
        user_profile: UserProfile,
        speakers: list[Speaker],
        max_matches: int
    ) -> list[SpeakerMatch]:
        """
        Use Claude to understand:
        - User needs, goals, interests
        - Speaker expertise, experience, offerings
        - Potential value of connection
        - Conversation opportunities
        """
        prompt = self._build_speaker_matching_prompt(user_profile, speakers)

        response = await anthropic_client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )

        matches = self._parse_speaker_llm_response(response.content[0].text)

        # Generate conversation starters for each match
        for match in matches[:max_matches]:
            match.conversation_starters = await self.generate_conversation_starters(
                user_profile,
                match.speaker,
                match.reasons
            )

        return matches[:max_matches]

    async def generate_conversation_starters(
        self,
        user_profile: UserProfile,
        speaker: Speaker,
        match_reasons: list[str]
    ) -> list[str]:
        """
        Generate personalized conversation starters.
        """
        prompt = f"""
        Generate 3 personalized conversation starters for this connection:

        Attendee Profile:
        - Name: {user_profile.name}
        - Role: {user_profile.role}
        - Interests: {", ".join(user_profile.interests)}
        - Goals: {", ".join(user_profile.goals)}

        Speaker Profile:
        - Name: {speaker.name}
        - Title: {speaker.title}
        - Company: {speaker.company}
        - Expertise: {", ".join(speaker.expertise)}

        Match Reasons: {", ".join(match_reasons)}

        Generate 3 specific, engaging conversation starters that:
        1. Reference shared interests or complementary expertise
        2. Are open-ended and encourage dialogue
        3. Show genuine interest and context awareness
        4. Are professional but warm

        Format as JSON array of strings.
        """

        response = await anthropic_client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        try:
            starters = json.loads(response.content[0].text)
            return starters[:3]
        except:
            # Fallback to template-based
            return self._template_conversation_starters(
                user_profile,
                speaker,
                match_reasons
            )

    def _template_conversation_starters(
        self,
        user_profile: UserProfile,
        speaker: Speaker,
        match_reasons: list[str]
    ) -> list[str]:
        """
        Fallback template-based conversation starters.
        """
        starters = []

        # Interest-based
        common_interests = set(user_profile.interests) & set(speaker.expertise)
        if common_interests:
            interest = list(common_interests)[0]
            starters.append(
                f"I noticed we both share an interest in {interest}. "
                f"What's been your most impactful project in this area?"
            )

        # Goal-based
        if "MENTOR" in user_profile.goals or "GET_MENTORED" in user_profile.goals:
            starters.append(
                f"I'm looking to grow in {user_profile.interests[0] if user_profile.interests else 'this field'}. "
                f"What advice would you give to someone in my position?"
            )

        # Session-based
        if speaker.sessions:
            starters.append(
                f"I'm really looking forward to your session on {speaker.sessions[0].title}. "
                f"What's the key takeaway you hope attendees will leave with?"
            )

        # Generic professional
        if len(starters) < 3:
            starters.append(
                f"What's been the most exciting development in {speaker.expertise[0] if speaker.expertise else 'your field'} recently?"
            )

        return starters[:3]

    def algorithmic_match_speakers(
        self,
        user_profile: UserProfile,
        speakers: list[Speaker],
        max_matches: int
    ) -> list[SpeakerMatch]:
        """
        Fallback algorithm:
        - Expertise-to-interest matching
        - Goal-to-offering alignment
        - Role complementarity
        - Industry matching
        """
        matches = []

        for speaker in speakers:
            score = 0.0
            reasons = []

            # Expertise matching (50% weight)
            expertise_overlap = set(user_profile.interests) & set(speaker.expertise)
            if expertise_overlap:
                expertise_score = len(expertise_overlap) / max(len(user_profile.interests), 1)
                score += expertise_score * 0.5
                reasons.append(f"Expert in: {', '.join(list(expertise_overlap)[:2])}")

            # Skills exchange (30% weight)
            if user_profile.skills_needed:
                skills_match = set(user_profile.skills_needed) & set(speaker.expertise)
                if skills_match:
                    score += 0.3
                    reasons.append(f"Can help with: {', '.join(list(skills_match)[:2])}")

            # Goal alignment (15% weight)
            if self._check_goal_compatibility(user_profile.goals, speaker):
                score += 0.15
                reasons.append("Goal alignment")

            # Industry (5% weight)
            if user_profile.industry == speaker.industry:
                score += 0.05
                reasons.append(f"Same industry: {speaker.industry}")

            matches.append(SpeakerMatch(
                speaker_id=speaker.id,
                match_score=int(score * 100),
                reasons=reasons,
                speaker=speaker,
                conversation_starters=self._template_conversation_starters(
                    user_profile,
                    speaker,
                    reasons
                )
            ))

        matches.sort(key=lambda m: m.match_score, reverse=True)
        return matches[:max_matches]
```

---

## Implementation Phases

### Phase 1: MVP (2-3 weeks) 🟢

**Goal:** Basic session recommendations with LLM matching

#### Backend Tasks

**Oracle AI Service:**
- [ ] Create `/app/features/session_recommendations/` module
- [ ] Implement `SessionMatchmakingService` with LLM + fallback
- [ ] Create FastAPI endpoints:
  - `POST /oracle/sessions/match` - Match user to sessions
- [ ] Add Pydantic schemas for request/response
- [ ] Write unit tests for matching algorithms
- [ ] Add circuit breaker for LLM failures

**Real-Time Service:**
- [ ] Create `/src/recommendations/sessions/` module
- [ ] Implement `SessionsRecommendationsService`:
  - `getRecommendations()` with three-tier caching
  - `generateAndStore()` calling Oracle AI
  - `bookmarkSession()` tracking
  - `dismissSession()` tracking
- [ ] Create Prisma schema for `SessionRecommendation` table
- [ ] Implement Redis caching (5min TTL)
- [ ] Create REST endpoints:
  - `GET /events/:eventId/sessions/recommendations`
  - `POST /recommendations/sessions/:id/bookmark`
  - `POST /recommendations/sessions/:id/dismiss`
- [ ] Add event listener for check-in events
- [ ] Write integration tests

#### Frontend Tasks

**GlobalConnect:**
- [ ] Create `use-session-recommendations.ts` hook
- [ ] Build `SessionRecommendations.tsx` component
- [ ] Build `SessionRecommendationCard.tsx` component
- [ ] Add bookmark/dismiss UI actions
- [ ] Integrate into event detail page
- [ ] Add loading states and error handling
- [ ] Write component tests

#### Data Requirements

- [ ] Seed test events with 20+ sessions
- [ ] Add session metadata (title, description, tags, speakers)
- [ ] Create session-speaker relationships
- [ ] Add difficulty levels, tracks, time slots

#### Success Criteria

- ✅ Users see 5-10 recommended sessions on event page
- ✅ Recommendations include match scores and reasons
- ✅ Users can bookmark/dismiss recommendations
- ✅ System uses LLM when available, falls back gracefully
- ✅ Recommendations cached for performance
- ✅ <500ms response time for cached recommendations

---

### Phase 2: Production Features (4-6 weeks) 🟡

**Goal:** Full feature parity with competitors + speaker recommendations

#### Session Enhancements

**Backend:**
- [ ] Implement real-time re-ranking based on behavior
- [ ] Add collaborative filtering ("Similar attendees liked...")
- [ ] Create personalized agenda builder endpoint
- [ ] Add conflict detection and alternative suggestions
- [ ] Implement session reminder system
- [ ] Build analytics dashboard for organizers
- [ ] Add background scheduler for daily refresh
- [ ] Implement cleanup job for expired recommendations

**Frontend:**
- [ ] Build `PersonalizedAgenda.tsx` component
- [ ] Add session filters (track, time, difficulty)
- [ ] Implement bookmark reminder system
- [ ] Create session conflict resolver UI
- [ ] Add "Similar sessions" carousel
- [ ] Build organizer analytics dashboard

#### Speaker Recommendations

**Backend (Oracle AI):**
- [ ] Create `/app/features/speaker_recommendations/` module
- [ ] Implement `SpeakerMatchmakingService`
- [ ] Add conversation starter generation
- [ ] Create FastAPI endpoints:
  - `POST /oracle/speakers/match`
  - `POST /oracle/speakers/conversation-starters`

**Backend (Real-Time):**
- [ ] Create `/src/recommendations/speakers/` module
- [ ] Implement `SpeakersRecommendationsService`
- [ ] Create Prisma schema for `SpeakerRecommendation` table
- [ ] Create REST endpoints:
  - `GET /events/:eventId/speakers/recommendations`
  - `POST /recommendations/speakers/:id/request-meeting`
  - `POST /recommendations/speakers/:id/dismiss`
- [ ] Add analytics endpoints

**Frontend:**
- [ ] Create `use-speaker-recommendations.ts` hook
- [ ] Build `SpeakerRecommendations.tsx` component
- [ ] Build `SpeakerRecommendationCard.tsx` with conversation starters
- [ ] Add meeting request flow
- [ ] Integrate into event page

#### Database Migrations

```sql
-- Session Recommendations table
CREATE TABLE session_recommendations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  event_id UUID NOT NULL REFERENCES events(id),
  session_id UUID NOT NULL REFERENCES sessions(id),

  match_score INTEGER NOT NULL CHECK (match_score >= 0 AND match_score <= 100),
  reasons TEXT[] NOT NULL DEFAULT '{}',

  bookmarked BOOLEAN NOT NULL DEFAULT false,
  bookmarked_at TIMESTAMP,
  dismissed BOOLEAN NOT NULL DEFAULT false,
  dismissed_at TIMESTAMP,
  attended BOOLEAN NOT NULL DEFAULT false,
  attended_at TIMESTAMP,

  generated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMP NOT NULL DEFAULT NOW() + INTERVAL '24 hours',

  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

  UNIQUE(user_id, event_id, session_id)
);

CREATE INDEX idx_session_recs_user_event ON session_recommendations(user_id, event_id);
CREATE INDEX idx_session_recs_expiry ON session_recommendations(event_id, expires_at);

-- Speaker Recommendations table
CREATE TABLE speaker_recommendations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  event_id UUID NOT NULL REFERENCES events(id),
  speaker_id UUID NOT NULL REFERENCES users(id), -- Assuming speakers are users

  match_score INTEGER NOT NULL CHECK (match_score >= 0 AND match_score <= 100),
  reasons TEXT[] NOT NULL DEFAULT '{}',
  conversation_starters TEXT[] NOT NULL DEFAULT '{}',

  contacted BOOLEAN NOT NULL DEFAULT false,
  contacted_at TIMESTAMP,
  meeting_scheduled BOOLEAN NOT NULL DEFAULT false,
  meeting_scheduled_at TIMESTAMP,
  dismissed BOOLEAN NOT NULL DEFAULT false,
  dismissed_at TIMESTAMP,

  generated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMP NOT NULL DEFAULT NOW() + INTERVAL '24 hours',

  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

  UNIQUE(user_id, event_id, speaker_id)
);

CREATE INDEX idx_speaker_recs_user_event ON speaker_recommendations(user_id, event_id);
CREATE INDEX idx_speaker_recs_expiry ON speaker_recommendations(event_id, expires_at);
```

#### Success Criteria

- ✅ Personalized agenda builder with conflict resolution
- ✅ Real-time re-ranking based on user behavior
- ✅ Speaker recommendations with conversation starters
- ✅ Meeting request workflow
- ✅ Organizer analytics dashboard
- ✅ Background jobs running smoothly
- ✅ 95%+ cache hit rate

---

### Phase 3: Competitive Advantage (8-12 weeks) 🔵

**Goal:** Advanced features that differentiate from competitors

#### Advanced Session Features

- [ ] **Multi-format recommendations**
  - Mix live, on-demand, workshops, networking sessions
  - Hybrid event support (virtual + in-person)

- [ ] **Contextual timing**
  - Location-aware recommendations (on-site attendees)
  - Time-of-day optimization (energy levels)

- [ ] **Social proof integration**
  - "3 connections attending this session"
  - "Highly rated by similar attendees"

- [ ] **Content similarity engine**
  - Build session graph based on content overlap
  - "If you liked X, try Y" chains

- [ ] **Predictive capacity management**
  - Alert when session near full
  - Suggest similar sessions with space

- [ ] **A/B testing framework**
  - Test different algorithms
  - Measure recommendation quality

#### Advanced Speaker Features

- [ ] **AI-powered speaker intros**
  - Generate personalized introduction emails
  - Mutual value proposition highlighting

- [ ] **Speaker portfolio recommendations**
  - Recommend speaker's blog posts, papers, talks
  - Deep-dive learning paths

- [ ] **Group meeting suggestions**
  - "These 3 speakers + you = great panel"
  - Facilitate emergent programming

- [ ] **Speaker reputation signals**
  - Session ratings, feedback scores
  - Social proof integration

#### Unique Integration: Networking + Content

**This is your competitive moat - no competitor does this well**

- [ ] **"Attend where your network is"**
  - Recommend sessions where compatible attendees will be
  - Surface networking opportunities within sessions

- [ ] **"Meet this speaker 1:1"**
  - Treat speakers as networking recommendations
  - Apply same matching algorithms

- [ ] **"Your connection recommended this"**
  - Social proof from trusted network
  - Viral discovery loops

- [ ] **Post-session networking**
  - "Connect with 5 attendees who share your takeaway"
  - Session-based networking suggestions

- [ ] **Agenda-optimized networking**
  - Schedule networking meetings around agenda
  - Find gaps for optimal connection times

#### Success Criteria

- ✅ 80%+ content discovery rate (vs. 30% manual)
- ✅ Unique networking-content integration live
- ✅ A/B testing showing recommendation quality
- ✅ Measurable increase in session attendance
- ✅ Positive organizer feedback on differentiation

---

## API Specifications

### Real-Time Service APIs

#### Session Recommendations

**Get Session Recommendations**
```http
GET /events/:eventId/sessions/recommendations
Authorization: Bearer {jwt_token}
Query Params:
  - refresh: boolean (default: false) - Force regeneration
  - track: string (optional) - Filter by track
  - difficulty: string (optional) - Filter by difficulty
  - timeSlot: string (optional) - Filter by time slot
  - limit: number (default: 10) - Max recommendations

Response 200:
{
  "recommendations": [
    {
      "id": "rec_abc123",
      "sessionId": "session_xyz",
      "matchScore": 85,
      "reasons": [
        "Based on your interest in Machine Learning",
        "Aligns with your goal to learn about AI",
        "Designed for Product Managers"
      ],
      "session": {
        "id": "session_xyz",
        "title": "Advanced ML for Product Teams",
        "description": "...",
        "startTime": "2026-03-15T14:00:00Z",
        "endTime": "2026-03-15T15:30:00Z",
        "location": "Room 301",
        "track": "AI & ML",
        "difficulty": "intermediate",
        "speakers": [
          {
            "id": "speaker_123",
            "name": "Jane Doe",
            "title": "ML Engineer",
            "company": "TechCorp"
          }
        ],
        "tags": ["machine-learning", "product-management", "ai"],
        "capacity": 100,
        "currentAttendance": 47
      },
      "bookmarked": false,
      "dismissed": false,
      "attended": false,
      "generatedAt": "2026-03-14T10:00:00Z",
      "expiresAt": "2026-03-15T10:00:00Z"
    }
  ],
  "metadata": {
    "total": 10,
    "cached": true,
    "generatedAt": "2026-03-14T10:00:00Z"
  }
}
```

**Bookmark Session**
```http
POST /recommendations/sessions/:id/bookmark
Authorization: Bearer {jwt_token}

Response 200:
{
  "success": true,
  "recommendation": { ... }
}
```

**Dismiss Session**
```http
POST /recommendations/sessions/:id/dismiss
Authorization: Bearer {jwt_token}

Response 200:
{
  "success": true
}
```

**Track Session Attendance**
```http
POST /recommendations/sessions/:id/attended
Authorization: Bearer {jwt_token}

Response 200:
{
  "success": true
}
```

**Get Personalized Agenda**
```http
GET /events/:eventId/agenda/personalized
Authorization: Bearer {jwt_token}
Query Params:
  - date: string (optional) - Specific date (YYYY-MM-DD)
  - resolveConflicts: boolean (default: true)

Response 200:
{
  "agenda": [
    {
      "timeSlot": "09:00-10:30",
      "primarySession": { ... },
      "alternatives": [ ... ],  // If conflicts exist
      "reason": "Best match for your interests"
    }
  ],
  "conflicts": [
    {
      "timeSlot": "14:00-15:30",
      "sessions": [ ... ],
      "resolution": "Recommended: Session A (90 score) over Session B (75 score)"
    }
  ]
}
```

**Session Analytics (Organizer)**
```http
GET /events/:eventId/sessions/recommendations/analytics
Authorization: Bearer {jwt_token}
Requires: Organizer role

Response 200:
{
  "overview": {
    "totalRecommendations": 5000,
    "uniqueUsers": 500,
    "bookmarkRate": 0.34,
    "attendanceRate": 0.28,
    "dismissRate": 0.12
  },
  "topSessions": [
    {
      "sessionId": "session_xyz",
      "sessionTitle": "Advanced ML",
      "recommendationCount": 450,
      "bookmarkCount": 180,
      "attendanceCount": 95,
      "avgMatchScore": 82
    }
  ],
  "underperformingSessions": [ ... ],
  "recommendationQuality": {
    "avgMatchScore": 75,
    "bookmarkConversionRate": 0.34,
    "attendanceConversionRate": 0.28
  }
}
```

#### Speaker Recommendations

**Get Speaker Recommendations**
```http
GET /events/:eventId/speakers/recommendations
Authorization: Bearer {jwt_token}
Query Params:
  - refresh: boolean (default: false)
  - limit: number (default: 10)

Response 200:
{
  "recommendations": [
    {
      "id": "rec_speaker_123",
      "speakerId": "speaker_abc",
      "matchScore": 88,
      "reasons": [
        "Expert in Machine Learning - matches your interest",
        "Offers mentorship - aligns with your goal",
        "Similar role: Product Manager"
      ],
      "conversationStarters": [
        "I noticed we both share an interest in ML for product teams. What's been your most impactful project in this area?",
        "I'm looking to grow in AI product management. What advice would you give to someone transitioning into this field?",
        "I'm really looking forward to your session on ML product strategy. What's the key takeaway you hope attendees will leave with?"
      ],
      "speaker": {
        "id": "speaker_abc",
        "name": "Jane Doe",
        "title": "Head of AI Product",
        "company": "TechCorp",
        "bio": "15 years building ML products...",
        "expertise": ["machine-learning", "product-strategy", "ai"],
        "sessions": [
          {
            "id": "session_xyz",
            "title": "ML Product Strategy",
            "startTime": "2026-03-15T14:00:00Z"
          }
        ],
        "availableForMeetings": true
      },
      "contacted": false,
      "meetingScheduled": false,
      "dismissed": false,
      "generatedAt": "2026-03-14T10:00:00Z"
    }
  ]
}
```

**Request Speaker Meeting**
```http
POST /recommendations/speakers/:id/request-meeting
Authorization: Bearer {jwt_token}
Body:
{
  "message": "Hi Jane, I'd love to discuss ML product strategy...",
  "preferredTimes": [
    "2026-03-15T10:00:00Z",
    "2026-03-15T16:00:00Z"
  ]
}

Response 200:
{
  "success": true,
  "meetingRequest": {
    "id": "meeting_req_123",
    "status": "pending",
    "sentAt": "2026-03-14T12:00:00Z"
  }
}
```

**Dismiss Speaker**
```http
POST /recommendations/speakers/:id/dismiss
Authorization: Bearer {jwt_token}

Response 200:
{
  "success": true
}
```

**Speaker Analytics (Organizer)**
```http
GET /events/:eventId/speakers/recommendations/analytics
Authorization: Bearer {jwt_token}
Requires: Organizer role

Response 200:
{
  "overview": {
    "totalRecommendations": 3000,
    "uniqueUsers": 500,
    "contactRate": 0.22,
    "meetingScheduledRate": 0.15,
    "dismissRate": 0.08
  },
  "topSpeakers": [
    {
      "speakerId": "speaker_abc",
      "speakerName": "Jane Doe",
      "recommendationCount": 280,
      "contactCount": 95,
      "meetingCount": 58,
      "avgMatchScore": 85
    }
  ]
}
```

### Oracle AI Service APIs

#### Session Matching

**Match User to Sessions**
```http
POST /oracle/sessions/match
Content-Type: application/json

Request Body:
{
  "user_profile": {
    "user_id": "user_123",
    "interests": ["machine-learning", "product-management"],
    "goals": ["LEARN", "NETWORK"],
    "skills_to_offer": ["python", "data-analysis"],
    "skills_needed": ["ml-ops", "deployment"],
    "role": "Product Manager",
    "industry": "Technology",
    "preferred_difficulty": "intermediate"
  },
  "sessions": [
    {
      "id": "session_xyz",
      "title": "Advanced ML for Product Teams",
      "description": "Learn how to integrate ML into product workflows...",
      "tags": ["machine-learning", "product", "ai"],
      "track": "AI & ML",
      "difficulty": "intermediate",
      "speakers": [
        {
          "name": "Jane Doe",
          "expertise": ["machine-learning", "product-strategy"]
        }
      ],
      "outcomes": ["Understand ML product lifecycle", "Build ML roadmaps"],
      "target_audience": ["Product Manager", "Engineering Manager"]
    }
  ],
  "max_matches": 10,
  "use_llm": true  // Set false to force algorithmic fallback
}

Response 200:
{
  "matches": [
    {
      "session_id": "session_xyz",
      "match_score": 85,
      "reasons": [
        "Strong interest alignment: machine-learning, product-management",
        "Matches your intermediate difficulty preference",
        "Designed for Product Managers",
        "Addresses your learning goal"
      ],
      "session": { ... }
    }
  ],
  "algorithm_used": "llm",  // or "algorithmic"
  "processing_time_ms": 1250
}
```

#### Speaker Matching

**Match User to Speakers**
```http
POST /oracle/speakers/match
Content-Type: application/json

Request Body:
{
  "user_profile": {
    "user_id": "user_123",
    "interests": ["machine-learning", "product-management"],
    "goals": ["GET_MENTORED", "NETWORK"],
    "skills_needed": ["ml-strategy"],
    "role": "Product Manager",
    "industry": "Technology"
  },
  "speakers": [
    {
      "id": "speaker_abc",
      "name": "Jane Doe",
      "title": "Head of AI Product",
      "company": "TechCorp",
      "expertise": ["machine-learning", "product-strategy", "mentorship"],
      "industry": "Technology",
      "offerings": ["mentorship", "consulting"],
      "sessions": [ ... ],
      "available_for_meetings": true
    }
  ],
  "max_matches": 10,
  "use_llm": true
}

Response 200:
{
  "matches": [
    {
      "speaker_id": "speaker_abc",
      "match_score": 88,
      "reasons": [
        "Expert in machine-learning - matches your interest",
        "Offers mentorship - aligns with GET_MENTORED goal",
        "Same industry: Technology",
        "Can help with: ml-strategy"
      ],
      "speaker": { ... }
    }
  ],
  "algorithm_used": "llm",
  "processing_time_ms": 1450
}
```

**Generate Conversation Starters**
```http
POST /oracle/speakers/conversation-starters
Content-Type: application/json

Request Body:
{
  "user_profile": {
    "name": "John Smith",
    "role": "Product Manager",
    "interests": ["machine-learning", "product-strategy"],
    "goals": ["GET_MENTORED"]
  },
  "speaker": {
    "name": "Jane Doe",
    "title": "Head of AI Product",
    "company": "TechCorp",
    "expertise": ["machine-learning", "product-strategy"],
    "sessions": [
      {
        "title": "ML Product Strategy"
      }
    ]
  },
  "match_reasons": [
    "Expert in machine-learning",
    "Offers mentorship"
  ]
}

Response 200:
{
  "conversation_starters": [
    "I noticed we both share an interest in ML for product teams. What's been your most impactful project in this area?",
    "I'm looking to grow in AI product management. What advice would you give to someone transitioning into this field?",
    "I'm really looking forward to your session on ML product strategy. What's the key takeaway you hope attendees will leave with?"
  ],
  "generation_method": "llm",  // or "template"
  "processing_time_ms": 850
}
```

---

## Database Schema

### Prisma Schema Extensions

```prisma
// Add to existing schema.prisma

model Session {
  id                  String   @id @default(uuid())
  eventId             String
  event               Event    @relation(fields: [eventId], references: [id], onDelete: Cascade)

  title               String
  description         String
  startTime           DateTime
  endTime             DateTime
  location            String?
  virtualLink         String?

  track               String?
  difficulty          String?  // "beginner" | "intermediate" | "advanced"
  tags                String[]
  outcomes            String[]  // Learning outcomes
  targetAudience      String[]  // Roles this session targets

  capacity            Int?
  currentAttendance   Int      @default(0)

  speakers            SessionSpeaker[]
  recommendations     SessionRecommendation[]
  attendances         SessionAttendance[]

  createdAt           DateTime @default(now())
  updatedAt           DateTime @updatedAt

  @@index([eventId])
  @@index([eventId, startTime])
  @@index([track])
}

model SessionSpeaker {
  id         String   @id @default(uuid())
  sessionId  String
  session    Session  @relation(fields: [sessionId], references: [id], onDelete: Cascade)
  speakerId  String
  speaker    User     @relation(fields: [speakerId], references: [id], onDelete: Cascade)

  role       String?  // "keynote" | "panelist" | "moderator"

  @@unique([sessionId, speakerId])
  @@index([speakerId])
}

model SessionRecommendation {
  id                  String    @id @default(uuid())
  userId              String
  user                User      @relation(fields: [userId], references: [id], onDelete: Cascade)
  eventId             String
  event               Event     @relation(fields: [eventId], references: [id], onDelete: Cascade)
  sessionId           String
  session             Session   @relation(fields: [sessionId], references: [id], onDelete: Cascade)

  matchScore          Int       // 0-100
  reasons             String[]

  // User actions
  bookmarked          Boolean   @default(false)
  bookmarkedAt        DateTime?
  dismissed           Boolean   @default(false)
  dismissedAt         DateTime?
  attended            Boolean   @default(false)
  attendedAt          DateTime?

  // Lifecycle
  generatedAt         DateTime  @default(now())
  expiresAt           DateTime  // 24 hours from generation

  createdAt           DateTime  @default(now())
  updatedAt           DateTime  @updatedAt

  @@unique([userId, eventId, sessionId])
  @@index([userId, eventId])
  @@index([eventId, expiresAt])
  @@index([sessionId])
}

model SpeakerRecommendation {
  id                    String    @id @default(uuid())
  userId                String
  user                  User      @relation(fields: [userId], references: [id], onDelete: Cascade)
  eventId               String
  event                 Event     @relation(fields: [eventId], references: [id], onDelete: Cascade)
  speakerId             String
  speaker               User      @relation("SpeakerRecommendations", fields: [speakerId], references: [id], onDelete: Cascade)

  matchScore            Int       // 0-100
  reasons               String[]
  conversationStarters  String[]

  // User actions
  contacted             Boolean   @default(false)
  contactedAt           DateTime?
  meetingScheduled      Boolean   @default(false)
  meetingScheduledAt    DateTime?
  dismissed             Boolean   @default(false)
  dismissedAt           DateTime?

  // Lifecycle
  generatedAt           DateTime  @default(now())
  expiresAt             DateTime  // 24 hours from generation

  createdAt             DateTime  @default(now())
  updatedAt             DateTime  @updatedAt

  @@unique([userId, eventId, speakerId])
  @@index([userId, eventId])
  @@index([eventId, expiresAt])
  @@index([speakerId])
}

model SessionAttendance {
  id         String   @id @default(uuid())
  userId     String
  user       User     @relation(fields: [userId], references: [id], onDelete: Cascade)
  sessionId  String
  session    Session  @relation(fields: [sessionId], references: [id], onDelete: Cascade)
  eventId    String
  event      Event    @relation(fields: [eventId], references: [id], onDelete: Cascade)

  joinedAt   DateTime @default(now())
  leftAt     DateTime?
  duration   Int?     // Minutes attended

  @@unique([userId, sessionId])
  @@index([sessionId])
  @@index([userId, eventId])
}

// Extend existing User model
model User {
  // ... existing fields ...

  // New relationships
  speakingSessions        SessionSpeaker[]
  sessionRecommendations  SessionRecommendation[]
  speakerRecommendations  SpeakerRecommendation[]
  speakerRecsReceived     SpeakerRecommendation[] @relation("SpeakerRecommendations")
  sessionAttendances      SessionAttendance[]
}

// Extend existing Event model
model Event {
  // ... existing fields ...

  // New relationships
  sessions                Session[]
  sessionRecommendations  SessionRecommendation[]
  speakerRecommendations  SpeakerRecommendation[]
  sessionAttendances      SessionAttendance[]
}
```

### Migration Strategy

```bash
# Create migration
npx prisma migrate dev --name add_session_speaker_recommendations

# Generate Prisma client
npx prisma generate

# Seed test data
npm run seed:sessions
```

---

## Algorithm Details

### Session Matching Algorithm

#### LLM-Based Matching (Primary)

**Prompt Template:**
```python
SYSTEM_PROMPT = """
You are an expert event recommendation system. Your task is to match attendees
to sessions based on deep semantic understanding of their profiles and session content.

Analyze:
1. Interest alignment - Do session topics match user interests?
2. Goal alignment - Does the session help achieve their goals?
3. Skill level - Is the difficulty appropriate?
4. Role relevance - Is it designed for their role?
5. Learning objectives - Do outcomes match their needs?

Output JSON with match scores (0-100) and specific reasons.
"""

USER_PROMPT = f"""
User Profile:
- Interests: {user.interests}
- Goals: {user.goals}
- Skills to Offer: {user.skills_to_offer}
- Skills Needed: {user.skills_needed}
- Role: {user.role}
- Industry: {user.industry}
- Preferred Difficulty: {user.preferred_difficulty}

Sessions to Match (top {max_matches} only):
{json.dumps(sessions, indent=2)}

Provide JSON array of matches, sorted by score (highest first):
[
  {{
    "session_id": "...",
    "match_score": 85,
    "reasons": [
      "Strong interest alignment: machine-learning",
      "Matches intermediate difficulty preference",
      "Designed for Product Managers"
    ]
  }}
]
"""
```

**Response Processing:**
```python
async def llm_match_sessions(
    user_profile: UserProfile,
    sessions: list[Session],
    max_matches: int = 10
) -> list[SessionMatch]:
    """Use Claude for semantic matching."""

    # Build prompt
    prompt = build_session_matching_prompt(user_profile, sessions, max_matches)

    # Call Claude
    response = await anthropic_client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4000,
        temperature=0.3,  # Lower temperature for consistent matching
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
    )

    # Parse JSON response
    try:
        matches_data = json.loads(response.content[0].text)
        matches = [
            SessionMatch(
                session_id=m["session_id"],
                match_score=m["match_score"],
                reasons=m["reasons"],
                session=next(s for s in sessions if s.id == m["session_id"])
            )
            for m in matches_data[:max_matches]
        ]
        return matches
    except (json.JSONDecodeError, KeyError, StopIteration) as e:
        logger.error(f"Failed to parse LLM response: {e}")
        raise
```

#### Algorithmic Matching (Fallback)

**Multi-Factor Scoring:**
```python
def algorithmic_match_sessions(
    user_profile: UserProfile,
    sessions: list[Session],
    max_matches: int = 10
) -> list[SessionMatch]:
    """Fallback algorithm using weighted scoring."""

    matches = []

    for session in sessions:
        score = 0.0
        reasons = []

        # 1. Interest/Tag Overlap (40% weight)
        interest_score = jaccard_similarity(
            user_profile.interests,
            session.tags
        )
        score += interest_score * 0.4

        if interest_score > 0.3:
            overlaps = get_overlap(user_profile.interests, session.tags)
            reasons.append(f"Shared interests: {', '.join(overlaps[:2])}")

        # 2. Goal Alignment (30% weight)
        goal_score = calculate_goal_alignment(
            user_profile.goals,
            session.outcomes
        )
        score += goal_score * 0.3

        if goal_score > 0:
            reasons.append("Aligns with your learning goals")

        # 3. Role/Audience Match (20% weight)
        if user_profile.role.lower() in [a.lower() for a in session.target_audience]:
            score += 0.2
            reasons.append(f"Designed for {user_profile.role}s")

        # 4. Difficulty Match (10% weight)
        if session.difficulty == user_profile.preferred_difficulty:
            score += 0.1
            reasons.append(f"Matches your {session.difficulty} level preference")
        elif session.difficulty == "intermediate":
            # Intermediate is often acceptable for all
            score += 0.05

        # 5. Skills Match Bonus (+15% max)
        if user_profile.skills_needed:
            skills_taught = extract_skills_from_outcomes(session.outcomes)
            skills_match = set(user_profile.skills_needed) & set(skills_taught)
            if skills_match:
                score += min(0.15, len(skills_match) * 0.05)
                reasons.append(f"Teaches: {', '.join(list(skills_match)[:2])}")

        # Only include sessions with reasonable scores
        if score > 0.2:
            matches.append(SessionMatch(
                session_id=session.id,
                match_score=min(100, int(score * 100)),
                reasons=reasons,
                session=session
            ))

    # Sort by score and return top matches
    matches.sort(key=lambda m: m.match_score, reverse=True)
    return matches[:max_matches]

def jaccard_similarity(list1: list[str], list2: list[str]) -> float:
    """Calculate Jaccard index."""
    set1 = {item.lower() for item in list1}
    set2 = {item.lower() for item in list2}

    if not set1 or not set2:
        return 0.0

    intersection = len(set1 & set2)
    union = len(set1 | set2)

    return intersection / union if union > 0 else 0.0

def calculate_goal_alignment(
    user_goals: list[str],
    session_outcomes: list[str]
) -> float:
    """Check if session outcomes align with user goals."""

    # Map goals to outcome keywords
    goal_keywords = {
        "LEARN": ["learn", "understand", "master", "discover"],
        "NETWORK": ["network", "connect", "meet", "collaborate"],
        "HIRE": ["hire", "recruit", "talent"],
        "GET_HIRED": ["career", "job", "opportunity"],
        "MENTOR": ["mentor", "teach", "guide"],
        "GET_MENTORED": ["learn from", "guided by"],
    }

    score = 0.0
    outcomes_text = " ".join(session_outcomes).lower()

    for goal in user_goals:
        keywords = goal_keywords.get(goal, [])
        if any(kw in outcomes_text for kw in keywords):
            score += 0.3  # Each goal match adds 30%

    return min(1.0, score)
```

### Speaker Matching Algorithm

#### LLM-Based Matching (Primary)

**Prompt Template:**
```python
SPEAKER_SYSTEM_PROMPT = """
You are an expert at matching event attendees with speakers for valuable
professional connections. Analyze both profiles to find meaningful alignment.

Consider:
1. Expertise alignment - Does speaker expertise match attendee interests/needs?
2. Goal compatibility - Can the speaker help achieve attendee goals?
3. Skills exchange - Can speaker offer skills the attendee needs?
4. Role complementarity - Are their roles complementary?
5. Mutual value - What's the potential benefit for both parties?

Output JSON with match scores and specific, actionable reasons.
"""

SPEAKER_USER_PROMPT = f"""
Attendee Profile:
- Name: {user.name}
- Role: {user.role}
- Company: {user.company}
- Interests: {user.interests}
- Goals: {user.goals}
- Skills to Offer: {user.skills_to_offer}
- Skills Needed: {user.skills_needed}
- Industry: {user.industry}

Speakers to Match (top {max_matches} only):
{json.dumps(speakers, indent=2)}

Provide JSON array of matches:
[
  {{
    "speaker_id": "...",
    "match_score": 88,
    "reasons": [
      "Expert in machine-learning - matches your interest",
      "Offers mentorship - aligns with GET_MENTORED goal",
      "Can help with: ml-strategy, deployment"
    ],
    "potential_value": "Could provide guidance on ML product strategy and career growth"
  }}
]
"""
```

#### Algorithmic Matching (Fallback)

```python
def algorithmic_match_speakers(
    user_profile: UserProfile,
    speakers: list[Speaker],
    max_matches: int = 10
) -> list[SpeakerMatch]:
    """Fallback algorithm for speaker matching."""

    matches = []

    for speaker in speakers:
        score = 0.0
        reasons = []

        # 1. Expertise-to-Interest Match (50% weight)
        expertise_overlap = set(user_profile.interests) & set(speaker.expertise)
        if expertise_overlap:
            expertise_score = len(expertise_overlap) / max(len(user_profile.interests), 1)
            score += expertise_score * 0.5
            reasons.append(f"Expert in: {', '.join(list(expertise_overlap)[:2])}")

        # 2. Skills Exchange (30% weight)
        if user_profile.skills_needed:
            skills_match = set(user_profile.skills_needed) & set(speaker.expertise)
            if skills_match:
                score += 0.3
                reasons.append(f"Can help with: {', '.join(list(skills_match)[:2])}")

        # 3. Goal Compatibility (15% weight)
        goal_compatible = check_speaker_goal_compatibility(
            user_profile.goals,
            speaker
        )
        if goal_compatible:
            score += 0.15
            reasons.append(goal_compatible["reason"])

        # 4. Industry Match (5% weight)
        if user_profile.industry == speaker.industry:
            score += 0.05
            reasons.append(f"Same industry: {speaker.industry}")

        # Only include reasonable matches
        if score > 0.2:
            matches.append(SpeakerMatch(
                speaker_id=speaker.id,
                match_score=min(100, int(score * 100)),
                reasons=reasons,
                speaker=speaker,
                conversation_starters=[]  # Will be generated separately
            ))

    matches.sort(key=lambda m: m.match_score, reverse=True)
    return matches[:max_matches]

def check_speaker_goal_compatibility(
    user_goals: list[str],
    speaker: Speaker
) -> dict | None:
    """Check if speaker can help with user goals."""

    # Check if speaker offers what user seeks
    if "GET_MENTORED" in user_goals and "mentorship" in speaker.offerings:
        return {"reason": "Offers mentorship - aligns with your goal"}

    if "HIRE" in user_goals and speaker.role in ["Engineer", "Designer", "Product Manager"]:
        return {"reason": "Potential hiring candidate"}

    if "LEARN" in user_goals and speaker.expertise:
        return {"reason": "Can teach relevant skills"}

    if "NETWORK" in user_goals:
        return {"reason": "Valuable networking connection"}

    return None
```

### Conversation Starter Generation

**LLM-Based (Primary):**
```python
async def generate_conversation_starters(
    user_profile: UserProfile,
    speaker: Speaker,
    match_reasons: list[str]
) -> list[str]:
    """Generate personalized icebreakers using Claude."""

    prompt = f"""
    Generate 3 personalized conversation starters for this introduction:

    Attendee:
    - Name: {user_profile.name}
    - Role: {user_profile.role}
    - Interests: {", ".join(user_profile.interests)}
    - Goals: {", ".join(user_profile.goals)}

    Speaker:
    - Name: {speaker.name}
    - Title: {speaker.title}
    - Company: {speaker.company}
    - Expertise: {", ".join(speaker.expertise)}

    Match Reasons: {", ".join(match_reasons)}

    Generate 3 conversation starters that are:
    1. Specific and personalized (reference shared interests or complementary expertise)
    2. Open-ended (encourage dialogue, not yes/no)
    3. Professional but warm
    4. Show genuine interest and context awareness
    5. 1-2 sentences each

    Return as JSON array: ["starter 1", "starter 2", "starter 3"]
    """

    response = await anthropic_client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=800,
        temperature=0.7,  # Higher temp for creative starters
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        starters = json.loads(response.content[0].text)
        return starters[:3]
    except:
        # Fallback to template-based
        return template_conversation_starters(user_profile, speaker, match_reasons)

def template_conversation_starters(
    user_profile: UserProfile,
    speaker: Speaker,
    match_reasons: list[str]
) -> list[str]:
    """Template-based fallback."""

    starters = []

    # Template 1: Shared interest
    common_interests = set(user_profile.interests) & set(speaker.expertise)
    if common_interests:
        interest = list(common_interests)[0]
        starters.append(
            f"I noticed we both share an interest in {interest}. "
            f"What's been your most impactful project in this area?"
        )

    # Template 2: Goal-based
    if "GET_MENTORED" in user_profile.goals and "mentorship" in speaker.offerings:
        starters.append(
            f"I'm looking to grow in {user_profile.interests[0] if user_profile.interests else 'this field'}. "
            f"What advice would you give to someone in my position?"
        )

    # Template 3: Session-based
    if speaker.sessions:
        starters.append(
            f"I'm really looking forward to your session on {speaker.sessions[0].title}. "
            f"What's the key takeaway you hope attendees will leave with?"
        )

    # Template 4: Generic professional
    if len(starters) < 3:
        starters.append(
            f"What's been the most exciting development in "
            f"{speaker.expertise[0] if speaker.expertise else 'your field'} recently?"
        )

    # Template 5: Company/role specific
    if len(starters) < 3 and speaker.company:
        starters.append(
            f"I'd love to hear about your experience at {speaker.company}. "
            f"What's the most interesting challenge you're working on?"
        )

    return starters[:3]
```

---

## Integration with Existing Systems

### Leverage Existing Infrastructure

#### 1. Reuse Oracle AI Service Architecture

**Current User Networking System:**
```python
# /oracle-ai-service/app/features/networking/service.py
# Already has:
- LLM-based matchmaking
- Fallback algorithmic matching
- Circuit breaker pattern
- Error handling and logging
```

**Adaptation for Sessions/Speakers:**
```python
# Create parallel structure:
/app/features/session_recommendations/
  - service.py          # Reuse patterns from networking/service.py
  - llm_matcher.py      # Reuse LLM calling logic
  - algorithms.py       # Similar fallback algorithms
  - schemas.py          # Pydantic models

/app/features/speaker_recommendations/
  - service.py          # Same patterns
  - llm_matcher.py      # Same LLM integration
  - algorithms.py       # Adapted scoring logic
  - schemas.py          # Speaker-specific models
```

**Code Reuse Strategy:**
```python
# Extract shared utilities
/app/features/shared/
  - llm_client.py       # Shared Anthropic client
  - matching_utils.py   # Common matching functions
  - cache_utils.py      # Shared caching logic
  - circuit_breaker.py  # Reusable circuit breaker

# Example shared utility:
class LLMMatchingService:
    """Base class for all LLM-based matching."""

    def __init__(self):
        self.client = anthropic_client
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            timeout=30
        )

    async def call_llm_with_fallback(
        self,
        prompt: str,
        fallback_fn: Callable,
        **fallback_kwargs
    ):
        """Standardized LLM calling with circuit breaker + fallback."""
        try:
            if self.circuit_breaker.is_open():
                logger.warning("Circuit breaker open, using fallback")
                return fallback_fn(**fallback_kwargs)

            response = await self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )

            self.circuit_breaker.record_success()
            return response

        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(f"LLM call failed: {e}, using fallback")
            return fallback_fn(**fallback_kwargs)
```

#### 2. Reuse Real-Time Service Patterns

**Current Networking Recommendations Structure:**
```typescript
/src/networking/recommendations/
  - recommendations.controller.ts    # REST endpoints
  - recommendations.service.ts       # Business logic + caching
  - recommendations.listener.ts      # Event-driven triggers
  - recommendations.scheduler.ts     # Background jobs
```

**Adaptation for Sessions/Speakers:**
```typescript
// Create parallel modules with SAME patterns:

/src/recommendations/sessions/
  - sessions-recommendations.controller.ts
  - sessions-recommendations.service.ts
  - sessions-recommendations.listener.ts
  - sessions-recommendations.scheduler.ts

/src/recommendations/speakers/
  - speakers-recommendations.controller.ts
  - speakers-recommendations.service.ts
  // (listeners and schedulers can be shared)

// Extract shared base class:
abstract class BaseRecommendationsService<T> {
  constructor(
    protected readonly redis: RedisService,
    protected readonly prisma: PrismaService,
    protected readonly oracleClient: OracleAIClient
  ) {}

  // Shared three-tier caching logic
  async getRecommendations(
    userId: string,
    eventId: string,
    options?: GetRecommendationsOptions
  ): Promise<T[]> {
    // 1. Check Redis
    const cached = await this.getCachedRecommendations(userId, eventId);
    if (cached && !options?.refresh) return cached;

    // 2. Check Database
    const dbRecs = await this.getValidDbRecommendations(userId, eventId);
    if (dbRecs.length > 0) {
      await this.cacheRecommendations(userId, eventId, dbRecs);
      return dbRecs;
    }

    // 3. Generate fresh
    const freshRecs = await this.generateAndStore(userId, eventId);
    await this.cacheRecommendations(userId, eventId, freshRecs);
    return freshRecs;
  }

  // Abstract methods for subclasses to implement
  abstract generateAndStore(userId: string, eventId: string): Promise<T[]>;
  abstract callOracleService(request: any): Promise<T[]>;
}

// Then subclass:
class SessionsRecommendationsService extends BaseRecommendationsService<SessionRecommendation> {
  async generateAndStore(userId: string, eventId: string) {
    // Session-specific logic
  }

  async callOracleService(request: SessionMatchRequest) {
    // Call /oracle/sessions/match
  }
}
```

#### 3. Event-Driven Integration

**Existing Event Patterns:**
```typescript
// Already listening to:
@EventPattern('platform.analytics.check-in.v1')
async handleCheckIn(payload) {
  // Generate user networking recommendations
}
```

**Extend for Sessions/Speakers:**
```typescript
@EventPattern('platform.analytics.check-in.v1')
async handleCheckIn(payload: CheckInEvent) {
  // Generate ALL recommendations in parallel
  await Promise.all([
    this.networkingService.generateRecommendations(payload.userId, payload.eventId),
    this.sessionsService.generateRecommendations(payload.userId, payload.eventId),
    this.speakersService.generateRecommendations(payload.userId, payload.eventId),
  ]);
}

// New event: Session join
@EventPattern('platform.analytics.session-join.v1')
async handleSessionJoin(payload: SessionJoinEvent) {
  // Track attendance
  await this.sessionsService.trackAttendance(
    payload.userId,
    payload.sessionId
  );

  // Invalidate cache to trigger re-ranking
  await this.sessionsService.invalidateCache(
    payload.userId,
    payload.eventId
  );

  // Could also update networking recommendations
  // based on who else is in the session
  await this.networkingService.invalidateCache(
    payload.userId,
    payload.eventId
  );
}
```

#### 4. Analytics Integration

**Existing Analytics Pattern:**
```typescript
// /src/networking/recommendations/recommendations.service.ts
async getAnalytics(eventId: string) {
  // Returns recommendation effectiveness metrics
}
```

**Unified Analytics Dashboard:**
```typescript
// Create unified recommendation analytics
class RecommendationAnalyticsService {
  async getUnifiedAnalytics(eventId: string) {
    const [networking, sessions, speakers] = await Promise.all([
      this.networkingService.getAnalytics(eventId),
      this.sessionsService.getAnalytics(eventId),
      this.speakersService.getAnalytics(eventId),
    ]);

    return {
      networking: networking,
      sessions: sessions,
      speakers: speakers,
      overall: {
        totalRecommendations:
          networking.total + sessions.total + speakers.total,
        avgEngagementRate:
          (networking.engagementRate + sessions.engagementRate + speakers.engagementRate) / 3,
      }
    };
  }
}
```

### Cross-Feature Synergies

#### 1. Session Attendance → Networking Recommendations

**Insight:** People who attend the same session have shared interests

```typescript
@EventPattern('platform.analytics.session-join.v1')
async handleSessionJoin(payload: SessionJoinEvent) {
  // Get other attendees in this session
  const otherAttendees = await this.getSessionAttendees(
    payload.sessionId,
    payload.userId  // Exclude current user
  );

  // Boost networking recommendations for these attendees
  await this.networkingService.boostRecommendations(
    payload.userId,
    otherAttendees.map(a => a.userId),
    {
      reason: `Also attending: ${payload.sessionTitle}`,
      scoreBoost: 15  // +15 points
    }
  );
}
```

#### 2. Networking Connections → Session Recommendations

**Insight:** Recommend sessions your connections are attending

```typescript
async generateSessionRecommendations(userId: string, eventId: string) {
  // Get user's networking connections
  const connections = await this.getConnections(userId, eventId);

  // Get sessions they're attending
  const connectionSessions = await this.getConnectionSessions(
    connections.map(c => c.userId),
    eventId
  );

  // Boost these sessions in recommendations
  const recommendations = await this.baseRecommendations(userId, eventId);

  for (const rec of recommendations) {
    const attendingConnections = connectionSessions.filter(
      cs => cs.sessionId === rec.sessionId
    );

    if (attendingConnections.length > 0) {
      rec.matchScore += Math.min(20, attendingConnections.length * 5);
      rec.reasons.push(
        `${attendingConnections.length} of your connections attending`
      );
    }
  }

  return recommendations;
}
```

#### 3. Speaker Recommendations → Networking Recommendations

**Insight:** Speakers are networking connections too

```typescript
async generateNetworkingRecommendations(userId: string, eventId: string) {
  // Include speakers as potential networking connections
  const speakers = await this.getSpeakers(eventId);
  const regularAttendees = await this.getAttendees(eventId);

  // Combine both pools
  const allCandidates = [...regularAttendees, ...speakers];

  // Call Oracle AI with combined pool
  const recommendations = await this.callOracleService({
    userId,
    candidates: allCandidates,
    // Speakers might get boosted scores due to expertise
  });

  return recommendations;
}
```

#### 4. Unified Recommendation Feed

**Frontend Integration:**
```typescript
// Unified recommendation component
function UnifiedRecommendations({ eventId }) {
  const { data: networking } = useNetworkingRecommendations({ eventId });
  const { data: sessions } = useSessionRecommendations({ eventId });
  const { data: speakers } = useSpeakerRecommendations({ eventId });

  // Interleave all recommendations by match score
  const unified = useMemo(() => {
    const all = [
      ...networking.map(n => ({ ...n, type: 'networking' })),
      ...sessions.map(s => ({ ...s, type: 'session' })),
      ...speakers.map(sp => ({ ...sp, type: 'speaker' })),
    ];

    // Sort by match score
    return all.sort((a, b) => b.matchScore - a.matchScore);
  }, [networking, sessions, speakers]);

  return (
    <div>
      <h2>Recommended for You</h2>
      {unified.map(rec => (
        <RecommendationCard key={rec.id} recommendation={rec} />
      ))}
    </div>
  );
}
```

---

## Success Metrics & Analytics

### Key Performance Indicators (KPIs)

#### 1. Recommendation Quality Metrics

**Match Score Distribution:**
```typescript
interface MatchScoreMetrics {
  avgMatchScore: number;          // Should be >70
  medianMatchScore: number;
  scoreDistribution: {
    low: number;      // 0-50
    medium: number;   // 51-75
    high: number;     // 76-100
  };
}
```

**Recommendation Acceptance Rate:**
```typescript
interface AcceptanceMetrics {
  // Session Recommendations
  sessionBookmarkRate: number;     // Target: >30%
  sessionAttendanceRate: number;   // Target: >25%
  sessionDismissRate: number;      // Target: <15%

  // Speaker Recommendations
  speakerContactRate: number;      // Target: >20%
  speakerMeetingRate: number;      // Target: >15%
  speakerDismissRate: number;      // Target: <10%

  // Networking (for comparison)
  networkingPingRate: number;
  networkingConnectRate: number;
}
```

#### 2. Discovery Metrics

**Content Discovery Rate:**
```typescript
interface DiscoveryMetrics {
  // How much content users discover via recommendations vs. manual
  totalSessionsDiscovered: number;
  discoveredViaRecommendations: number;
  discoveredManually: number;

  discoveryRate: number;  // Target: >80% via recommendations

  // Diversity
  uniqueSessionsRecommended: number;
  uniqueSessionsAttended: number;
  diversityScore: number;  // Prevent echo chamber
}
```

**Session Attendance Impact:**
```typescript
interface AttendanceImpact {
  // Compare sessions with/without recommendations
  avgAttendanceWithRecs: number;
  avgAttendanceWithoutRecs: number;
  attendanceIncrease: number;  // Target: >25%

  // Under-attended sessions boosted by recommendations
  lowAttendanceSessionsBoosted: number;
}
```

#### 3. User Engagement Metrics

**Time-Based Engagement:**
```typescript
interface EngagementMetrics {
  // How quickly users interact with recommendations
  avgTimeToFirstBookmark: number;  // Target: <5 minutes
  avgTimeToFirstDismiss: number;

  // Session engagement
  avgRecommendationsViewed: number;  // Target: >8
  avgRecommendationsActedOn: number; // Target: >3

  // Return engagement
  dailyActiveUsers: number;
  weeklyActiveUsers: number;
  returnRate: number;  // Users who come back to recommendations
}
```

**Funnel Metrics:**
```typescript
interface FunnelMetrics {
  // Session recommendation funnel
  recommendationsGenerated: number;
  recommendationsViewed: number;
  recommendationsBookmarked: number;
  recommendationsAttended: number;

  // Conversion rates
  viewRate: number;      // viewed / generated
  bookmarkRate: number;  // bookmarked / viewed
  attendRate: number;    // attended / bookmarked

  // Overall conversion
  overallConversionRate: number;  // attended / generated
}
```

#### 4. Organizer Value Metrics

**Event Success Metrics:**
```typescript
interface OrganizerMetrics {
  // Session performance
  topRecommendedSessions: Array<{
    sessionId: string;
    recommendationCount: number;
    attendanceRate: number;
    avgRating: number;
  }>;

  underperformingSessions: Array<{
    sessionId: string;
    lowRecommendationReasons: string[];
    suggestedImprovements: string[];
  }>;

  // Content quality insights
  contentGaps: string[];  // Topics users want but aren't offered
  oversubscribedTopics: string[];  // Too many similar sessions

  // Speaker insights
  topSpeakers: Array<{
    speakerId: string;
    recommendationCount: number;
    meetingRequestCount: number;
    avgRating: number;
  }>;
}
```

#### 5. System Performance Metrics

**Technical Performance:**
```typescript
interface PerformanceMetrics {
  // Latency
  avgRecommendationLatency: number;  // Target: <500ms
  p95Latency: number;                // Target: <1000ms
  p99Latency: number;                // Target: <2000ms

  // Cache performance
  cacheHitRate: number;              // Target: >95%
  cacheHitRateRedis: number;
  cacheHitRateDB: number;

  // LLM usage
  llmCallCount: number;
  llmSuccessRate: number;            // Target: >98%
  llmFallbackRate: number;           // Target: <5%

  // Cost metrics
  avgCostPerRecommendation: number;  // In USD
  totalMonthlyCost: number;
}
```

### Analytics Endpoints

#### Session Analytics

```typescript
GET /events/:eventId/sessions/recommendations/analytics

Response:
{
  "overview": {
    "totalRecommendations": 5000,
    "uniqueUsers": 500,
    "avgRecommendationsPerUser": 10,
    "bookmarkRate": 0.34,
    "attendanceRate": 0.28,
    "dismissRate": 0.12
  },

  "topSessions": [
    {
      "sessionId": "session_xyz",
      "title": "Advanced ML",
      "recommendationCount": 450,
      "bookmarkCount": 180,
      "attendanceCount": 95,
      "avgMatchScore": 82,
      "rating": 4.7
    }
  ],

  "underperformingSessions": [
    {
      "sessionId": "session_abc",
      "title": "Intro to Blockchain",
      "recommendationCount": 45,
      "bookmarkCount": 8,
      "attendanceCount": 3,
      "avgMatchScore": 52,
      "reasons": [
        "Topic doesn't match attendee interests",
        "Difficulty mismatch",
        "Time slot conflicts with popular sessions"
      ]
    }
  ],

  "contentGaps": [
    "Advanced AI Ethics",
    "Web3 Security",
    "Climate Tech"
  ],

  "qualityMetrics": {
    "avgMatchScore": 75,
    "scoreDistribution": {
      "high": 0.45,
      "medium": 0.40,
      "low": 0.15
    },
    "diversityScore": 0.78
  }
}
```

#### Speaker Analytics

```typescript
GET /events/:eventId/speakers/recommendations/analytics

Response:
{
  "overview": {
    "totalRecommendations": 3000,
    "uniqueUsers": 500,
    "contactRate": 0.22,
    "meetingScheduledRate": 0.15,
    "dismissRate": 0.08
  },

  "topSpeakers": [
    {
      "speakerId": "speaker_abc",
      "name": "Jane Doe",
      "recommendationCount": 280,
      "contactCount": 95,
      "meetingCount": 58,
      "avgMatchScore": 85,
      "rating": 4.9
    }
  ],

  "speakerEngagement": {
    "avgResponseTime": "2.5 hours",
    "responseRate": 0.85,
    "meetingCompletionRate": 0.92
  }
}
```

#### Unified Analytics Dashboard

```typescript
GET /events/:eventId/recommendations/analytics/unified

Response:
{
  "overall": {
    "totalRecommendations": 13000,  // networking + sessions + speakers
    "engagementRate": 0.31,
    "avgMatchScore": 77,
    "costPerRecommendation": 0.02  // USD
  },

  "breakdown": {
    "networking": { ... },
    "sessions": { ... },
    "speakers": { ... }
  },

  "crossFeatureSynergies": {
    "sessionToNetworking": {
      "connectionsFormedInSessions": 234,
      "avgConnectionsPerSession": 2.3
    },
    "speakerToNetworking": {
      "speakerConnectionsMade": 58,
      "speakerMeetingsCompleted": 42
    }
  },

  "performance": {
    "avgLatency": 420,
    "cacheHitRate": 0.96,
    "llmSuccessRate": 0.99,
    "llmCostSavings": 0.67  // Via caching
  }
}
```

### Tracking Implementation

**Event Tracking:**
```typescript
// Track all user interactions for analytics
class RecommendationTracker {
  async trackView(recommendationId: string, type: 'session' | 'speaker') {
    await this.analyticsService.track({
      event: 'recommendation_viewed',
      recommendationId,
      type,
      timestamp: new Date()
    });
  }

  async trackBookmark(recommendationId: string) {
    await this.analyticsService.track({
      event: 'session_bookmarked',
      recommendationId,
      timestamp: new Date()
    });
  }

  async trackDismiss(recommendationId: string, reason?: string) {
    await this.analyticsService.track({
      event: 'recommendation_dismissed',
      recommendationId,
      reason,
      timestamp: new Date()
    });
  }

  async trackAttendance(sessionId: string, userId: string, duration: number) {
    await this.analyticsService.track({
      event: 'session_attended',
      sessionId,
      userId,
      duration,
      timestamp: new Date()
    });
  }
}
```

---

## Competitive Analysis

### Feature Comparison Matrix

| Feature | Your Platform | Swapcard | Brella | Whova | Cvent |
|---------|---------------|----------|--------|-------|-------|
| **AI Session Recommendations** | 🔴 Not Yet | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **AI Speaker Matching** | 🔴 Not Yet | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **AI Networking (Attendees)** | ✅ **Best-in-class** | ✅ Yes | ✅ Yes | ⚠️ Basic | ✅ Yes |
| **LLM-Powered Matching** | ✅ Claude | ✅ GPT-4 | ⚠️ Proprietary | ⚠️ Basic | ⚠️ Basic |
| **Conversation Starters** | ✅ Yes (networking) | ✅ Yes | ✅ Yes | 🔴 No | ⚠️ Basic |
| **Personalized Agenda** | 🔴 Not Yet | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **Real-time Re-ranking** | 🔴 Not Yet | ✅ Yes | ⚠️ Basic | 🔴 No | ⚠️ Basic |
| **Collaborative Filtering** | 🔴 Not Yet | ✅ Yes | ⚠️ Basic | ⚠️ Basic | 🔴 No |
| **Hybrid Event Support** | 🔴 Not Yet | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **Organizer Analytics** | ⚠️ Basic | ✅ Advanced | ✅ Advanced | ✅ Yes | ✅ Advanced |

**Legend:**
- ✅ Fully implemented
- ⚠️ Partially implemented or basic
- 🔴 Not implemented

### Your Competitive Position

#### Current Strengths
1. **Best-in-class networking recommendations**
   - LLM-powered (Claude Sonnet 4.5)
   - Sophisticated fallback algorithms
   - Conversation starters
   - Event-driven architecture

2. **Modern tech stack**
   - Real-time capabilities
   - Scalable caching
   - Kafka event streaming
   - Circuit breaker resilience

3. **Development velocity**
   - Can reuse 80% of networking infrastructure
   - 2-3 week MVP timeline
   - Proven LLM integration patterns

#### Current Gaps (Closed by This Spec)
1. ❌ No session recommendations → ✅ LLM-powered session matching
2. ❌ No speaker recommendations → ✅ Expert matching with icebreakers
3. ❌ No personalized agenda → ✅ Auto-generated schedules
4. ❌ Limited organizer analytics → ✅ Comprehensive dashboards

#### Unique Competitive Advantages (After Implementation)

**1. Integrated Networking + Content Discovery**
- **Unique Feature:** "Attend sessions where compatible people will be"
- **Competitor Gap:** Swapcard/Brella treat these as separate features
- **Value Prop:** Maximize both learning AND networking

**2. Claude-Powered Semantic Understanding**
- **Unique Feature:** State-of-the-art LLM for matching
- **Competitor Gap:** Most use GPT-3.5 or proprietary models
- **Value Prop:** Better match quality, more nuanced reasoning

**3. Unified Recommendation Feed**
- **Unique Feature:** Interleaved networking, sessions, speakers
- **Competitor Gap:** Competitors silo these features
- **Value Prop:** Holistic event experience

**4. Cross-Feature Synergies**
- **Unique Feature:** Session attendance → networking boost
- **Unique Feature:** Speaker recommendations → networking pool
- **Competitor Gap:** No one connects these dots
- **Value Prop:** Smarter, context-aware recommendations

### Competitive Pricing Strategy

**Current Market Pricing (per event):**
- Swapcard: $4,000 - $25,000+ (depending on attendees)
- Brella: $3,500 - $20,000+
- Whova: $2,500 - $15,000+
- Cvent: Enterprise (often $50,000+)

**Your Pricing Opportunity:**
- **MVP Launch:** Include in base tier (competitive parity)
- **Phase 2:** Upsell advanced features to premium tier
- **Phase 3:** Unique features justify 10-20% price premium

---

## Risk Mitigation

### Technical Risks

#### 1. LLM API Costs
**Risk:** Claude API calls expensive at scale

**Mitigation:**
- ✅ Aggressive caching (5min Redis + 24h DB)
- ✅ Batch processing where possible
- ✅ Fallback to algorithmic matching
- ✅ Use cheaper Haiku model for simple tasks
- ✅ Monitor costs with alerts

**Cost Estimates:**
```
Assumptions:
- 500 attendees per event
- 10 recommendations per user
- 50% cache hit rate (conservative)
- $3 per million input tokens (Claude Sonnet)

Cost per event:
- LLM calls needed: 500 users × 10 recs × 0.5 = 2,500 calls
- Avg tokens per call: 2,000 input + 500 output
- Total tokens: 2,500 × 2,500 = 6.25M tokens
- Cost: ~$19 per event

With 95% cache hit rate (realistic after warm-up):
- Cost: ~$4 per event
```

#### 2. Cold Start Problem
**Risk:** No recommendations cached for new events

**Mitigation:**
- ✅ Pre-generate recommendations on event creation
- ✅ Background job for early registrants
- ✅ Optimize for <2s latency on first request
- ✅ Progressive loading (show top 3, lazy-load rest)

#### 3. Data Quality
**Risk:** Poor session/speaker metadata → bad recommendations

**Mitigation:**
- ✅ Require minimum metadata for sessions (tags, description, track)
- ✅ Validate speaker profiles on creation
- ✅ Fallback gracefully when data missing
- ✅ Organizer dashboard shows data quality score

#### 4. Scalability
**Risk:** High load during check-in spikes

**Mitigation:**
- ✅ Async event processing (Kafka)
- ✅ Rate limiting on Oracle AI service
- ✅ Horizontal scaling for real-time service
- ✅ Redis cluster for cache distribution

### Product Risks

#### 1. User Adoption
**Risk:** Users ignore recommendations

**Mitigation:**
- ✅ Prominent UI placement
- ✅ Push notifications for high-match sessions
- ✅ Gamification (badges for attending recommended sessions)
- ✅ Social proof ("3 connections attending")
- ✅ A/B testing different presentations

#### 2. Recommendation Quality
**Risk:** Poor matches frustrate users

**Mitigation:**
- ✅ Dual-strategy (LLM + algorithmic)
- ✅ User feedback loop (dismiss reasons)
- ✅ Continuous A/B testing
- ✅ Manual quality audits
- ✅ Organizer override capability

#### 3. Privacy Concerns
**Risk:** Users uncomfortable with AI profiling

**Mitigation:**
- ✅ Transparent about algorithm ("Based on your interests...")
- ✅ User control (disable recommendations)
- ✅ No sensitive data in matching (only professional info)
- ✅ Privacy policy updates
- ✅ GDPR compliance (right to delete)

### Business Risks

#### 1. Competitive Response
**Risk:** Swapcard/Brella improve their features

**Mitigation:**
- ✅ First-mover advantage on integration (networking + content)
- ✅ Continuous iteration (Phase 3 advanced features)
- ✅ Lock-in via data network effects
- ✅ Patent unique synergy features

#### 2. ROI Justification
**Risk:** Organizers don't see value

**Mitigation:**
- ✅ Comprehensive analytics dashboard
- ✅ Before/after metrics (with/without recommendations)
- ✅ Case studies with early adopters
- ✅ Free pilot program for key accounts

---

## Future Enhancements

### Phase 4+: Advanced Features (12+ weeks out)

#### 1. Predictive Analytics
- **Session capacity forecasting:** Predict which sessions will fill up
- **Optimal session timing:** Suggest best time slots for sessions
- **Track popularity prediction:** Forecast which tracks will be most popular

#### 2. Dynamic Programming
- **Emergent sessions:** Auto-create sessions based on attendee demand
- **Speaker matching for panels:** Suggest optimal panel compositions
- **Topic gap detection:** Identify underserved topics in real-time

#### 3. Post-Event Features
- **On-demand content recommendations:** Continue learning after event
- **Follow-up networking:** Suggest connections based on sessions attended
- **Next event predictions:** Recommend future events to attend

#### 4. Multi-Event Intelligence
- **Cross-event patterns:** Learn from all events on platform
- **Attendee journey mapping:** Track interests across multiple events
- **Global speaker database:** Recommend speakers across events

#### 5. Advanced Personalization
- **Learning path recommendations:** Multi-session learning journeys
- **Career progression paths:** Sessions aligned with career goals
- **Skill gap analysis:** Identify missing skills, recommend sessions

#### 6. Social Features
- **Group recommendations:** "You and 3 friends should attend..."
- **Team agendas:** Coordinate schedules for company teams
- **Networking pods:** Small group networking based on shared interests

#### 7. Accessibility & Inclusion
- **Diverse speaker recommendations:** Ensure diverse representation
- **Accessibility-aware scheduling:** Account for physical needs
- **Language preferences:** Match speakers/sessions to language preferences

---

## References

### Research Sources

1. **Event Technology Trends in 2026**
   https://www.gocadmium.com/resources/event-technology-what-are-the-top-trends-in-2025

2. **Mobile Apps for Conferences: Boost ROI (2026)**
   https://www.engineerica.com/conferences-and-events/post/conference-mobile-apps/

3. **Best Event App Solutions - Brella**
   https://www.brella.io/event-app

4. **Top Event Trends for 2026 - Swapcard**
   https://www.swapcard.com/blog/top-events-trends-2026

5. **Event Industry Trends for 2026**
   https://www.eventplanner.net/news/11089_event-industry-trends-for-2026-a-bold-new-era-of-innovation-and-impact.html

6. **Deep Dive Into Attendee Behavior - PCMA**
   https://www.pcma.org/deep-dive-attendee-behavior-event-experience/

7. **The Most Common Hybrid Event Pain Points**
   https://welcome.bizzabo.com/the-most-common-hybrid-event-pain-points

8. **Boomtown AI Personalization Case Study**
   https://www.monks.com/case-studies/boomtown-amplify-ai-powered-platform

9. **Netflix Hyper-Personalized CX**
   https://www.renascence.io/journal/how-netflix-uses-data-to-drive-hyper-personalized-customer-experience-cx

10. **Top Brella Alternatives and Competitors**
    https://www.eventdex.com/blog/brella-alternatives-and-competitors-2026/

### Key Statistics Summary

- **40%** of event professionals deploying AI-powered agendas (2026)
- **50%** embracing AI throughout meetings journey
- **340%** average ROI for engagement apps
- **80%** content discovery via recommendations (Netflix model)
- **30%** higher engagement for personalized content
- **25%** higher attendance for recommended sessions
- **88%** completion rate for personalized event content
- **40%** share rate for personalized recommendations

---

## Implementation Checklist

### Phase 1: MVP (2-3 weeks)

**Backend - Oracle AI Service:**
- [ ] Create session recommendations module
- [ ] Implement LLM-based session matching
- [ ] Implement algorithmic fallback
- [ ] Add FastAPI endpoints
- [ ] Write unit tests
- [ ] Add circuit breaker

**Backend - Real-Time Service:**
- [ ] Create sessions module
- [ ] Implement three-tier caching
- [ ] Add Prisma schema
- [ ] Create REST endpoints
- [ ] Add event listeners
- [ ] Write integration tests

**Frontend:**
- [ ] Create recommendation hook
- [ ] Build UI components
- [ ] Add to event page
- [ ] Write tests

**Data:**
- [ ] Seed test sessions
- [ ] Add session metadata

### Phase 2: Production (4-6 weeks)

**Session Enhancements:**
- [ ] Real-time re-ranking
- [ ] Personalized agenda builder
- [ ] Session reminders
- [ ] Analytics dashboard
- [ ] Background jobs

**Speaker Recommendations:**
- [ ] Oracle AI speaker matching
- [ ] Conversation starters
- [ ] Real-time service integration
- [ ] Frontend components
- [ ] Meeting request flow

**Database:**
- [ ] Create migrations
- [ ] Run migrations
- [ ] Test data integrity

### Phase 3: Advanced (8-12 weeks)

- [ ] Multi-format recommendations
- [ ] Contextual timing
- [ ] Social proof integration
- [ ] Content similarity engine
- [ ] A/B testing framework
- [ ] Networking-content integration

---

## Conclusion

This specification provides a complete blueprint for implementing production-ready session and speaker recommendations. Key takeaways:

1. **Strong Business Case:** Industry-standard feature with proven ROI (340%)
2. **Low Implementation Cost:** Reuse 80% of existing infrastructure
3. **Fast Time-to-Market:** 2-3 weeks for MVP, 6 weeks for competitive parity
4. **Unique Differentiation:** Integration with networking creates competitive moat
5. **Scalable Architecture:** Built on proven patterns from networking recommendations
6. **Clear Success Metrics:** Measurable impact on discovery, engagement, and revenue

**Next Steps:**
1. Review and approve this specification
2. Deploy agents to implement Phase 1 MVP
3. Iterate based on user feedback
4. Scale to Phase 2 and Phase 3

**Recommended Approach:**
- Start with session recommendations (higher impact)
- Add speaker recommendations in parallel
- Integrate with networking features
- Continuously optimize based on analytics

This feature will bring your platform to competitive parity with Swapcard and Brella, while your unique networking-content integration will create a differentiated position in the market.

---

**Document Status:** ✅ Ready for Implementation
**Approval Required:** Product Team, Engineering Team
**Implementation Start:** Upon Approval
