// src/common/utils/encryption.util.ts
import { createCipheriv, createDecipheriv, randomBytes } from 'crypto';

const ALGORITHM = 'aes-256-gcm';
const IV_LENGTH = 16;
const AUTH_TAG_LENGTH = 16;

/**
 * Encrypts a string using AES-256-GCM.
 * @param text - The plaintext to encrypt
 * @param encryptionKey - 32-byte hex string (64 characters)
 * @returns Encrypted string in format: iv:authTag:encryptedData (all base64)
 */
export function encrypt(text: string, encryptionKey: string): string {
  const key = Buffer.from(encryptionKey, 'hex');
  const iv = randomBytes(IV_LENGTH);

  const cipher = createCipheriv(ALGORITHM, key, iv);

  let encrypted = cipher.update(text, 'utf8', 'base64');
  encrypted += cipher.final('base64');

  const authTag = cipher.getAuthTag();

  // Format: iv:authTag:encryptedData (all base64 encoded)
  return `${iv.toString('base64')}:${authTag.toString('base64')}:${encrypted}`;
}

/**
 * Decrypts a string that was encrypted with the encrypt function.
 * @param encryptedText - The encrypted string in format: iv:authTag:encryptedData
 * @param encryptionKey - 32-byte hex string (64 characters)
 * @returns The decrypted plaintext
 */
export function decrypt(encryptedText: string, encryptionKey: string): string {
  const key = Buffer.from(encryptionKey, 'hex');
  const parts = encryptedText.split(':');

  if (parts.length !== 3) {
    throw new Error('Invalid encrypted text format');
  }

  const iv = Buffer.from(parts[0], 'base64');
  const authTag = Buffer.from(parts[1], 'base64');
  const encrypted = parts[2];

  const decipher = createDecipheriv(ALGORITHM, key, iv);
  decipher.setAuthTag(authTag);

  let decrypted = decipher.update(encrypted, 'base64', 'utf8');
  decrypted += decipher.final('utf8');

  return decrypted;
}

/**
 * Generates a random 32-byte encryption key as a hex string.
 * Use this to generate the ENCRYPTION_KEY environment variable.
 */
export function generateEncryptionKey(): string {
  return randomBytes(32).toString('hex');
}
