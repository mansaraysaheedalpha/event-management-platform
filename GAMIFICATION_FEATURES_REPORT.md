# Event Dynamics — Gamification Features Report

---

## Executive Summary

Event Dynamics includes a comprehensive gamification system designed to transform passive event attendees into active participants. The system rewards engagement through points, achievements, team competition, live challenges, and trivia games — all happening in real time during event sessions.

The result: higher audience engagement, longer session attendance, and a more memorable event experience.

---

## Table of Contents

1. [Points & Scoring System](#1-points--scoring-system)
2. [Engagement Streaks](#2-engagement-streaks)
3. [Achievements & Badges](#3-achievements--badges)
4. [Individual Leaderboard](#4-individual-leaderboard)
5. [Teams](#5-teams)
6. [Team Synergy Bonus](#6-team-synergy-bonus)
7. [Team Leaderboard](#7-team-leaderboard)
8. [Team Challenges](#8-team-challenges)
9. [Team Trivia](#9-team-trivia)
10. [Team Chat](#10-team-chat)
11. [Real-Time Notifications](#11-real-time-notifications)
12. [Attendee Dashboard](#12-attendee-dashboard)

---

## 1. Points & Scoring System

Every meaningful action an attendee takes during an event session earns them points. Points accumulate in real time and are visible to the attendee immediately.

### Actions & Point Values

| Action | Points | Description |
|--------|--------|-------------|
| Join a session | 2 | Awarded once per session when an attendee enters |
| Send a chat message | 1 | Encourages conversation and engagement |
| React to a message | 2 | Rewards social interaction |
| Ask a question (Q&A) | 5 | Higher reward for meaningful participation |
| Upvote a question | 2 | Encourages peer validation of good questions |
| Create a poll | 10 | Organizer/speaker action, high reward |
| Vote in a poll | 1 | Easy action to encourage broad participation |
| Join a waitlist | 3 | Shows interest in capacity-limited sessions |
| Create a team | 5 | Leadership action |
| Join a team | 3 | Team participation |
| Complete a challenge | 10 | Awarded to all participants who finish |
| Win a challenge (1st place) | 50 | Top reward for competitive excellence |
| Win a challenge (2nd place) | 30 | Strong performance recognition |
| Win a challenge (3rd place) | 15 | Podium finish recognition |
| Answer trivia correctly | 10 | Knowledge reward |
| Trivia speed bonus | 5 | Extra reward for fast correct answers |

### How Points Work

- Points are awarded instantly when an action is performed
- Each attendee's total score is the sum of all points earned in a session
- Certain actions (like joining a session) can only earn points once — repeated joins don't stack
- Points can be amplified through **streak multipliers** and **team synergy bonuses** (explained below)

---

## 2. Engagement Streaks

The streak system rewards sustained, continuous engagement. When an attendee keeps participating over time, their point earnings increase.

### How Streaks Work

- Every qualifying action increments the attendee's streak counter
- The streak counter resets after **5 minutes of inactivity**
- To prevent spam, the streak only increments once per minute regardless of how many actions are performed
- As the streak grows, a **multiplier** is applied to all points earned:

| Streak Level | Actions in a Row | Point Multiplier |
|-------------|-----------------|-----------------|
| No streak | 0-2 actions | 1.0x (normal) |
| Hot streak | 3-5 actions | 1.5x |
| On fire | 6+ actions | 2.0x (double points) |

### Example

An attendee who has been actively chatting and voting for several minutes reaches a 6-action streak. Their next question (normally 5 points) earns them **10 points** thanks to the 2.0x multiplier.

Attendees receive a notification when their streak level changes, encouraging them to keep engaging.

---

## 3. Achievements & Badges

The platform features **18 unlockable achievements** organized into 7 categories. Achievements are visual badges that attendees collect as recognition of their participation milestones.

### Social Butterfly (Chat Engagement)

| Badge | Requirement | Icon |
|-------|------------|------|
| First Words | Send your first chat message | 💬 |
| Conversation Starter | Send 10 messages in a session | 🗣️ |
| Social Butterfly | Send 25 messages in a session | 🦋 |

### Curious Mind (Q&A Engagement)

| Badge | Requirement | Icon |
|-------|------------|------|
| Question Asker | Ask your first question | ❓ |
| Thought Leader | Ask 5 questions in a session | 🧠 |
| Helpful Hand | Upvote 10 questions | 🤝 |

### Voice of the People (Poll Engagement)

| Badge | Requirement | Icon |
|-------|------------|------|
| Poll Pioneer | Vote in your first poll | 🗳️ |
| Super Voter | Vote in 5 polls | 🏆 |
| Opinion Leader | Vote in 10 polls | 📊 |

### Team Player

| Badge | Requirement | Icon |
|-------|------------|------|
| Team Founder | Create a team | 🚀 |
| Team Player | Join a team | 🤜 |
| Team Spirit | Earn a synergy bonus 10 times (across all sessions) | 🤝 |

### Event Explorer

| Badge | Requirement | Icon |
|-------|------------|------|
| Explorer | Join 3 different sessions (across the event) | 🧭 |

### Competitor (Challenges & Trivia)

| Badge | Requirement | Icon |
|-------|------------|------|
| Challenge Champion | Win first place in a team challenge | 🏅 |
| Challenge Veteran | Complete 5 team challenges (across all sessions) | ⚔️ |
| Trivia Master | Answer 10 trivia questions correctly (across all sessions) | 🧩 |

### Milestones (Point Thresholds)

| Badge | Requirement | Icon |
|-------|------------|------|
| Engaged Attendee | Earn 50 points | ⭐ |
| Rising Star | Earn 100 points | 🌟 |
| Superstar | Earn 200 points | 💫 |

### Achievement Behavior

- Achievements unlock automatically when conditions are met — no manual claiming needed
- Once unlocked, the attendee receives an instant notification with the badge name, icon, and description
- Some achievements are **session-scoped** (must be completed within one session), while others are **cross-session** (progress carries across the entire event)
- Every attendee can view their progress toward all 18 achievements, including a percentage completion bar for each

---

## 4. Individual Leaderboard

Each session has a live individual leaderboard that ranks attendees by their total points.

### Features

- **Top 10 display**: Shows the highest-scoring attendees with their name, rank, and score
- **Personal rank**: Every attendee can see their own rank and score, even if they're not in the top 10
- **Real-time updates**: The leaderboard refreshes automatically as points are earned
- **Rank icons**: The top 3 positions are visually distinguished

---

## 5. Teams

Attendees can form and join teams within a session to compete together. Teams add a collaborative dimension to the gamification experience.

### Team Features

- **Create a team**: Any attendee can create a team with a custom name. The creator becomes the first member.
- **Join a team**: Attendees can browse existing teams and join one. If they're already on a team in the same session, they're automatically switched to the new team.
- **Leave a team**: Members can leave at any time.
- **One team per session**: An attendee can only be on one team per session at a time.
- **Unique names**: Team names must be unique within a session.
- **Automatic room assignment**: When a team member joins a session, they're automatically connected to their team's communication channel.

### Team Roster

All team members are visible to everyone in the session, along with the team creator and the number of members.

---

## 6. Team Synergy Bonus

The synergy system rewards teams whose members are actively participating at the same time. When multiple teammates are engaged simultaneously, everyone on the team earns bonus points.

### How Synergy Works

- The system tracks which team members are currently active (within a 5-minute window)
- The more teammates active at the same time, the higher the synergy multiplier applied to everyone's points:

| Active Teammates | Synergy Multiplier |
|-----------------|-------------------|
| Just you | 1.0x (no bonus) |
| 1 teammate also active | 1.1x |
| 2 teammates also active | 1.2x |
| 3+ teammates also active | 1.3x (maximum) |

### Combined Multipliers

Streak and synergy multipliers **stack multiplicatively**. An attendee with a hot streak (1.5x) and 3 active teammates (1.3x) earns:

> 1.5 x 1.3 = **1.95x points** on every action

The theoretical maximum is **2.6x** (2.0x streak x 1.3x synergy).

### Synergy Notifications

When synergy is active, the points notification shows the attendee:
- The base points earned
- The streak multiplier applied
- The synergy multiplier applied
- How many teammates are currently active

This encourages teams to coordinate and participate together.

---

## 7. Team Leaderboard

Alongside the individual leaderboard, each session has a **team leaderboard** that ranks teams by the combined scores of all their members.

### Features

- **Team ranking**: Teams are ranked by the sum of all members' individual points
- **Member count**: Shows how many members each team has
- **Real-time updates**: Updates automatically as team members earn points
- **Rank change notifications**: When a team moves up or down in rank, all team members receive a notification (e.g., "Your team moved from #3 to #2!")

---

## 8. Team Challenges

Organizers can launch **timed competitive challenges** during a session where teams race to complete specific actions. Challenges create intense, focused bursts of engagement.

### Available Challenge Types

| Challenge | Duration | Goal | Rewards (1st/2nd/3rd) |
|-----------|----------|------|----------------------|
| Chat Blitz | 5 minutes | Send the most chat messages | 50 / 30 / 15 points |
| Poll Rush | 10 minutes | Vote in the most polls | 50 / 30 / 15 points |
| Q&A Sprint | 10 minutes | Ask the most questions | 60 / 35 / 20 points |
| Points Race | 15 minutes | Earn the most total points (any action) | 75 / 50 / 25 points |

Organizers can also create **custom challenges** with their own names, descriptions, durations, tracked actions, and reward amounts.

### Challenge Lifecycle

1. **Created**: The organizer selects a challenge type (or creates a custom one)
2. **Started**: The organizer launches the challenge. All attendees in the session are notified
3. **In Progress**: Teams compete in real time. A live progress board shows each team's current score and ranking
4. **Completed**: When the timer expires, final results are calculated automatically:
   - Teams are ranked by their score
   - Points are awarded to the top 3 teams
   - Every member of the winning teams receives the reward points
   - All attendees see the final standings
5. **Cancelled** (optional): The organizer can cancel an active challenge at any time

### Progress Tracking

During an active challenge:
- Each team's score updates in real time
- All session attendees can see the live standings
- Team members receive progress notifications

### Who Can Manage Challenges

Only users with organizer-level permissions (event managers, content managers, or gamification managers) can create, start, or cancel challenges. Regular attendees participate but cannot manage challenges.

---

## 9. Team Trivia

Organizers can run **live trivia games** where teams compete to answer questions correctly and quickly. Trivia adds a knowledge-based competitive element beyond engagement metrics.

### How Trivia Works

1. **Game Creation**: The organizer creates a trivia game with:
   - A game name
   - Multiple-choice questions (2-10 answer options each)
   - Time per question (default: 30 seconds)
   - Points for correct answers (default: 10)
   - Speed bonus points (default: 5)

2. **Game Start**: The organizer starts the game. All teams in the session are enrolled automatically. The first question is displayed.

3. **Answering**:
   - The team captain (team creator) submits the team's answer
   - Only one answer per team per question is allowed
   - Answers must be submitted within the time limit

4. **Speed Bonus**: Teams that answer correctly in less than **half the allowed time** earn extra speed bonus points. For a 30-second question, answering correctly within 15 seconds earns the bonus.

5. **Question Progression**: The organizer advances through questions one at a time:
   - The correct answer is revealed
   - All teams' answers are shown
   - Updated scores are displayed
   - The next question is presented

6. **Game End**: After the last question, final scores are displayed with team rankings.

### Trivia Scoring

| Action | Points |
|--------|--------|
| Correct answer | 10 (configurable) |
| Speed bonus (correct + fast) | +5 (configurable) |
| Wrong answer | 0 |

### Trivia Features

- Questions are revealed one at a time, controlled by the organizer
- Teams see their own answers and scores in real time
- After each question is revealed, all teams can see everyone's answers
- The game tracks: total score, correct answer count, and speed bonuses per team
- Attendees who join mid-game can see the current game state and catch up

---

## 10. Team Chat

Teams have their own **private chat channel** separate from the session-wide chat. This lets team members strategize, coordinate, and communicate during challenges and trivia.

### Features

- **Private to team members**: Only members of a team can see and send messages in the team chat
- **Real-time messaging**: Messages appear instantly for all team members
- **Emoji reactions**: Team members can react to messages with emojis. Reactions toggle on/off (tap once to add, tap again to remove)
- **Chat history**: Messages are persisted and can be scrolled back through. Supports pagination for loading older messages.
- **Points for participation**: Sending team chat messages earns MESSAGE_SENT points (1 point each), subject to streak and synergy multipliers
- **Message length limit**: Messages can be up to 2,000 characters

---

## 11. Real-Time Notifications

The gamification system sends instant notifications to keep attendees informed and motivated.

### Individual Notifications (sent to the specific attendee)

| Notification | When It Fires |
|-------------|---------------|
| Points awarded | Every time the attendee earns points. Shows: base points, multipliers applied, new total score |
| Streak update | When the attendee's streak level changes (e.g., reaching 1.5x or 2.0x) |
| Achievement unlocked | When a new badge is earned. Shows: badge name, icon, description |

### Team Notifications (sent to all members of a team)

| Notification | When It Fires |
|-------------|---------------|
| Member joined | A new member joins the team |
| Member left | A member leaves the team |
| Rank changed | The team moves up or down on the leaderboard. Shows: old rank, new rank, direction |
| Challenge event | A challenge starts, progress updates, or a challenge completes |
| Trivia starting | A trivia game is about to begin |
| Synergy active | Multiple teammates are participating simultaneously |

### Session-Wide Broadcasts (sent to everyone in the session)

| Broadcast | When It Fires |
|-----------|---------------|
| Leaderboard updated | When individual rankings change |
| Team leaderboard updated | When team rankings change |
| Challenge started | When an organizer launches a new challenge |
| Challenge progress | Live score updates during an active challenge |
| Challenge completed | Final results and rankings when a challenge ends |
| Trivia question active | When a new trivia question is displayed |
| Trivia question revealed | When the correct answer is shown |
| Trivia scores updated | After each question is answered |
| Trivia game completed | Final trivia results |

---

## 12. Attendee Dashboard

Attendees have access to a gamification dashboard that provides a complete view of their participation and progress.

### Dashboard Views

**Full Dashboard** (default view):
- Personal score card showing current score, rank, and connection status
- Individual leaderboard (top 10)
- Team leaderboard (if teams are active)
- Animated points overlay when points are earned

**Compact View**:
- Minimal score and rank display
- Recent points indicator

### Gamification Hub (detailed panel)

Attendees can open a detailed panel with four tabs:

**1. Progress Tab**
- Current score and rank
- Streak status with explanation of how streaks work
- Achievement overview (X of 18 unlocked)
- Next 3 closest achievements to unlock (with progress bars)
- Recent activity feed (last 5 point events)
- "How to Earn Points" guide showing all actions and their values

**2. Challenges Tab**
- Active challenges (with live pulse indicator)
- Upcoming (pending) challenges
- Completed challenges with results
- Each challenge card shows: name, type, status, description

**3. Badges Tab**
- All 18 achievements organized by category:
  - Social Butterfly, Curious Mind, Voice of the People, Team Player, Event Explorer, Competitor, Milestones
- Grid view showing locked and unlocked badges
- Progress bars for partially completed achievements
- Unlock dates for earned badges

**4. Leaderboard Tab**
- Full individual rankings with rank icons for top positions
- Team rankings (when teams are active)
- Live updates as scores change

---

## Feature Summary

| Feature | Purpose | Key Benefit |
|---------|---------|-------------|
| Points System | Reward every meaningful action | Encourages broad participation |
| Streaks | Reward sustained engagement | Keeps attendees engaged longer |
| Achievements | Milestone recognition | Gives attendees goals to work toward |
| Individual Leaderboard | Personal competition | Motivates high performers |
| Teams | Group collaboration | Social bonding and team spirit |
| Synergy Bonus | Reward coordinated team activity | Teams participate together |
| Team Leaderboard | Group competition | Drives team coordination |
| Challenges | Timed competitive bursts | Creates exciting, focused moments |
| Trivia | Knowledge-based competition | Adds educational and fun dimension |
| Team Chat | Private team communication | Enables strategy and coordination |
| Notifications | Real-time feedback | Keeps attendees informed and motivated |
| Dashboard | Progress visibility | Attendees always know where they stand |

---

## How It All Works Together

A typical attendee experience during a gamified session:

1. **Arrival**: The attendee joins the session and earns their first 2 points. They see the leaderboard and other attendees' scores.

2. **Engagement**: They start chatting, asking questions, and voting in polls. Points accumulate. After a few actions, their streak kicks in and points start multiplying.

3. **Team Formation**: They join a team with friends or other attendees. As teammates participate alongside them, the synergy bonus activates, further boosting everyone's points.

4. **Challenge Time**: The organizer launches a "Chat Blitz" challenge. For 5 minutes, all teams race to send the most messages. The live progress board shows teams neck-and-neck. When time's up, the winning team earns 50 bonus points per member.

5. **Trivia Round**: The organizer starts a trivia game. Teams huddle in their team chat to discuss answers. The team captain submits answers quickly to earn speed bonuses. After 10 questions, final scores are revealed.

6. **Achievement Unlocks**: Throughout the session, badges pop up as milestones are reached — "Social Butterfly" for 25 messages, "Rising Star" for 100 points, "Challenge Champion" for winning first place.

7. **Final Standings**: By the end of the session, attendees have a rich record of their participation: points earned, badges collected, team ranking, and challenge results.

---

*This report covers all gamification features currently built into the Event Dynamics platform.*