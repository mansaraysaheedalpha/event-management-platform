/**
 * Script to resync booth leads from MongoDB to PostgreSQL
 *
 * Usage:
 *   node resync-booth-leads.js <boothId|sponsorId>
 *
 * Examples:
 *   node resync-booth-leads.js abc123-booth-id
 *   node resync-booth-leads.js spon_ae51186d66f7
 *
 * This script calls the internal resync endpoint to copy all leads
 * from MongoDB (real-time-service) to PostgreSQL (event-lifecycle-service).
 *
 * Note: Requires INTERNAL_API_KEY environment variable to be set.
 */

const idArg = process.argv[2];

if (!idArg) {
  console.error('Usage: node resync-booth-leads.js <boothId|sponsorId>');
  console.error('\nTo find your boothId, check the browser console when on the booth dashboard.');
  console.error('Look for logs like: "[ExpoStaffProvider] Setting booth data: { boothId: ... }"');
  console.error('\nTo use a sponsorId, pass an ID that starts with "spon_" (e.g., spon_ae51186d66f7)');
  process.exit(1);
}

// Detect if this is a sponsorId (starts with "spon_")
const isSponsorId = idArg.startsWith('spon_');

const REALTIME_SERVICE_URL = process.env.REALTIME_SERVICE_URL || 'http://localhost:3002';
const INTERNAL_API_KEY = process.env.INTERNAL_API_KEY || 'dev-internal-key';

async function resyncLeads() {
  const idType = isSponsorId ? 'sponsor' : 'booth';
  console.log(`\nResyncing leads for ${idType}: ${idArg}`);
  console.log(`Real-time service URL: ${REALTIME_SERVICE_URL}`);
  console.log('---');

  try {
    const payload = isSponsorId ? { sponsorId: idArg } : { boothId: idArg };

    const response = await fetch(`${REALTIME_SERVICE_URL}/internal/expo/booth-leads/resync`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Internal-Api-Key': INTERNAL_API_KEY,
      },
      body: JSON.stringify(payload),
    });

    const data = await response.json();

    if (!response.ok) {
      console.error('Error:', data.error || data.message || 'Unknown error');
      process.exit(1);
    }

    console.log('\nResync completed!');
    if (data.boothId) {
      console.log(`Booth ID: ${data.boothId}`);
    }
    if (data.boothName) {
      console.log(`Booth Name: ${data.boothName}`);
    }
    console.log('\nSummary:');
    console.log(`  Total leads:  ${data.summary.total}`);
    console.log(`  Synced:       ${data.summary.synced}`);
    console.log(`  Failed:       ${data.summary.failed}`);

    if (data.summary.failed > 0) {
      console.log('\nFailed leads:');
      data.results.filter(r => !r.success).forEach(r => {
        console.log(`  - ${r.visitorId}: ${r.error}`);
      });
    }

    if (data.summary.synced > 0) {
      console.log('\nLeads should now appear on the Sponsor Dashboard and Booth Dashboard.');
      console.log('Refresh the pages to see the updated data.');
    } else if (data.summary.total === 0) {
      console.log('\nNo leads found in MongoDB for this booth.');
      console.log('This means the lead capture might not have happened, or the ID is incorrect.');
    }

  } catch (error) {
    console.error('Failed to connect to real-time service:', error.message);
    console.error('\nMake sure:');
    console.error('  1. The real-time-service is running');
    console.error('  2. REALTIME_SERVICE_URL is set correctly');
    console.error('  3. INTERNAL_API_KEY matches the service configuration');
    process.exit(1);
  }
}

resyncLeads();
