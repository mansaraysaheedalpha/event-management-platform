// src/gamification/teams/challenges/challenge-templates.ts
import { ChallengeType, PointReason } from '@prisma/client';

export interface ChallengeTemplate {
  name: string;
  description: string;
  type: ChallengeType;
  durationMinutes: number;
  trackedReason: PointReason;
  rewardFirst: number;
  rewardSecond: number;
  rewardThird: number;
}

export const CHALLENGE_TEMPLATES: Record<string, ChallengeTemplate> = {
  CHAT_BLITZ: {
    name: 'Chat Blitz',
    description:
      'The team with the most chat messages wins! Get your team talking and earn the top spot.',
    type: 'CHAT_BLITZ',
    durationMinutes: 5,
    trackedReason: 'MESSAGE_SENT',
    rewardFirst: 50,
    rewardSecond: 30,
    rewardThird: 15,
  },
  POLL_RUSH: {
    name: 'Poll Rush',
    description:
      'Vote in as many polls as possible! The team with the most poll votes takes the crown.',
    type: 'POLL_RUSH',
    durationMinutes: 10,
    trackedReason: 'POLL_VOTED',
    rewardFirst: 50,
    rewardSecond: 30,
    rewardThird: 15,
  },
  QA_SPRINT: {
    name: 'Q&A Sprint',
    description:
      'Ask the most questions! The most curious team earns bragging rights and bonus points.',
    type: 'QA_SPRINT',
    durationMinutes: 10,
    trackedReason: 'QUESTION_ASKED',
    rewardFirst: 60,
    rewardSecond: 35,
    rewardThird: 20,
  },
  POINTS_RACE: {
    name: 'Points Race',
    description:
      'Earn the most total points by any means necessary. Chat, vote, ask questions — everything counts!',
    type: 'POINTS_RACE',
    durationMinutes: 15,
    trackedReason: 'MESSAGE_SENT', // Will be overridden by MULTI_ACTION logic
    rewardFirst: 75,
    rewardSecond: 50,
    rewardThird: 25,
  },
};
