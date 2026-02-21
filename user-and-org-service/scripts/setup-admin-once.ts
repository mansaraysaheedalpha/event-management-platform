// scripts/setup-admin-once.ts
// Run this ONCE to set up platform admin access
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();
const ADMIN_EMAIL = 'saheedalphamansaray@gmail.com';

async function main() {
  console.log('🔧 Setting up platform admin access...\n');

  // Find the user
  const user = await prisma.user.findUnique({
    where: { email: ADMIN_EMAIL },
    select: {
      id: true,
      email: true,
      first_name: true,
      last_name: true,
      isPlatformAdmin: true,
    },
  });

  if (!user) {
    console.error(`❌ User with email "${ADMIN_EMAIL}" not found`);
    console.log('\nMake sure you have an account at eventdynamics.io first!');
    process.exit(1);
  }

  if (user.isPlatformAdmin) {
    console.log(`✅ User "${user.first_name} ${user.last_name}" is already a platform admin!`);
    console.log(`   Email: ${user.email}`);
    console.log('\n🔄 Log out and log back in to access /admin');
    process.exit(0);
  }

  // Grant admin access
  await prisma.user.update({
    where: { id: user.id },
    data: { isPlatformAdmin: true },
  });

  console.log(`✅ Successfully granted platform admin access!`);
  console.log(`   Name: ${user.first_name} ${user.last_name}`);
  console.log(`   Email: ${user.email}`);
  console.log(`   User ID: ${user.id}`);
  console.log('\n🔄 Next steps:');
  console.log('   1. Log out of eventdynamics.io');
  console.log('   2. Log back in (generates new JWT with admin flag)');
  console.log('   3. Navigate to /admin');
  console.log('   4. Click "Venues" to review submissions');
  console.log('\n🎉 You now have platform admin access!');
}

main()
  .catch((e) => {
    console.error('❌ Error:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
