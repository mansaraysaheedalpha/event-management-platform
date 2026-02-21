# Platform Admin Setup Guide

## Problem
There's currently no way to grant platform admin access because:
1. The `isPlatformAdmin` field doesn't exist in the User database schema
2. The JWT payload doesn't include `isPlatformAdmin`
3. There's no UI or script to grant admin access

## Solution Overview

We need to:
1. ✅ Add `isPlatformAdmin` field to the User model
2. ✅ Create a database migration
3. ✅ Update JWT generation to include the field
4. ✅ Create a script to grant admin access
5. ✅ Deploy and apply changes

---

## Step 1: Add `isPlatformAdmin` to Prisma Schema

**File:** `user-and-org-service/prisma/schema.prisma`

Add this field to the `User` model (around line 64, after `isTwoFactorEnabled`):

```prisma
model User {
  id                        String                 @id @default(cuid())
  email                     String                 @unique
  first_name                String
  last_name                 String
  imageUrl                  String?
  password                  String
  createdAt                 DateTime               @default(now())
  updatedAt                 DateTime               @updatedAt

  // User type: ORGANIZER (needs org) or ATTENDEE (no org needed)
  userType                  UserType               @default(ORGANIZER)

  hashedRefreshToken        String?

  // Fields for 2FA
  twoFactorSecret           String?
  isTwoFactorEnabled        Boolean                @default(false)

  // Platform admin access (for Event Dynamics internal staff)
  isPlatformAdmin           Boolean                @default(false)  // ✨ ADD THIS LINE

  // ... rest of fields
}
```

---

## Step 2: Create and Apply Database Migration

```bash
cd user-and-org-service

# Create the migration
npx prisma migrate dev --name add_platform_admin_field

# For production, use:
npx prisma migrate deploy
```

This will add the `is_platform_admin` column to the `users` table.

---

## Step 3: Update JWT Payload Generation

**File:** `user-and-org-service/src/auth/auth.service.ts`

### 3a. Update `UserForToken` type (around line 32):

```typescript
type UserForToken = Pick<
  User,
  | 'id'
  | 'email'
  | 'first_name'
  | 'last_name'
  | 'imageUrl'
  | 'tier'
  | 'preferredLanguage'
  | 'sponsorId'
  | 'isTwoFactorEnabled'
  | 'userType'
  | 'isPlatformAdmin'  // ✨ ADD THIS LINE
>;
```

### 3b. Update all user queries to select `isPlatformAdmin`:

**In `login()` method** (around line 148):
```typescript
const existingUser = await this.prisma.user.findUnique({
  where: { email: loginDTO.email },
  select: {
    id: true,
    email: true,
    password: true,
    first_name: true,
    last_name: true,
    imageUrl: true,
    isTwoFactorEnabled: true,
    isPlatformAdmin: true,  // ✨ ADD THIS LINE
    preferredLanguage: true,
    tier: true,
    sponsorId: true,
    userType: true,
    failedLoginAttempts: true,
    lockedUntil: true,
    memberships: {
      // ...
    },
  },
});
```

**Repeat for these methods:**
- `login2FA()` (line ~266)
- `generateTokensAfter2FA()` (line ~318)
- `refreshTokenService()` (line ~370)
- `switchOrganization()` (line ~668)
- `registerAttendee()` (line ~732)
- `registerVenueOwner()` (line ~798)

### 3c. Update JWT payload in `getTokensForUser()` (around line 460):

```typescript
const accessTokenPayload: JwtPayload = {
  sub: user.id,
  email: user.email,
  orgId: membership.organizationId,
  role: membership.role.name,
  permissions: [...new Set([...existingPermissions, ...additionalPermissions])],
  tier: (user.tier as 'default' | 'vip') || 'default',
  preferredLanguage: user.preferredLanguage || 'en',
  sponsorId: user.sponsorId || undefined,
  orgRequires2FA: organization.isTwoFactorRequired ?? false,
  is2FAEnabled: user.isTwoFactorEnabled,
  isPlatformAdmin: user.isPlatformAdmin || false,  // ✨ ADD THIS LINE
};
```

### 3d. Update JWT payload in `getTokensForAttendee()` (around line 518):

```typescript
const accessTokenPayload: JwtPayload = {
  sub: user.id,
  email: user.email,
  // No orgId for attendees
  permissions: attendeePermissions,
  tier: (user.tier as 'default' | 'vip') || 'default',
  preferredLanguage: user.preferredLanguage || 'en',
  sponsorId: sponsorStatus?.sponsors?.[0]?.id || user.sponsorId || undefined,
  is2FAEnabled: user.isTwoFactorEnabled,
  isPlatformAdmin: user.isPlatformAdmin || false,  // ✨ ADD THIS LINE
  userType: user.userType,
};
```

---

## Step 4: Update JwtPayload Interface

