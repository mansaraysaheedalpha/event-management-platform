# Venue Review Process

## Overview
When venue owners submit their venues for listing in the public directory, they go through a review and approval process managed by Platform Administrators.

## How It Works

### 1. Venue Owner Submits for Review
- Venue owners create and edit their venue in **"My Venues"** section
- Once they've added all required information (name, description, location, photos, spaces, amenities, etc.), they click **"Submit for Review"**
- The venue status changes from `draft` to `pending_review`
- A timestamp is recorded in `submitted_at`

### 2. Where Submissions Go
All submitted venues go into the **Platform Admin Review Queue**, which can be accessed at:

```
https://eventdynamics.io/admin/venues
```

### 3. Who Reviews Submissions

**Platform Administrators** review submissions. These are internal Event Dynamics team members with the `isPlatformAdmin` flag in their JWT token.

Platform admin access is controlled at the backend level and cannot be self-assigned. It must be set in the database or through user management APIs.

### 4. Review Queue Features

The admin review queue provides:

- **Status Filtering**: Filter by `pending_review`, `approved`, `rejected`, `suspended`, or all statuses
- **Domain Match Filter**: Show only venues where the email domain matches the organization domain (higher trust)
- **Pagination**: Browse through all submissions
- **Quick Actions**: Approve, reject, suspend, or request documents

### 5. Admin Actions

Platform admins can take the following actions on submitted venues:

#### ✅ Approve
- Changes status to `approved`
- Sets `approved_at` timestamp
- Makes the venue visible in the public directory (`/venues`)
- Notifies the venue owner (if email notifications are configured)

#### ❌ Reject
- Changes status to `rejected`
- Admin provides a rejection reason
- Venue owner can see the reason and resubmit after addressing issues
- Venue is NOT visible in public directory

#### 🛑 Suspend
- Changes status to `suspended` (for previously approved venues)
- Admin provides suspension reason
- Removes venue from public directory
- Used for policy violations or outdated information

#### 📄 Request Documents
- Sends an email to the venue owner requesting additional verification documents
- Status remains `pending_review`
- Used when more proof is needed (utility bills, tax certificates, etc.)

### 6. Venue Statuses

| Status | Description | Visible in Directory? |
|--------|-------------|----------------------|
| `draft` | Venue is being created/edited | No |
| `pending_review` | Submitted for admin review | No |
| `approved` | Approved and live | Yes |
| `rejected` | Rejected with reason | No |
| `suspended` | Previously approved, now suspended | No |

## Accessing the Admin Panel

### For Platform Admins

1. Log in to Event Dynamics at: https://eventdynamics.io
2. If you have `isPlatformAdmin` flag, you'll see an "Admin" link in your navigation
3. Click **"Admin"** in the main navigation
4. Click **"Venues"** in the admin sidebar (newly added!)
5. You'll see the venue review queue

### For Developers/Setting Up Admin Access

To grant platform admin access to a user:

1. **Via Database** (PostgreSQL):
   ```sql
   -- Update the user's JWT payload in your authentication system
   -- Exact method depends on your auth implementation
   -- The JWT should include: { "isPlatformAdmin": true }
   ```

2. **Via Backend API** (if you have a user management endpoint):
   - Update the user record to set `isPlatformAdmin` flag
   - Regenerate the JWT token with the new flag

3. **Security Note**:
   - The `isPlatformAdmin` flag is verified server-side by decoding the JWT
   - Client-side manipulation is prevented by middleware JWT decoding
   - See [middleware.ts:98-100](../../globalconnect/middleware.ts#L98-L100)

## What Venue Owners See

Venue owners can check their submission status at:
```
https://eventdynamics.io/my-venues
```

Each venue card shows:
- **Draft**: Gray status badge - "Not submitted"
- **Pending Review**: Yellow status badge - "Under review"
- **Approved**: Green status badge - "Live in directory"
- **Rejected**: Red status badge - "Rejected" (with reason visible)

## Email Notifications

The system supports email notifications for:
- ✅ Venue approved
- ❌ Venue rejected (with reason)
- 🛑 Venue suspended (with reason)
- 📄 Documents requested

Email configuration is in `app/core/email.py`.

## Recent Fix

**Issue**: The "Venues" link was missing from the admin navigation menu, making it hard for admins to find the review queue.

**Fix** (2026-02-21): Added "Venues" navigation item to admin sidebar at [globalconnect/src/app/(admin)/layout.tsx](../../globalconnect/src/app/(admin)/layout.tsx#L36-L41)

## API Reference

### GraphQL Mutations

**Submit for Review** (Venue Owner):
```graphql
mutation SubmitVenue($id: ID!) {
  submitVenueForReview(id: $id) {
    id
    status
    submittedAt
  }
}
```

**Approve Venue** (Platform Admin):
```graphql
mutation ApproveVenue($id: ID!) {
  approveVenue(id: $id) {
    id
    status
    approvedAt
  }
}
```

**Reject Venue** (Platform Admin):
```graphql
mutation RejectVenue($id: ID!, $reason: String!) {
  rejectVenue(id: $id, reason: $reason) {
    id
    status
    rejectionReason
  }
}
```

**Suspend Venue** (Platform Admin):
```graphql
mutation SuspendVenue($id: ID!, $reason: String!) {
  suspendVenue(id: $id, reason: $reason) {
    id
    status
    rejectionReason
  }
}
```

### REST Endpoints

**Request Documents** (Platform Admin):
```http
POST /api/v1/admin/venues/{venueId}/request-documents
Content-Type: application/json
Cookie: token=<jwt>

{
  "message": "Please upload a utility bill or tax certificate to verify your address."
}
```

## Testing the Flow

1. **As Venue Owner**:
   - Create a venue in "My Venues"
   - Add all required info (photos, spaces, amenities)
   - Click "Submit for Review"
   - Check status changes to "Pending Review"

2. **As Platform Admin**:
   - Go to `/admin/venues`
   - See the venue in the queue
   - Review the details
   - Approve, reject, or request documents

3. **Verify**:
   - Approved venues appear at `/venues`
   - Rejected venues show reason to owner
   - Email notifications are sent (if configured)

## Troubleshooting

**Q: I submitted a venue but don't see it anywhere**
A: Only platform admins can see pending submissions. Regular users and even organization admins cannot see the review queue.

**Q: How do I become a platform admin?**
A: Platform admin access must be granted by a system administrator or developer with database access. Contact your development team.

**Q: The "Venues" link is missing from admin menu**
A: This was fixed on 2026-02-21. Pull the latest changes and redeploy the frontend.

**Q: Can I approve my own venue?**
A: No. Even if you're a platform admin, the review process is meant to be independent to maintain directory quality.

## Future Enhancements

Potential improvements to the review system:
- Automated checks for completeness (photos, required fields)
- AI-powered content moderation for descriptions
- Bulk approval/rejection actions
- Review assignment to specific admins
- SLA tracking (time to review)
- Venue quality scoring
- Public review comments from customers
