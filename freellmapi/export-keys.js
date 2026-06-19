#!/usr/bin/env node
/**
 * Export API keys from a running FreeLLM SQLite database.
 *
 * Usage:
 *   1. Copy freeapi.db from your Docker container:
 *      docker cp <container_id>:/app/server/data/freeapi.db ./freeapi.db
 *
 *   2. Run this script:
 *      ENCRYPTION_KEY=682a53939b6f09531ada7bb13b6f84a68e7e91e95e3f5e14ce4f3418ed428ca5 node export-keys.js
 *
 *   3. Copy the output JSON and set it as SEED_API_KEYS env var on Render.
 *
 * The output is a JSON array suitable for the SEED_API_KEYS env var.
 */

import crypto from 'crypto';
import Database from 'better-sqlite3';
import { existsSync } from 'fs';

const ALGORITHM = 'aes-256-gcm';
const DB_PATH = process.argv[2] || './freeapi.db';

if (!existsSync(DB_PATH)) {
  console.error(`Database not found: ${DB_PATH}`);
  console.error('Copy it from Docker: docker cp <container>:/app/server/data/freeapi.db ./freeapi.db');
  process.exit(1);
}

const envKey = process.env.ENCRYPTION_KEY;
if (!envKey || envKey.length !== 64) {
  console.error('Set ENCRYPTION_KEY env var (64 hex chars from your .env file)');
  process.exit(1);
}

const key = Buffer.from(envKey, 'hex');

function decrypt(encrypted, iv, authTag) {
  const decipher = crypto.createDecipheriv(ALGORITHM, key, Buffer.from(iv, 'hex'));
  decipher.setAuthTag(Buffer.from(authTag, 'hex'));
  let decrypted = decipher.update(encrypted, 'hex', 'utf8');
  decrypted += decipher.final('utf8');
  return decrypted;
}

const db = new Database(DB_PATH, { readonly: true });

// Check if DB has its own encryption key stored (dev mode)
const settingsRow = db.prepare("SELECT value FROM settings WHERE key = 'encryption_key'").get();
if (settingsRow && settingsRow.value !== envKey) {
  console.error('WARNING: DB has a different encryption_key in settings table.');
  console.error(`DB key: ${settingsRow.value}`);
  console.error('Retrying with DB key...\n');
  const dbKey = Buffer.from(settingsRow.value, 'hex');
  // Override
  function decryptWithDbKey(encrypted, iv, authTag) {
    const decipher = crypto.createDecipheriv(ALGORITHM, dbKey, Buffer.from(iv, 'hex'));
    decipher.setAuthTag(Buffer.from(authTag, 'hex'));
    let decrypted = decipher.update(encrypted, 'hex', 'utf8');
    decrypted += decipher.final('utf8');
    return decrypted;
  }

  const rows = db.prepare('SELECT platform, label, encrypted_key, iv, auth_tag FROM api_keys WHERE enabled = 1').all();
  const keys = [];
  for (const row of rows) {
    try {
      const plainKey = decryptWithDbKey(row.encrypted_key, row.iv, row.auth_tag);
      keys.push({ platform: row.platform, key: plainKey, label: row.label || undefined });
    } catch (e) {
      console.error(`Failed to decrypt key for ${row.platform}: ${e.message}`);
    }
  }

  console.log('\n=== SEED_API_KEYS (set this as env var on Render) ===\n');
  console.log(JSON.stringify(keys));
  console.log(`\n=== ${keys.length} keys exported ===`);
  process.exit(0);
}

const rows = db.prepare('SELECT platform, label, encrypted_key, iv, auth_tag FROM api_keys WHERE enabled = 1').all();
const keys = [];

for (const row of rows) {
  try {
    const plainKey = decrypt(row.encrypted_key, row.iv, row.auth_tag);
    keys.push({ platform: row.platform, key: plainKey, label: row.label || undefined });
  } catch (e) {
    console.error(`Failed to decrypt key for ${row.platform}: ${e.message}`);
  }
}

console.log('\n=== SEED_API_KEYS (set this as env var on Render) ===\n');
console.log(JSON.stringify(keys));
console.log(`\n=== ${keys.length} keys exported ===`);
