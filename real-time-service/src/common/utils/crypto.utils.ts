// src/common/utils/crypto.utils.ts
import { createCipheriv, createDecipheriv, randomBytes, scryptSync } from 'crypto';

const ALGORITHM = 'aes-256-gcm';
const IV_LENGTH = 16;
const AUTH_TAG_LENGTH = 16;
const SALT_LENGTH = 32;

/**
 * Encrypts sensitive data using AES-256-GCM.
 * Returns a combined string: salt:iv:authTag:encryptedData (all base64 encoded)
 */
export function encrypt(plainText: string, secretKey: string): string {
  if (!plainText || !secretKey) {
    throw new Error('Both plainText and secretKey are required for encryption');
  }

  // Generate random salt and IV
  const salt = randomBytes(SALT_LENGTH);
  const iv = randomBytes(IV_LENGTH);

  // Derive key from secret using scrypt
  const key = scryptSync(secretKey, salt, 32);

  // Create cipher and encrypt
  const cipher = createCipheriv(ALGORITHM, key, iv);
  let encrypted = cipher.update(plainText, 'utf8', 'base64');
  encrypted += cipher.final('base64');

  // Get auth tag for GCM mode
  const authTag = cipher.getAuthTag();

  // Combine salt:iv:authTag:encryptedData
  return [
    salt.toString('base64'),
    iv.toString('base64'),
    authTag.toString('base64'),
    encrypted,
  ].join(':');
}

/**
 * Decrypts data that was encrypted with encrypt().
 * Expects format: salt:iv:authTag:encryptedData (all base64 encoded)
 */
export function decrypt(encryptedData: string, secretKey: string): string {
  if (!encryptedData || !secretKey) {
    throw new Error('Both encryptedData and secretKey are required for decryption');
  }

  // Split the combined string
  const parts = encryptedData.split(':');
  if (parts.length !== 4) {
    throw new Error('Invalid encrypted data format');
  }

  const [saltB64, ivB64, authTagB64, cipherTextB64] = parts;

  // Decode from base64
  const salt = Buffer.from(saltB64, 'base64');
  const iv = Buffer.from(ivB64, 'base64');
  const authTag = Buffer.from(authTagB64, 'base64');

  // Derive key from secret using same salt
  const key = scryptSync(secretKey, salt, 32);

  // Create decipher
  const decipher = createDecipheriv(ALGORITHM, key, iv);
  decipher.setAuthTag(authTag);

  // Decrypt
  let decrypted = decipher.update(cipherTextB64, 'base64', 'utf8');
  decrypted += decipher.final('utf8');

  return decrypted;
}

/**
 * Check if a string looks like it's already encrypted (contains our format)
 */
export function isEncrypted(value: string): boolean {
  if (!value) return false;
  const parts = value.split(':');
  return parts.length === 4 && parts.every((p) => p.length > 0);
}
