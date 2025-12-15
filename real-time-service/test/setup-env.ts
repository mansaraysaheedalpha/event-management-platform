// test/setup-env.ts
import * as dotenv from 'dotenv';
import * as path from 'path';

// Load test environment variables from .env.test
dotenv.config({ path: path.resolve(__dirname, '../.env.test') });
