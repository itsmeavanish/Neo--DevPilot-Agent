import { Router } from 'express';
import type { Request, Response } from 'express';
import { getPermanentApiKey, regenerateUnifiedKey } from '../db/index.js';

export const settingsRouter = Router();

// Get the unified API key (returns the permanent static key if configured)
settingsRouter.get('/api-key', (_req: Request, res: Response) => {
  res.json({ apiKey: getPermanentApiKey() });
});

// Regenerate the unified API key (no-op if static key is configured)
settingsRouter.post('/api-key/regenerate', (_req: Request, res: Response) => {
  const newKey = regenerateUnifiedKey();
  res.json({ apiKey: newKey });
});