**File:** `user-and-org-service/src/common/interfaces/auth.interface.ts`

```typescript
export interface JwtPayload {
  sub: string;                    // User ID
  email: string;
  orgId?: string;                 // Optional for attendees
  role?: string;
  permissions?: string[];
  tier?: 'default' | 'vip';
  preferredLanguage?: string;
  sponsorId?: string;
  orgRequires2FA?: boolean;
  is2FAEnabled?: boolean;
  userType?: string;
  isPlatformAdmin?: boolean;      // ✨ ADD THIS LINE
}
```

---

## Step 5: Update GraphQL User Type

**File:** `user-and-org-service/src/users/gql_types/user.types.ts`

```typescript
@ObjectType('User')
@Directive('@key(fields: "id")')
export class GqlUser {
  @Field(() => ID)
  id: string;

  @Field()
  email: string;

  @Field()
  first_name: string;

  @Field()
  last_name: string;

  @Field(() => String, { nullable: true })
  imageUrl: string | null;

  @Field(() => Boolean)
  isTwoFactorEnabled: boolean;

  @Field(() => Boolean)
  isPlatformAdmin: boolean;  // ✨ ADD THIS LINE

  @Field(() => String)
  userType: string;
}
```

---

## Step 6: Create Admin Grant Script

**File:** `user-and-org-service/scripts/grant-admin.ts`

```typescript
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
```

Make it executable:
```bash
chmod +x scripts/grant-admin.ts
```

---

## How to Grant Admin Access

### Method 1: Using the Script (Recommended)

```bash
cd user-and-org-service
npx ts-node scripts/grant-admin.ts
```

It will prompt for the user's email address and grant them admin access.

### Method 2: Direct SQL (Quick Method)

```bash
# Connect to your production database
# Replace with your actual database connection

# For Render PostgreSQL:
psql $DATABASE_URL

# Then run:
UPDATE users
SET is_platform_admin = true
WHERE email = 'your-email@example.com';
```

### Method 3: Prisma Studio (Visual)

```bash
cd user-and-org-service
npx prisma studio
```

1. Open the `User` table
2. Find your user by email
3. Set `isPlatformAdmin` to `true`
4. Save

---

## Deployment Checklist

- [ ] 1. Update Prisma schema with `isPlatformAdmin` field
- [ ] 2. Create and test migration locally
- [ ] 3. Update JWT payload in `getTokensForUser()`
- [ ] 4. Update JWT payload in `getTokensForAttendee()`
- [ ] 5. Update `UserForToken` type
- [ ] 6. Update all user queries to select `isPlatformAdmin`
- [ ] 7. Update `JwtPayload` interface
- [ ] 8. Update `GqlUser` type
- [ ] 9. Create grant-admin script
- [ ] 10. Test locally
- [ ] 11. Deploy to production
- [ ] 12. Run migration on production DB
- [ ] 13. Grant admin access to yourself
- [ ] 14. Test admin panel access

---

## Testing

### 1. Verify Database Migration
```bash
psql $DATABASE_URL -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'is_platform_admin';"
```

### 2. Verify JWT Payload
After logging in, decode your JWT at https://jwt.io and verify it contains:
```json
{
  "isPlatformAdmin": true,
  // ... other fields
}
```

### 3. Verify Admin Access
1. Log in to https://eventdynamics.io
2. You should see "Admin" link in navigation
3. Click "Admin" → "Venues"
4. You should see the venue review queue

---

## Security Notes

⚠️ **Important Security Considerations:**

1. **Limited Access**: Only grant `isPlatformAdmin` to trusted internal team members
2. **Audit Logging**: Platform admin actions should be logged (consider adding audit trails)
3. **No Self-Grant**: Users cannot grant themselves admin access - requires database access
4. **Revocation**: To revoke access, set `isPlatformAdmin` back to `false`
5. **Production Access**: Limit who has database access in production

---

## Troubleshooting

**Q: I granted admin access but still can't access /admin**
A: Log out and log back in. The `isPlatformAdmin` flag is in the JWT, which is generated at login time.

**Q: The migration failed**
A: Check if the column already exists. Run: `\d users` in psql to see the table structure.

**Q: JWT doesn't include isPlatformAdmin**
A: Make sure you updated all the user query selects AND the JWT payload generation in both `getTokensForUser()` and `getTokensForAttendee()`.

**Q: Can I have multiple platform admins?**
A: Yes! Grant access to as many users as needed using the same process.

---

## Real-World Example

```bash
# 1. Apply migration
cd user-and-org-service
npx prisma migrate deploy

# 2. Grant admin access to yourself
npx ts-node scripts/grant-admin.ts
# Enter: your-email@example.com

# 3. Log out and log back in to eventdynamics.io

# 4. Navigate to /admin/venues to review submissions
```

That's it! You now have a complete platform admin system.
