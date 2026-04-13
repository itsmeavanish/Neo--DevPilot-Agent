/**
 * JARVIS API Client
 *
 * Provides typed wrappers for every backend endpoint consumed by the
 * React-Native / Expo front-end.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

// ─────────────────────────────────────────────────────────────────────────────
// Config
// ─────────────────────────────────────────────────────────────────────────────

export interface ApiConfig {
  baseUrl: string;
  apiKey: string;
}

let _config: ApiConfig = {
  baseUrl: 'http://localhost:8000',
  apiKey: '',
};

/** Update the global API config (call after loading from storage). */
export function updateApiConfig(cfg?: Partial<ApiConfig>) {
  if (cfg) Object.assign(_config, cfg);
}

/** Return the current base URL (useful for settings UI). */
export function getApiUrl(): string {
  return _config.baseUrl;
}

export const API_CONFIG = _config; // reference kept for legacy usage

// ─────────────────────────────────────────────────────────────────────────────
// HTTP helpers
// ─────────────────────────────────────────────────────────────────────────────

async function headers(): Promise<Record<string, string>> {
  const h: Record<string, string> = { 'Content-Type': 'application/json' };
  if (_config.apiKey) h['X-API-Key'] = _config.apiKey;
  return h;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${_config.baseUrl}${path}`, {
    headers: await headers(),
  });
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${_config.baseUrl}${path}`, {
    method: 'POST',
    headers: await headers(),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let msg = `POST ${path} → ${res.status}`;
    try {
      const err = await res.json();
      if (err?.detail) msg = String(err.detail);
    } catch { /* ignore */ }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${_config.baseUrl}${path}`, {
    method: 'DELETE',
    headers: await headers(),
  });
  if (!res.ok) throw new Error(`DELETE ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

// ─────────────────────────────────────────────────────────────────────────────
// Shared types
// ─────────────────────────────────────────────────────────────────────────────

export interface CommandResponse {
  status: 'success' | 'error' | 'info';
  stdout?: string;
  stderr?: string;
  exit_code?: number;
  message?: string;
}

export interface SystemInfo {
  status: string;
  platform: string;
  platform_version: string;
  hostname: string;
  cpu_percent?: number;
  memory_total_gb?: number;
  memory_used_gb?: number;
  memory_percent?: number;
  disk_total_gb?: number;
  disk_used_gb?: number;
  disk_percent?: number;
}

export interface FileInfo {
  name: string;
  path: string;
  is_dir: boolean;
  size: number;
  extension: string;
}

export interface FileContent {
  path: string;
  content: string;
  lines: number;
  language: string;
  size: number;
  error?: string;
}

export interface ProjectInfo {
  path: string;
  name: string;
  type: string;
  code_files: number;
  has_git: boolean;
  has_package_json: boolean;
  has_requirements: boolean;
  error?: string;
}

export interface AIProvidersResponse {
  current: string;
  providers: Record<string, { available: boolean; message: string; selected: boolean }>;
}

export interface GitHubAuthStatus {
  authenticated: boolean;
  username?: string;
  account_type?: string;
  scopes: string[];
  message: string;
}

export interface DeviceInfo {
  id: string;
  name: string;
  status: string;
  hostname?: string;
  platform?: string;
  last_seen?: string;
  capabilities: string[];
}

export interface DeviceWithToken extends DeviceInfo {
  token: string;
}

export interface CopilotEditResponse {
  success: boolean;
  original_content: string;
  suggested_content: string;
  diff: string;
  message: string;
  applied: boolean;
}

// ─────────────────────────────────────────────────────────────────────────────
// Health / Connectivity
// ─────────────────────────────────────────────────────────────────────────────

export async function checkHealth(): Promise<{ status: string; version?: string }> {
  return get('/health');
}

export async function ping(): Promise<CommandResponse> {
  return get('/commands/ping');
}

// ─────────────────────────────────────────────────────────────────────────────
// System Commands
// ─────────────────────────────────────────────────────────────────────────────

export async function runSystemCommand(command: string): Promise<CommandResponse> {
  return post('/system/run', { command });
}

export async function getSystemInfo(): Promise<SystemInfo> {
  return get('/system/info');
}

// ─────────────────────────────────────────────────────────────────────────────
// Git
// ─────────────────────────────────────────────────────────────────────────────

export async function runGitCommand(command: string): Promise<CommandResponse> {
  return post('/git/run', { command });
}

// ─────────────────────────────────────────────────────────────────────────────
// VS Code / IDE
// ─────────────────────────────────────────────────────────────────────────────

export async function openVSCode(): Promise<CommandResponse> {
  return post('/vscode/open', {});
}

export async function openProject(path: string): Promise<CommandResponse> {
  return post('/vscode/open-project', { path });
}

// ─────────────────────────────────────────────────────────────────────────────
// Files / Project
// ─────────────────────────────────────────────────────────────────────────────

export async function listDirectory(
  path: string,
  show_hidden = false,
): Promise<{ path: string; files: FileInfo[]; count: number; error?: string }> {
  return post('/project/list', { path, show_hidden });
}

export async function readFile(path: string, max_lines = 500): Promise<FileContent> {
  return post('/project/read', { path, max_lines });
}

export async function writeFile(
  path: string,
  content: string,
  create_backup = true,
): Promise<{ success: boolean; path: string; message: string; backup_path?: string }> {
  return post('/project/write', { path, content, create_backup });
}

export async function getProjectInfo(path: string): Promise<ProjectInfo> {
  return post('/project/info', { path });
}

// ─────────────────────────────────────────────────────────────────────────────
// Copilot
// ─────────────────────────────────────────────────────────────────────────────

export async function runCopilot(command: string): Promise<CommandResponse> {
  return post('/copilot/run', { command });
}

export async function copilotEdit(
  file_path: string,
  instruction: string,
  apply_changes = false,
): Promise<CopilotEditResponse> {
  return post('/copilot/edit', { file_path, instruction, apply_changes });
}

// ─────────────────────────────────────────────────────────────────────────────
// AI Providers & Ask
// ─────────────────────────────────────────────────────────────────────────────

export async function getAIProviders(): Promise<AIProvidersResponse> {
  return get('/project/ai/providers');
}

export async function setAIProvider(
  provider: string,
): Promise<{ success: boolean; provider: string; message: string }> {
  return post('/project/ai/set-provider', { provider });
}

export async function askAI(
  prompt: string,
  code_context?: string,
  file_path?: string,
  language?: string,
): Promise<{ status: string; response: string; error?: string }> {
  return post('/project/ai/ask', { prompt, code_context, file_path, language });
}

// ─────────────────────────────────────────────────────────────────────────────
// Conversational Chat (new multi-turn endpoint)
// ─────────────────────────────────────────────────────────────────────────────

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatResponse {
  session_id: string;
  response: string;
  error?: string;
}

/**
 * Send a multi-turn chat message to JARVIS.
 * Pass all previous messages to maintain conversation context.
 */
export async function chatWithAgent(
  message: string,
  history: ChatMessage[] = [],
  session_id?: string,
): Promise<ChatResponse> {
  return post('/api/v1/agent/chat', { message, history, session_id });
}

// ─────────────────────────────────────────────────────────────────────────────
// AI Code Review (new endpoint)
// ─────────────────────────────────────────────────────────────────────────────

export interface CodeReviewResult {
  summary: string;
  issues: Array<{ severity: 'critical' | 'warning' | 'info'; line?: number; message: string; suggestion?: string }>;
  score: number;
  error?: string;
}

export async function reviewCode(
  code: string,
  language: string,
  file_path?: string,
): Promise<CodeReviewResult> {
  return post('/api/v1/agent/review', { code, language, file_path });
}

// ─────────────────────────────────────────────────────────────────────────────
// GitHub Auth
// ─────────────────────────────────────────────────────────────────────────────

export async function getGitHubAuthStatus(): Promise<GitHubAuthStatus> {
  return get('/github/auth/status');
}

export async function githubLogin(): Promise<{
  success: boolean;
  message: string;
  auth_url?: string;
}> {
  return post('/github/auth/login', {});
}

export async function githubLogout(): Promise<{ success: boolean; message: string }> {
  return post('/github/auth/logout', {});
}

// ─────────────────────────────────────────────────────────────────────────────
// Multi-Device Management
// ─────────────────────────────────────────────────────────────────────────────

export async function listDevices(): Promise<DeviceInfo[]> {
  return get('/devices');
}

export async function registerDevice(
  name: string,
  capabilities?: string[],
): Promise<DeviceWithToken> {
  return post('/devices', { name, capabilities });
}

export async function deleteDevice(id: string): Promise<{ success: boolean }> {
  return del(`/devices/${id}`);
}

export async function executeOnDevice(
  id: string,
  command: string,
  timeout = 120,
): Promise<{ success: boolean; stdout: string; stderr: string; exit_code: number; error?: string }> {
  return post(`/devices/${id}/execute`, { command, timeout });
}

export async function getDeviceStatus(id: string): Promise<DeviceInfo> {
  return get(`/devices/${id}`);
}

export async function rotateDeviceToken(id: string): Promise<{ token: string }> {
  return post(`/devices/${id}/rotate-token`, {});
}
