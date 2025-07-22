// In src/test-client.ts

import { io } from 'socket.io-client';

// --- IMPORTANT ---
// 1. Run your 'user-and-org-service' and log in to get a valid token.
// 2. Paste that valid access_token here.
const JWT =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjbWN4dngyM2cwMDAxdHI5YzRtM3NodnNmIiwiZW1haWwiOiJtYW5zYXJheXNhaGVlZGFscGhhQGdtYWlsLmNvbSIsImlhdCI6MTc1MjE4MjE0MiwiZXhwIjoxNzUyMTgzMDQyfQ.J5-pUyhXY4QcryAEtDn9Fv4flvI7lz4RrLSO86xSZxA';

const socket = io('ws://localhost:3002/events', {
  auth: {
    token: JWT,
  },
});

socket.on('connect', () => {
  console.log('✅ CLIENT: Successfully connected to the server!');
  console.log('Socket ID:', socket.id);
});

socket.on('disconnect', (reason) => {
  console.log(`❌ CLIENT: Disconnected from server. Reason: ${reason}`);
});

// Listen for our custom 'connected' event from the server
socket.on('connected', (data) => {
  console.log('🎉 CLIENT: Received "connected" event from server:', data);
});

// Listen for our custom 'error' event from the server
socket.on('error', (error) => {
  console.error('🔥 CLIENT: Received error from server:', error);
});

console.log('Attempting to connect...');
