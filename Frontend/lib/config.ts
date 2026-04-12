import * as SecureStore from 'expo-secure-store';

// ==============================================
// JARVIS Configuration Manager
// Single app for single laptop - pairing code based
// ==============================================

const STORAGE_KEYS = {
  BACKEND_URL: 'jarvis_backend_url',
  PAIRING_CODE: 'jarvis_pairing_code',
  LAPTOP_NAME: 'jarvis_laptop_name',
  IS_PAIRED: 'jarvis_is_paired',
};

// Default ngrok URL
export const DEFAULT_NGROK_URL = 'https://precommercial-nubbly-theda.ngrok-free.dev';

class ConfigManager {
    // Warn if backend URL is unsafe for production
    get isBackendUrlUnsafe(): boolean {
      return (
        this._backendUrl.includes('localhost') ||
        this._backendUrl.includes('127.0.0.1')
      );
    }
  private _backendUrl: string = DEFAULT_NGROK_URL;
  private _pairingCode: string = '';
  private _laptopName: string = '';
  private _isPaired: boolean = false;
  private initialized = false;

  async init(): Promise<void> {
    if (this.initialized) return;

    try {
      const savedUrl = await SecureStore.getItemAsync(STORAGE_KEYS.BACKEND_URL);
      const savedCode = await SecureStore.getItemAsync(STORAGE_KEYS.PAIRING_CODE);
      const savedName = await SecureStore.getItemAsync(STORAGE_KEYS.LAPTOP_NAME);
      const savedPaired = await SecureStore.getItemAsync(STORAGE_KEYS.IS_PAIRED);

      if (savedUrl) this._backendUrl = savedUrl;
      if (savedCode) this._pairingCode = savedCode;
      if (savedName) this._laptopName = savedName;
      if (savedPaired) this._isPaired = savedPaired === 'true';

      this.initialized = true;
    } catch (error) {
      console.error('Failed to load config:', error);
      this.initialized = true; // Continue anyway
    }
  }

  // Check if user has paired with a laptop
  get isPaired(): boolean {
    return this._isPaired && this._pairingCode.length > 0;
  }

  // Get the pairing code
  get pairingCode(): string {
    return this._pairingCode;
  }

  // Get laptop name
  get laptopName(): string {
    return this._laptopName;
  }

  // Get backend URL
  get backendUrl(): string {
    return this._backendUrl;
  }

  // Pair with a laptop using the pairing code
  async pairWithLaptop(code: string, laptopName: string = 'My Laptop'): Promise<void> {
    this._pairingCode = code.toUpperCase().trim();
    this._laptopName = laptopName;
    this._isPaired = true;

    try {
      await SecureStore.setItemAsync(STORAGE_KEYS.PAIRING_CODE, this._pairingCode);
      await SecureStore.setItemAsync(STORAGE_KEYS.LAPTOP_NAME, this._laptopName);
      await SecureStore.setItemAsync(STORAGE_KEYS.IS_PAIRED, 'true');
    } catch (error) {
      console.error('Failed to save pairing:', error);
    }
  }

  // Unpair from laptop
  async unpair(): Promise<void> {
    this._pairingCode = '';
    this._laptopName = '';
    this._isPaired = false;

    try {
      await SecureStore.deleteItemAsync(STORAGE_KEYS.PAIRING_CODE);
      await SecureStore.deleteItemAsync(STORAGE_KEYS.LAPTOP_NAME);
      await SecureStore.deleteItemAsync(STORAGE_KEYS.IS_PAIRED);
    } catch (error) {
      console.error('Failed to clear pairing:', error);
    }
  }

  // Set backend URL
  async setBackendUrl(url: string): Promise<void> {
    this._backendUrl = url.replace(/\/$/, '');
    try {
      await SecureStore.setItemAsync(STORAGE_KEYS.BACKEND_URL, this._backendUrl);
    } catch (error) {
      console.error('Failed to save URL:', error);
    }
  }

  // Test connection to laptop
  async testLaptopConnection(): Promise<{ online: boolean; hostname?: string; platform?: string }> {
    if (!this._pairingCode) {
      return { online: false };
    }

    try {
      const response = await fetch(`${this._backendUrl}/api/v1/ws/agents/${this._pairingCode}`, {
        headers: { 'ngrok-skip-browser-warning': 'true' },
      });

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
    } catch (error) {
      return { online: false };
    }
  }
}

export const configManager = new ConfigManager();
export default configManager;
