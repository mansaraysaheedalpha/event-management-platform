// find-booth-id.js
// Script to find your booth ID based on sponsor ID
// Run with: node find-booth-id.js <SPONSOR_ID>

const https = require('https');

const REALTIME_SERVICE_URL = process.env.REALTIME_SERVICE_URL || 'https://real-time-service-daf9.onrender.com';
const AUTH_TOKEN = process.env.AUTH_TOKEN;

async function findBoothId(sponsorId) {
  if (!AUTH_TOKEN) {
    console.error('❌ ERROR: AUTH_TOKEN environment variable is required');
    console.error('Set it to your JWT token from localStorage["auth-storage"].state.token');
    process.exit(1);
  }

  if (!sponsorId) {
    console.error('❌ ERROR: Sponsor ID is required');
    console.error('Usage: node find-booth-id.js <SPONSOR_ID>');
    process.exit(1);
  }

  console.log(`🔍 Looking up booth for sponsor: ${sponsorId}\n`);

  const url = new URL(`/api/expo/sponsor/${sponsorId}/booth`, REALTIME_SERVICE_URL);

  const options = {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${AUTH_TOKEN}`,
      'Content-Type': 'application/json',
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

          if (res.statusCode === 200 && result.booth) {
            const booth = result.booth;
            console.log('✅ Booth found!\n');
            console.log('📋 Booth Details:');
            console.log(`   ID: ${booth.id}`);
            console.log(`   Name: ${booth.name}`);
            console.log(`   Booth Number: ${booth.boothNumber}`);
            console.log(`   Tier: ${booth.tier || 'N/A'}`);
            console.log(`   Expo Hall: ${booth.expoHall?.name || 'N/A'}\n`);

            console.log('📊 Stats:');
            console.log(`   Resources: ${booth.resources?.length || 0}`);
            console.log(`   CTA Buttons: ${booth.ctaButtons?.length || 0}\n`);

            console.log('🎯 To resync leads, run:');
            console.log(`   node resync-leads.js ${booth.id}\n`);

            resolve(booth);
          } else if (res.statusCode === 404) {
            console.error('❌ Booth not found for this sponsor');
            console.error('   The sponsor might not have an expo booth set up yet.');
            reject(new Error('Booth not found'));
          } else {
            console.error(`❌ Request failed with status ${res.statusCode}`);
            console.error('Response:', result);
            reject(new Error(result.message || 'Failed to fetch booth'));
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

    req.end();
  });
}

// Get sponsor ID from command line argument
const sponsorId = process.argv[2];

findBoothId(sponsorId)
  .then(() => {
    process.exit(0);
  })
  .catch((error) => {
    console.error('\n💥 Failed to find booth:', error.message);
    process.exit(1);
  });
