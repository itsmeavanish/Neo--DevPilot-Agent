/**
 * Persisted app configuration (backend URL, pairing, optional API key).
 * Uses SecureStore so secrets survive restarts.
 */

import * as SecureStore from 'expo-secure-store';

const STORAGE_KEYS = {
  BACKEND_URL: 'jarvis_backend_url',
  IS_CUSTOM_URL: 'jarvis_is_custom_url',
  PAIRING_CODE: 'jarvis_pairing_code',
  LAPTOP_NAME: 'jarvis_laptop_name',
  IS_PAIRED: 'jarvis_is_paired',
  API_KEY: 'jarvis_api_key',
  WORKSPACE_ROOT: 'jarvis_workspace_root',
} as const;

/** Default public API base (ngrok). Override in Settings or use localhost only for same-machine dev. */
export const DEFAULT_BACKEND_URL = 'https://neo-api-oths.onrender.com';

class ConfigManager {
  private _backendUrl: string = DEFAULT_BACKEND_URL;
  private _pairingCode: string = '';
  private _laptopName: string = '';
  private _isPaired: boolean = false;
  private _apiKey: string = '';
  private _workspaceRoot: string = '';
  private initialized = false;

  get isBackendUrlUnsafe(): boolean {
    return (
      this._backendUrl.includes('localhost') ||
      this._backendUrl.includes('127.0.0.1')
    );
  }

  get backendUrl(): string {
    return this._backendUrl;
  }

  get pairingCode(): string {
    return this._pairingCode;
  }

  get laptopName(): string {
    return this._laptopName;
  }

  get isPaired(): boolean {
    return this._isPaired && this._pairingCode.length > 0;
  }

  get apiKey(): string {
    return this._apiKey;
  }

  get workspaceRoot(): string {
    return this._workspaceRoot;
  }

  async init(): Promise<void> {
    if (this.initialized) return;

    try {
      const savedUrl = await SecureStore.getItemAsync(STORAGE_KEYS.BACKEND_URL);
      const isCustomUrl = await SecureStore.getItemAsync(STORAGE_KEYS.IS_CUSTOM_URL);
      const savedCode = await SecureStore.getItemAsync(STORAGE_KEYS.PAIRING_CODE);
      const savedName = await SecureStore.getItemAsync(STORAGE_KEYS.LAPTOP_NAME);
      const savedPaired = await SecureStore.getItemAsync(STORAGE_KEYS.IS_PAIRED);
      const savedKey = await SecureStore.getItemAsync(STORAGE_KEYS.API_KEY);
      const savedWorkspace = await SecureStore.getItemAsync(STORAGE_KEYS.WORKSPACE_ROOT);

      if (isCustomUrl === 'true' && savedUrl) {
        this._backendUrl = savedUrl;
      } else {
        this._backendUrl = DEFAULT_BACKEND_URL;
      }
      if (savedCode) this._pairingCode = savedCode;
      if (savedName) this._laptopName = savedName;
      if (savedPaired) this._isPaired = savedPaired === 'true';
      if (savedKey) this._apiKey = savedKey;
      if (savedWorkspace) this._workspaceRoot = savedWorkspace;
    } catch (e) {
      console.warn('Config init:', e);
    }

    this.initialized = true;
  }

  async pairWithLaptop(code: string, laptopName: string = 'My Laptop'): Promise<void> {
    this._pairingCode = code.toUpperCase().trim();
    this._laptopName = laptopName;
    this._isPaired = true;

    try {
      await SecureStore.setItemAsync(STORAGE_KEYS.PAIRING_CODE, this._pairingCode);
      await SecureStore.setItemAsync(STORAGE_KEYS.LAPTOP_NAME, this._laptopName);
      await SecureStore.setItemAsync(STORAGE_KEYS.IS_PAIRED, 'true');
    } catch (e) {
      console.error('Failed to save pairing:', e);
    }
  }

  async unpair(): Promise<void> {
    this._pairingCode = '';
    this._laptopName = '';
    this._isPaired = false;

    try {
      await SecureStore.deleteItemAsync(STORAGE_KEYS.PAIRING_CODE);
      await SecureStore.deleteItemAsync(STORAGE_KEYS.LAPTOP_NAME);
      await SecureStore.deleteItemAsync(STORAGE_KEYS.IS_PAIRED);
    } catch (e) {
      console.error('Failed to clear pairing:', e);
    }
  }

  async setBackendUrl(url: string, isCustom: boolean = true): Promise<void> {
    this._backendUrl = url.replace(/\/$/, '');
    try {
      await SecureStore.setItemAsync(STORAGE_KEYS.BACKEND_URL, this._backendUrl);
      await SecureStore.setItemAsync(STORAGE_KEYS.IS_CUSTOM_URL, isCustom ? 'true' : 'false');
    } catch (e) {
      console.error('Failed to save backend URL:', e);
    }
  }

  async setWorkspaceRoot(path: string): Promise<void> {
    this._workspaceRoot = path.trim();
    try {
      if (this._workspaceRoot) {
        await SecureStore.setItemAsync(STORAGE_KEYS.WORKSPACE_ROOT, this._workspaceRoot);
      } else {
        await SecureStore.deleteItemAsync(STORAGE_KEYS.WORKSPACE_ROOT);
      }
    } catch (e) {
      console.error('Failed to save workspace root:', e);
    }
  }

  async setApiKey(key: string): Promise<void> {
    this._apiKey = key;
    try {
      if (key) {
        await SecureStore.setItemAsync(STORAGE_KEYS.API_KEY, key);
      } else {
        await SecureStore.deleteItemAsync(STORAGE_KEYS.API_KEY);
      }
    } catch (e) {
      console.error('Failed to save API key:', e);
    }
  }

  async testLaptopConnection(): Promise<{
    online: boolean;
    hostname?: string;
    platform?: string;
  }> {
    if (!this._pairingCode) {
      return { online: false };
    }

    try {
      const response = await fetch(
        `${this._backendUrl}/api/v1/ws/agents/${this._pairingCode}`,
        {
          headers: {
            'ngrok-skip-browser-warning': 'true',
            ...(this._apiKey ? { 'X-API-Key': this._apiKey } : {}),
          },
        }
      );

      if (response.ok) {
        const data = await response.json();
        if (data.success && data.agent) {
          return {
            online: data.agent.status === 'online',
            hostname: data.agent.hostname,
            platform: data.agent.platform,
          };
        }
      }
      return { online: false };
    } catch {
      return { online: false };
    }
  }
}

export const configManager = new ConfigManager();
export default configManager;
