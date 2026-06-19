/**
 * Auto-seed API keys from the SEED_API_KEYS environment variable on startup.
 *
 * Format: JSON array of objects: [{"platform":"google","key":"AIza...","label":"main"}]
 * Or pipe-separated shorthand: platform:key:label|platform:key:label
 *
 * Keys already present for a platform (by label match or key content) are skipped.
 * This ensures no duplicates across restarts while keeping the DB as source of truth.
 */

import { getDb } from '../db/index.js';
import { encrypt, decrypt } from '../lib/crypto.js';

interface SeedEntry {
  platform: string;
  key: string;
  label?: string;
}

function parseSeedKeys(raw: string): SeedEntry[] {
  const trimmed = raw.trim();
  if (!trimmed) return [];

  // Try JSON array first
  if (trimmed.startsWith('[')) {
    try {
      const parsed = JSON.parse(trimmed);
      if (Array.isArray(parsed)) return parsed;
    } catch {
      // fall through to pipe format
    }
  }

  // Pipe-separated: platform:key:label|platform:key:label
  return trimmed.split('|').map(entry => {
    const parts = entry.split(':');
    if (parts.length < 2) return null;
    // Handle keys that contain colons (e.g. base64) — rejoin everything after first colon except last segment if 3+ parts
    const platform = parts[0].trim();
    let key: string;
    let label = '';
    if (parts.length === 2) {
      key = parts[1].trim();
    } else {
      // Last part is label, middle is key (may contain colons)
      label = parts[parts.length - 1].trim();
      key = parts.slice(1, -1).join(':').trim();
    }
    return { platform, key, label };
  }).filter(Boolean) as SeedEntry[];
}

function keyAlreadyExists(platform: string, plainKey: string): boolean {
  const db = getDb();
  const rows = db.prepare(
    'SELECT encrypted_key, iv, auth_tag FROM api_keys WHERE platform = ? AND enabled = 1'
  ).all(platform) as { encrypted_key: string; iv: string; auth_tag: string }[];

  for (const row of rows) {
    try {
      const decrypted = decrypt(row.encrypted_key, row.iv, row.auth_tag);
      if (decrypted === plainKey) return true;
    } catch {
      // skip keys that can't be decrypted (stale encryption key)
    }
  }
  return false;
}

export function seedKeysFromEnv(): void {
  const raw = process.env.SEED_API_KEYS;
  if (!raw) return;

  const entries = parseSeedKeys(raw);
  if (entries.length === 0) return;

  const db = getDb();
  let added = 0;
  let skipped = 0;

  for (const entry of entries) {
    if (!entry.platform || !entry.key) {
      console.warn(`[seed] Skipping invalid entry: missing platform or key`);
      continue;
    }

    if (keyAlreadyExists(entry.platform, entry.key)) {
      skipped++;
      continue;
    }

    const { encrypted, iv, authTag } = encrypt(entry.key);
    db.prepare(`
      INSERT INTO api_keys (platform, label, encrypted_key, iv, auth_tag, status, enabled)
      VALUES (?, ?, ?, ?, ?, 'unknown', 1)
    `).run(entry.platform, entry.label ?? '', encrypted, iv, authTag);
    added++;
  }

  if (added > 0 || skipped > 0) {
    console.log(`[seed] API keys: ${added} added, ${skipped} already present`);
  }
}
