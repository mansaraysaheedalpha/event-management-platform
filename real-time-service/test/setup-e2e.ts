import * as dotenv from 'dotenv';
import * as path from 'path';

// This line reads the .env file from the project root (one level up from /test)
// and loads its variables into the environment for the test run.
dotenv.config({ path: path.resolve(__dirname, '../.env') });
