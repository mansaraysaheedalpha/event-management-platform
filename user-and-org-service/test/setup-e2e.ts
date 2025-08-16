import * as dotenv from 'dotenv';
import * as path from 'path';

// This loads the .env file from the service's root directory
dotenv.config({ path: path.resolve(__dirname, '../.env') });
