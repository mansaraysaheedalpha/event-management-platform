// scripts/grant-admin.ts
import { PrismaClient } from '@prisma/client';
import * as readline from 'readline';

const prisma = new PrismaClient();

async function main() {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  const email = await new Promise<string>((resolve) => {
    rl.question('Enter the email address of the user to grant admin access: ', (answer) => {
      resolve(answer.trim());
    });
  });

  rl.close();

  if (!email) {
    console.error('❌ Email address is required');
    process.exit(1);
  }

  // Find the user
  const user = await prisma.user.findUnique({
    where: { email },
    select: {
      id: true,
      email: true,
      first_name: true,
      last_name: true,
      isPlatformAdmin: true,
    },
  });

  if (!user) {
    console.error(`❌ User with email "${email}" not found`);
    process.exit(1);
  }

  if (user.isPlatformAdmin) {
    console.log(`⚠️  User "${user.first_name} ${user.last_name}" (${user.email}) is already a platform admin`);
    process.exit(0);
  }

  // Grant admin access
  await prisma.user.update({
    where: { id: user.id },
    data: { isPlatformAdmin: true },
  });

  console.log(`✅ Successfully granted platform admin access to:`);
  console.log(`   Name: ${user.first_name} ${user.last_name}`);
  console.log(`   Email: ${user.email}`);
  console.log(`   User ID: ${user.id}`);
  console.log('\n🔄 The user will need to log out and log back in for changes to take effect.');
}

main()
  .catch((e) => {
    console.error('❌ Error:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
