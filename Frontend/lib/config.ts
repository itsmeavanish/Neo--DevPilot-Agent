/**
 * Config manager – persists and manages multiple server profiles
 * using AsyncStorage so settings survive app restarts.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { updateApiConfig } from './api';

const STORAGE_KEY = 'jarvis_server_profiles';
const ACTIVE_KEY = 'jarvis_active_profile';

export interface ServerProfile {
  id: string;
  name: string;
  url: string;
  apiKey: string;
  isDefault?: boolean;
}

const DEFAULT_PROFILE: ServerProfile = {
  id: 'default',
  name: 'Local',
  url: 'http://localhost:8000',
  apiKey: '',
  isDefault: true,
};

class ConfigManager {
  private _profiles: ServerProfile[] = [DEFAULT_PROFILE];
  private _activeId: string = 'default';

  get serverProfiles(): ServerProfile[] {
    return this._profiles;
  }

  get activeProfile(): ServerProfile | null {
    return this._profiles.find((p) => p.id === this._activeId) ?? null;
  }

  get backendUrl(): string {
    return this.activeProfile?.url ?? DEFAULT_PROFILE.url;
  }

  async init(): Promise<void> {
    try {
      const raw = await AsyncStorage.getItem(STORAGE_KEY);
      if (raw) this._profiles = JSON.parse(raw);
    } catch {
      // AsyncStorage unavailable or data corrupt — use default profile
    }

    try {
      const activeId = await AsyncStorage.getItem(ACTIVE_KEY);
      if (activeId) this._activeId = activeId;
    } catch {
      // AsyncStorage unavailable — use default active profile
    }

    // Sync API config
    this._syncApiConfig();
  }

  async addProfile(profile: Omit<ServerProfile, 'id'>): Promise<ServerProfile> {
    const newProfile: ServerProfile = {
      ...profile,
      id: Date.now().toString(),
    };
    this._profiles.push(newProfile);
    await this._save();
    return newProfile;
  }

  async updateProfile(id: string, updates: Partial<ServerProfile>): Promise<void> {
    const idx = this._profiles.findIndex((p) => p.id === id);
    if (idx !== -1) {
      this._profiles[idx] = { ...this._profiles[idx], ...updates };
      await this._save();
      if (id === this._activeId) this._syncApiConfig();
    }
  }

  async removeProfile(id: string): Promise<void> {
    if (id === 'default') return; // Cannot remove default
    this._profiles = this._profiles.filter((p) => p.id !== id);
    if (this._activeId === id) {
      this._activeId = 'default';
      await AsyncStorage.setItem(ACTIVE_KEY, this._activeId);
      this._syncApiConfig();
    }
    await this._save();
  }

  async setActive(id: string): Promise<void> {
    if (!this._profiles.find((p) => p.id === id)) return;
    this._activeId = id;
    await AsyncStorage.setItem(ACTIVE_KEY, id);
    this._syncApiConfig();
  }

  private _syncApiConfig(): void {
    const profile = this.activeProfile;
    if (profile) {
      updateApiConfig({ baseUrl: profile.url, apiKey: profile.apiKey });
    }
  }

  private async _save(): Promise<void> {
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(this._profiles));
  }
}

const configManager = new ConfigManager();
export default configManager;
