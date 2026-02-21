# S3 Bucket Configuration for Venue Photos

## Problem
Venue photos are uploading successfully to S3 but returning 403 (Forbidden) errors when trying to display them in the browser.

## Root Cause
The S3 bucket `108782064634-globalconnect-uploads` has "Block all public access" enabled, which prevents public read access to the uploaded images.

## Solution
Apply a bucket policy that allows public read access to the `venue-images/` prefix while keeping other objects private.

## Steps to Fix

### Option 1: Using AWS Console (Recommended)

1. **Go to AWS S3 Console**
   - Navigate to: https://s3.console.aws.amazon.com/s3/buckets/108782064634-globalconnect-uploads
   - Or search for "S3" in AWS Console and select your bucket

2. **Update Block Public Access Settings**
   - Click on the "Permissions" tab
   - Under "Block public access (bucket settings)", click "Edit"
   - **Uncheck** "Block public access to buckets and objects granted through new public bucket or access point policies"
   - Keep other options as they are (you can keep "Block all public access" unchecked)
   - Click "Save changes"
   - Confirm by typing "confirm"

3. **Add Bucket Policy**
   - Still on the "Permissions" tab, scroll down to "Bucket policy"
   - Click "Edit"
   - Copy and paste this policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadVenueImages",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::108782064634-globalconnect-uploads/venue-images/*"
    }
  ]
}
```

   - Click "Save changes"

4. **Verify the Fix**
   - After applying the policy, refresh your venue page in the browser
   - The photos should now display without 403 errors
   - Check the browser console to confirm no more 403 errors

### Option 2: Using AWS CLI

```bash
# 1. Update block public access settings
aws s3api put-public-access-block \
  --bucket 108782064634-globalconnect-uploads \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=false,RestrictPublicBuckets=false"

# 2. Apply bucket policy
aws s3api put-bucket-policy \
  --bucket 108782064634-globalconnect-uploads \
  --policy file://docs/s3-bucket-policy.json
```

## Security Notes

✅ **This is SAFE because:**
- Only the `venue-images/*` prefix is publicly readable
- All other files in the bucket remain private
- Users still need authentication to upload photos
- The bucket policy only allows `GetObject` (read), not upload/delete/list

❌ **Do NOT:**
- Make the entire bucket public
- Allow public write access
- Disable all block public access settings

## Testing

After applying the bucket policy, test by:
1. Uploading a new venue photo
2. Checking if it displays immediately without errors
3. Verifying in browser DevTools Network tab that GET requests return 200 (not 403)

## Alternative Approach (If You Want to Keep Bucket Private)

If you prefer to keep the bucket completely private, we can modify the backend to generate presigned URLs for each photo. However, this:
- Requires code changes
- URLs expire after a certain time (default 5 minutes)
- Adds latency to page loads

For publicly viewable venue photos, the bucket policy approach is recommended.
