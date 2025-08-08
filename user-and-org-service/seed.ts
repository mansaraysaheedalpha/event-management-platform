import { PrismaClient } from '@prisma/client';

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
];

const roles = {
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
