//src/seed.ts
import { PrismaClient } from '@prisma/client';
import * as dotenv from 'dotenv';

dotenv.config();

const prisma = new PrismaClient();

const allPermissions = [
  // Polls
  { name: 'poll:create', description: 'Can create new polls' },
  { name: 'poll:manage', description: 'Can close/delete polls' },
  { name: 'poll:vote', description: 'Can vote in polls' },
  // Q&A
  { name: 'qna:ask', description: 'Can ask new questions' },
  { name: 'qna:upvote', description: 'Can upvote questions' },
  { name: 'qna:moderate', description: 'Can approve/dismiss questions' },
  // Chat
  { name: 'chat:send', description: 'Can send messages in session chat' },
  { name: 'chat:edit:own', description: 'Can edit their own messages' },
  { name: 'chat:delete:own', description: 'Can delete their own messages' },
  {
    name: 'chat:delete:any',
    description: 'Can delete any message (moderator)',
  },
  // DMs
  { name: 'dm:send', description: 'Can send direct messages' },
  {
    name: 'dashboard:read:live',
    description: 'Can view the live event dashboard',
  },
  // Incident Management
  { name: 'ops:incident:read', description: 'Can view reported incidents' },
  { name: 'ops:incident:manage', description: 'Can update incident status and resolution' },
  // Staff Backchannel
  { name: 'backchannel:join', description: 'Can join the staff backchannel' },
  { name: 'backchannel:send', description: 'Can send messages in the staff backchannel' },
  // Presentation Control
  { name: 'presentation:control', description: 'Can control live presentations (start/stop, navigate slides)' },
  // Breakout Rooms
  { name: 'breakout:manage', description: 'Can create, start, and close breakout rooms' },
];

/**
 * Role Definitions:
 *
 * OWNER - Organization owner with full access to everything
 * ADMIN - Full administrative access, can manage events, team, and settings
 * MODERATOR - Live event moderator, can moderate Q&A/chat, view dashboard, join backchannel
 *             but cannot manage organization settings or team members
 * SPEAKER - Event speaker, can control their presentations, receive speaker-targeted
 *           backchannel messages, but cannot moderate Q&A/chat
 * MEMBER - Basic team member, can participate in events but cannot moderate
 *          Useful for volunteers or helpers who need internal access
 */
const roles: Record<string, string[]> = {
  OWNER: [
    'poll:create',
    'poll:manage',
    'poll:vote',
    'qna:ask',
    'qna:upvote',
    'qna:moderate',
    'chat:send',
    'chat:edit:own',
    'chat:delete:own',
    'chat:delete:any',
    'dm:send',
    'dashboard:read:live',
    'ops:incident:read',
    'ops:incident:manage',
    'backchannel:join',
    'backchannel:send',
    'breakout:manage',
  ],
  ADMIN: [
    'poll:create',
    'poll:manage',
    'poll:vote',
    'qna:ask',
    'qna:upvote',
    'qna:moderate',
    'chat:send',
    'chat:edit:own',
    'chat:delete:own',
    'chat:delete:any',
    'dm:send',
    'dashboard:read:live',
    'ops:incident:read',
    'ops:incident:manage',
    'backchannel:join',
    'backchannel:send',
    'breakout:manage',
  ],
  MODERATOR: [
    'poll:create',
    'poll:manage',
    'poll:vote',
    'qna:ask',
    'qna:upvote',
    'qna:moderate',
    'chat:send',
    'chat:edit:own',
    'chat:delete:own',
    'chat:delete:any',
    'dm:send',
    'dashboard:read:live',
    'ops:incident:read',
    'backchannel:join',
    'backchannel:send',
    'breakout:manage',
  ],
  SPEAKER: [
    'poll:vote',
    'qna:ask',
    'qna:upvote',
    'chat:send',
    'chat:edit:own',
    'chat:delete:own',
    'dm:send',
    'presentation:control',
    'backchannel:join',
    'backchannel:send',
  ],
  MEMBER: [
    'poll:vote',
    'qna:ask',
    'qna:upvote',
    'chat:send',
    'chat:edit:own',
    'chat:delete:own',
    'dm:send',
  ],
};

async function main() {
  console.log('Seeding permissions...');
  await prisma.permission.createMany({
    data: allPermissions,
    skipDuplicates: true,
  });
  console.log('Permissions seeded.');

  console.log('Seeding system roles...');
  for (const roleName in roles) {
    const permissionsForRole = roles[roleName];

    // Find the permission records that match the names
    const permissionsToConnect = await prisma.permission.findMany({
      where: { name: { in: permissionsForRole } },
      select: { id: true },
    });

    // Create or update the system role
    const existingRole = await prisma.role.findFirst({
      where: {
        name: roleName,
        isSystemRole: true,
      },
    });

    if (existingRole) {
      // 2. If it exists, update it
      await prisma.role.update({
        where: { id: existingRole.id },
        data: {
          permissions: {
            set: permissionsToConnect, // Overwrite existing permissions
          },
        },
      });
    } else {
      // 3. If it doesn't exist, create it
      await prisma.role.create({
        data: {
          name: roleName,
          isSystemRole: true,
          // organizationId is omitted, so it defaults to null
          permissions: {
            connect: permissionsToConnect,
          },
        },
      });
    }
  }
  console.log('System roles seeded.');
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
