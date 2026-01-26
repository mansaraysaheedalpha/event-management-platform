// resync-leads.js
// Script to resync booth leads from MongoDB to PostgreSQL
// Run with: node resync-leads.js <BOOTH_ID>

const https = require('https');

const REALTIME_SERVICE_URL = process.env.REALTIME_SERVICE_URL || 'https://real-time-service-daf9.onrender.com';
const INTERNAL_API_KEY = process.env.INTERNAL_API_KEY;

async function resyncBoothLeads(boothId) {
  if (!INTERNAL_API_KEY) {
    console.error('❌ ERROR: INTERNAL_API_KEY environment variable is required');
    process.exit(1);
  }

  if (!boothId) {
    console.error('❌ ERROR: Booth ID is required');
    console.error('Usage: node resync-leads.js <BOOTH_ID>');
    process.exit(1);
  }

  console.log(`🔄 Resyncing leads for booth: ${boothId}`);
  console.log(`📡 Service: ${REALTIME_SERVICE_URL}\n`);

  const url = new URL('/api/expo/internal/booth-leads/resync', REALTIME_SERVICE_URL);

  const postData = JSON.stringify({ boothId });

  const options = {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Content-Length': Buffer.byteLength(postData),
      'X-Internal-Api-Key': INTERNAL_API_KEY,
    },
  };

  return new Promise((resolve, reject) => {
    const req = https.request(url, options, (res) => {
      let data = '';

      res.on('data', (chunk) => {
        data += chunk;
      });

      res.on('end', () => {
        try {
          const result = JSON.parse(data);

          if (res.statusCode === 200 && result.success) {
            console.log('✅ Resync completed successfully!\n');
            console.log('📊 Summary:');
            console.log(`   Total leads: ${result.summary.total}`);
            console.log(`   ✓ Synced: ${result.summary.synced}`);
            console.log(`   ✗ Failed: ${result.summary.failed}\n`);

            if (result.summary.failed > 0) {
              console.log('⚠️  Failed leads:');
              result.results
                .filter(r => !r.success)
                .forEach(r => {
                  console.log(`   - Visitor ${r.visitorId}: ${r.error}`);
                });
            }

            resolve(result);
          } else {
            console.error(`❌ Resync failed with status ${res.statusCode}`);
            console.error('Response:', result);
            reject(new Error(result.error || 'Resync failed'));
          }
        } catch (error) {
          console.error('❌ Failed to parse response:', error.message);
          console.error('Raw response:', data);
          reject(error);
        }
      });
    });

    req.on('error', (error) => {
      console.error('❌ Network error:', error.message);
      reject(error);
    });

    req.write(postData);
    req.end();
  });
}

// Get booth ID from command line argument
const boothId = process.argv[2];

resyncBoothLeads(boothId)
  .then(() => {
    console.log('\n✨ Done! Your leads are now synced and ready for campaigns.');
    process.exit(0);
  })
  .catch((error) => {
    console.error('\n💥 Resync failed:', error.message);
    process.exit(1);
  });
