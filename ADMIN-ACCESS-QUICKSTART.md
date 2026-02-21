# Platform Admin Access - Quick Start Guide

## TL;DR - Fastest Path to Admin Access

You submitted a venue for review but there's no one to review it because platform admin access isn't set up yet. Here's the fastest way to fix that:

## Quick Setup (Production - 5 minutes)

### Step 1: Add the Database Column

Connect to your **user-and-org-service** database on Render/Neon:

```bash
# Get your database URL from Render dashboard for user-and-org-service
psql YOUR_USER_SERVICE_DATABASE_URL

# Run this command:
ALTER TABLE users ADD COLUMN is_platform_admin BOOLEAN NOT NULL DEFAULT false;
```

### Step 2: Grant Yourself Admin Access

Still in the same psql session:

```sql
-- Replace with YOUR actual email address
UPDATE users SET is_platform_admin = true WHERE email = 'your-email@example.com';

-- Verify it worked:
SELECT email, first_name, last_name, is_platform_admin FROM users WHERE email = 'your-email@example.com';
```

### Step 3: Update the Code

You need to make the JWT include the `isPlatformAdmin` field. The comprehensive guide is at [user-and-org-service/docs/PLATFORM-ADMIN-SETUP.md](user-and-org-service/docs/PLATFORM-ADMIN-SETUP.md), but here are the KEY changes:

**File: `user-and-org-service/src/auth/auth.service.ts`**

1. Add `isPlatformAdmin` to the JWT payload in `getTokensForUser()` method (~line 460):
   ```typescript
   const accessTokenPayload: JwtPayload = {
     // ... existing fields ...
     isPlatformAdmin: user.isPlatformAdmin || false,  // ADD THIS LINE
   };
   ```

2. Add `isPlatformAdmin` to the JWT payload in `getTokensForAttendee()` method (~line 518):
   ```typescript
   const accessTokenPayload: JwtPayload = {
     // ... existing fields ...
     isPlatformAdmin: user.isPlatformAdmin || false,  // ADD THIS LINE
   };
   ```

3. Add `isPlatformAdmin: true,` to ALL the user queries (search for `.findUnique` and `.findFirst` in auth.service.ts and add it to the `select` object)

**File: `user-and-org-service/src/common/interfaces/auth.interface.ts`**

Add to JwtPayload interface:
```typescript
export interface JwtPayload {
  // ... existing fields ...
  isPlatformAdmin?: boolean;  // ADD THIS LINE
}
```

### Step 4: Deploy & Test

```bash
cd user-and-org-service
git add .
git commit -m "feat: add platform admin support"
git push origin main
```

Wait for Render to deploy, then:

1. **Log out** of eventdynamics.io
2. **Log back in** (this generates a new JWT with `isPlatformAdmin: true`)
3. Navigate to `/admin` - you should see the admin panel
4. Click "Venues" to see the review queue
5. Your submitted venue should be there!

---

## What This Does

**Before:**
- User submits venue → Status: "pending_review"
- No admin panel exists → Can't review it
- Venue never gets approved

**After:**
- You have `isPlatformAdmin: true` in your JWT
- Middleware allows access to `/admin` routes
- You can review and approve your own venue (and others)

---

## Real-World Usage

In production SaaS applications, platform admin access is **always** controlled at the database level, never through a UI. This is because:

1. **Security**: Admins need database access anyway - combines privileges
2. **Audit Trail**: Database changes are logged automatically
3. **Simplicity**: No extra code to maintain for admin management
4. **Separation**: UI is for customers, database is for internal staff

Examples:
- **Stripe**: Platform admins set via internal tools with DB access
- **GitHub**: Staff access granted through internal admin systems
- **AWS**: Root account created during setup, others via IAM (but IAM itself requires admin access)

You could build a UI for this later, but it requires:
- Super-admin account creation system
- Audit logging
- 2FA requirement
- IP whitelist...
- ...which is overkill when you have 1-5 admins

---

## Files Created for You

✅ [user-and-org-service/docs/PLATFORM-ADMIN-SETUP.md](user-and-org-service/docs/PLATFORM-ADMIN-SETUP.md) - Complete setup guide
✅ [user-and-org-service/scripts/grant-admin.ts](user-and-org-service/scripts/grant-admin.ts) - TypeScript script to grant access
✅ [user-and-org-service/scripts/add-platform-admin-field.sql](user-and-org-service/scripts/add-platform-admin-field.sql) - SQL to add the column
✅ [user-and-org-service/scripts/grant-admin-direct.sql](user-and-org-service/scripts/grant-admin-direct.sql) - SQL to grant access
✅ [user-and-org-service/prisma/schema.prisma](user-and-org-service/prisma/schema.prisma) - Updated with `isPlatformAdmin` field
✅ [event-lifecycle-service/docs/VENUE-REVIEW-PROCESS.md](event-lifecycle-service/docs/VENUE-REVIEW-PROCESS.md) - Review workflow docs
✅ [globalconnect/src/app/(admin)/layout.tsx](globalconnect/src/app/(admin)/layout.tsx) - Added "Venues" to admin nav

---

## Testing Checklist

After deployment:

- [ ] Log out and log back in
- [ ] Check JWT at https://jwt.io - should contain `"isPlatformAdmin": true`
- [ ] Visit `/admin` - should NOT redirect to `/auth/login`
- [ ] See "Venues" in admin sidebar
- [ ] Click "Venues" → see review queue
- [ ] See your submitted venue with status "Pending Review"
- [ ] Click "Approve" → venue goes live
- [ ] Visit `/venues` → see your venue in the public directory

---

## Need Help?

If something doesn't work:

1. **Check the JWT**: Decode it at jwt.io - does it have `isPlatformAdmin: true`?
2. **Check the database**: Run `SELECT is_platform_admin FROM users WHERE email = 'your-email@example.com';`
3. **Check the logs**: Look at Render logs for user-and-org-service
4. **Verify deployment**: Make sure the code changes were deployed

---

## Next Steps

Once you have admin access working, you can:

1. Review and approve venue submissions
2. Reject venues with feedback
3. Request additional documents from venue owners
4. Suspend venues for policy violations
5. View platform-wide metrics in the admin dashboard

---

## Future Enhancement

If you want to build a UI for admin management later (when you have 10+ admins):

- Create a "Platform Settings" admin page
- List all users with a toggle for `isPlatformAdmin`
- Require your own 2FA to grant access
- Log all admin grants in an audit table
- Notify users via email when granted/revoked

But for now (1-5 admins), database-level management is the industry standard approach!
