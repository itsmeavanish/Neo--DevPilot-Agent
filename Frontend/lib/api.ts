/**
 * JARVIS API client for Expo — pairs to a laptop via agent pairing code,
 * routes shell/project/AI calls through the backend.
 */

import { Platform } from 'react-native';
import configManager from './config';

// ─────────────────────────────────────────────────────────────────────────────
// Config (legacy helpers; state lives in configManager)
// ─────────────────────────────────────────────────────────────────────────────

export interface ApiConfig {
  baseUrl: string;
  apiKey: string;
}

/** Sync URL/API key into secure config (fire-and-forget persistence). */
export function updateApiConfig(cfg?: Partial<ApiConfig>): void {
  if (!cfg) return;
  if (cfg.baseUrl !== undefined) {
    void configManager.setBackendUrl(cfg.baseUrl);
  }
  if (cfg.apiKey !== undefined) {
    void configManager.setApiKey(cfg.apiKey);
  }
}

export function getApiUrl(): string {
  return configManager.backendUrl;
}

// ─────────────────────────────────────────────────────────────────────────────
// HTTP helpers
// ─────────────────────────────────────────────────────────────────────────────

async function buildHeaders(
  extra?: Record<string, string>
): Promise<Record<string, string>> {
  const h: Record<string, string> = {
    'Content-Type': 'application/json',
    'ngrok-skip-browser-warning': 'true',
    ...extra,
  };
  if (configManager.apiKey) {
    h['X-API-Key'] = configManager.apiKey;
  }
  return h;
}

async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${configManager.backendUrl}${path}`, {
    headers: await buildHeaders(),
  });
  if (!res.ok) {
    let msg = `GET ${path} → ${res.status}`;
    try {
      const err = await res.json();
      if (err?.detail) msg = String(err.detail);
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${configManager.backendUrl}${path}`, {
    method: 'POST',
    headers: await buildHeaders(),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let msg = `POST ${path} → ${res.status}`;
    try {
      const err = await res.json();
      if (err?.detail) msg = String(err.detail);
      else if (err?.message) msg = String(err.message);
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

async function apiDel<T>(path: string): Promise<T> {
  const res = await fetch(`${configManager.backendUrl}${path}`, {
    method: 'DELETE',
    headers: await buildHeaders(),
  });
  if (!res.ok) throw new Error(`DELETE ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

async function apiCall<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${configManager.backendUrl}${path}`, {
    ...options,
    headers: {
      ...(await buildHeaders()),
      ...(options.headers as Record<string, string>),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string; message?: string }).detail ||
        (body as { message?: string }).message ||
        `API error ${res.status}`
    );
  }
  return res.json() as Promise<T>;
}

// ─────────────────────────────────────────────────────────────────────────────
// Pairing & remote execution
// ─────────────────────────────────────────────────────────────────────────────

export interface CommandResult {
  success: boolean;
  stdout: string;
  stderr: string;
  exit_code: number;
  error?: string;
}

export interface LaptopStatus {
  online: boolean;
  hostname: string;
  platform: string;
  pairingCode: string;
}

export async function checkPairingCode(code: string): Promise<LaptopStatus> {
  await configManager.init();
  const clean = code.replace(/[^a-zA-Z0-9]/g, '').toUpperCase();
  if (clean.length < 4) {
    throw new Error('Enter the pairing code (letters/numbers only), e.g. E69B43');
  }

  if (configManager.isBackendUrlUnsafe && Platform.OS !== 'web') {
    throw new Error(
      'Backend URL is set to localhost — your phone cannot reach your PC. Open Settings → set Server URL to your ngrok HTTPS address (e.g. https://precommercial-nubbly-theda.ngrok-free.dev) with no trailing slash, then try pairing again.'
    );
  }

  try {
    const response = await apiCall<{ success: boolean; agent?: Record<string, unknown>; error?: string }>(
      `/api/v1/ws/agents/${encodeURIComponent(clean)}`
    );
    if (response.success && response.agent) {
      const a = response.agent;
      return {
        online: a.status === 'online',
        hostname: String(a.hostname || 'Unknown'),
        platform: String(a.platform || 'Unknown'),
        pairingCode: clean,
      };
    }
    throw new Error(
      response.error ||
        'No agent registered for this code on the server you reached. Confirm the agent is running and the Server URL matches this machine (same ngrok URL).'
    );
  } catch (e) {
    if (e instanceof Error) {
      const m = e.message;
      if (m.includes('localhost') || m.includes('ngrok')) throw e;
      if (m.includes('API error 401') || m.includes('Missing API key')) {
        throw new Error('Server requires an API key. Add it in Settings (same key as JARVIS_API_KEY on the PC).');
      }
      if (m.includes('Network request failed') || m.includes('Failed to fetch')) {
        throw new Error(
          `Cannot reach server at ${configManager.backendUrl}. Check Wi‑Fi/VPN and that the URL is correct (use https ngrok URL from the PC).`
        );
      }
      if (m.length > 0 && !m.startsWith('Invalid pairing')) throw e;
    }
    throw new Error('Invalid pairing code or laptop not connected');
  }
}

export async function getPairedLaptopStatus(): Promise<LaptopStatus | null> {
  const code = configManager.pairingCode;
  if (!code) return null;
  try {
    return await checkPairingCode(code);
  } catch {
    return null;
  }
}

function normalizeCommandResult(raw: Record<string, unknown>): CommandResult {
  return {
    success: Boolean(raw.success),
    stdout: String(raw.stdout ?? ''),
    stderr: String(raw.stderr ?? ''),
    exit_code: Number(raw.exit_code ?? -1),
    error: raw.error != null ? String(raw.error) : undefined,
  };
}

export async function executeCommand(
  command: string,
  timeout: number = 120
): Promise<CommandResult> {
  const code = configManager.pairingCode;
  if (!code) {
    throw new Error('No laptop paired. Please enter your pairing code first.');
  }
  const raw = await apiCall<Record<string, unknown>>(
    `/api/v1/ws/agents/${encodeURIComponent(code)}/execute`,
    {
      method: 'POST',
      body: JSON.stringify({ command, timeout }),
    }
  );
  return normalizeCommandResult(raw);
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
  platform?: string;
  platform_version?: string;
  hostname?: string;
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

export interface DirectoryListing {
  path: string;
  files: FileInfo[];
  count: number;
  error?: string;
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
  path?: string;
  name: string;
  type: string;
  code_files: number;
  has_git?: boolean;
  has_package_json?: boolean;
  has_requirements?: boolean;
  error?: string;
}

export interface AIProvidersResponse {
  current: string;
  providers: Record<string, { available: boolean; message: string; selected?: boolean }>;
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
// Health
// ─────────────────────────────────────────────────────────────────────────────

export async function checkHealth(): Promise<{
  status: string;
  agent?: string;
  version?: string;
}> {
  return apiGet('/');
}

export async function ping(): Promise<CommandResponse> {
  return apiGet('/commands/ping');
}

// ─────────────────────────────────────────────────────────────────────────────
// System / shell / git / IDE (mobile routes at repo root)
// ─────────────────────────────────────────────────────────────────────────────

export async function runSystemCommand(command: string): Promise<CommandResponse> {
  const result = await executeCommand(command);
  return {
    status: result.success ? 'success' : 'error',
    stdout: result.stdout,
    stderr: result.stderr,
    exit_code: result.exit_code,
    message: result.error,
  };
}

export async function getSystemInfo(): Promise<SystemInfo> {
  try {
    return await apiGet<SystemInfo>('/system/info');
  } catch (error: unknown) {
    return {
      status: 'error',
      platform: 'unknown',
      hostname: 'unknown',
    };
  }
}

export async function runGitCommand(command: string): Promise<CommandResponse> {
  return runSystemCommand(`git ${command}`);
}

export async function openVSCode(): Promise<CommandResponse> {
  return runSystemCommand('code');
}

export async function openProject(path: string): Promise<CommandResponse> {
  return runSystemCommand(`code "${path}"`);
}

export async function openInCursor(path: string): Promise<{ status: string; message: string }> {
  const result = await executeCommand(`cursor "${path}"`);
  return {
    status: result.success ? 'success' : 'error',
    message: result.success ? 'Opened in Cursor' : result.error || 'Failed to open in Cursor',
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Project / files
// ─────────────────────────────────────────────────────────────────────────────

/** When paired, list/read/info run on the laptop that runs the agent (not the API host). */
function pairedAgentFsPrefix(): string | null {
  const code = configManager.pairingCode?.trim();
  if (!code) return null;
  return `/api/v1/ws/agents/${encodeURIComponent(code)}`;
}

export async function listDirectory(
  path: string,
  showHidden = false
): Promise<DirectoryListing> {
  const agentBase = pairedAgentFsPrefix();
  try {
    if (agentBase) {
      return await apiPost<DirectoryListing>(`${agentBase}/fs/list`, {
        path,
        show_hidden: showHidden,
      });
    }
    return await apiPost<DirectoryListing>('/project/list', {
      path,
      show_hidden: showHidden,
    });
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : 'Failed to list directory';
    return { path, files: [], count: 0, error: msg };
  }
}

export async function readFile(path: string, max_lines = 500): Promise<FileContent> {
  const agentBase = pairedAgentFsPrefix();
  try {
    if (agentBase) {
      return await apiPost<FileContent>(`${agentBase}/fs/read`, { path, max_lines });
    }
    return await apiPost<FileContent>('/project/read', { path, max_lines });
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : 'Failed to read file';
    return {
      path,
      content: '',
      lines: 0,
      language: path.includes('.') ? path.split('.').pop() || 'text' : 'text',
      size: 0,
      error: msg,
    };
  }
}

export async function writeFile(
  path: string,
  content: string,
  create_backup = true
): Promise<{ success: boolean; path: string; message: string; backup_path?: string }> {
  const agentBase = pairedAgentFsPrefix();
  try {
    if (agentBase) {
      return await apiPost(`${agentBase}/fs/write`, { path, content, create_backup });
    }
    return await apiPost('/project/write', { path, content, create_backup });
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : 'Failed to write file';
    return { success: false, path, message: msg };
  }
}

export async function getProjectInfo(path: string): Promise<ProjectInfo> {
  const agentBase = pairedAgentFsPrefix();
  try {
    if (agentBase) {
      return await apiPost<ProjectInfo>(`${agentBase}/fs/info`, { path });
    }
    return await apiPost<ProjectInfo>('/project/info', { path });
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : 'Failed to load project info';
    const normalized = path.replace(/\\/g, '/').split('/').filter(Boolean);
    const inferredName = normalized[normalized.length - 1] || path || 'Project';
    return {
      name: inferredName,
      type: 'folder',
      has_git: false,
      code_files: 0,
      error: msg,
    };
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// AI
// ─────────────────────────────────────────────────────────────────────────────

export interface AIResponse {
  status: string;
  response: string;
  error?: string;
}

export async function askAI(
  prompt: string,
  code_context?: string,
  file_path?: string,
  language?: string
): Promise<AIResponse> {
  return apiPost<AIResponse>('/project/ai/ask', {
    prompt,
    code_context,
    file_path,
    language,
  });
}

export async function runCopilot(command: string): Promise<CommandResponse> {
  try {
    const aiResponse = await askAI(command);
    return {
      status: aiResponse.status as 'success' | 'error' | 'info',
      message: aiResponse.response,
    };
  } catch (error: unknown) {
    return {
      status: 'error',
      message: error instanceof Error ? error.message : 'AI request failed',
    };
  }
}

export async function getAIProviders(): Promise<AIProvidersResponse> {
  try {
    return await apiGet<AIProvidersResponse>('/project/ai/providers');
  } catch {
    return {
      current: 'copilot',
      providers: {
        copilot: { available: false, message: 'API connection failed' },
        openai: { available: false, message: 'API connection failed' },
        ollama: { available: false, message: 'API connection failed' },
        cursor: { available: false, message: 'Not available' },
      },
    };
  }
}

export async function setAIProvider(
  provider: string
): Promise<{ success: boolean; provider: string; message: string }> {
  try {
    return await apiPost('/project/ai/set-provider', { provider });
  } catch (error: unknown) {
    return {
      success: false,
      provider,
      message: error instanceof Error ? error.message : 'Failed to set AI provider',
    };
  }
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatResponse {
  session_id: string;
  response: string;
  error?: string;
}

export async function chatWithAgent(
  message: string,
  history: ChatMessage[] = [],
  session_id?: string
): Promise<ChatResponse> {
  return apiPost<ChatResponse>('/api/v1/agent/chat', {
    message,
    history,
    session_id,
  });
}

export interface CodeReviewResult {
  summary: string;
  issues: Array<{
    severity: 'critical' | 'warning' | 'info';
    line?: number;
    message: string;
    suggestion?: string;
  }>;
  score: number;
  error?: string;
}

export async function reviewCode(
  code: string,
  language: string,
  file_path?: string
): Promise<CodeReviewResult> {
  return apiPost<CodeReviewResult>('/api/v1/agent/review', {
    code,
    language,
    file_path,
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Copilot edit / IDE helpers
// ─────────────────────────────────────────────────────────────────────────────

export async function copilotEdit(
  filePath: string,
  instruction: string,
  applyChanges = false
): Promise<CopilotEditResponse> {
  try {
    return await apiPost<CopilotEditResponse>('/copilot/edit', {
      file_path: filePath,
      instruction,
      apply_changes: applyChanges,
    });
  } catch (error: unknown) {
    return {
      success: false,
      original_content: '',
      suggested_content: '',
      diff: '',
      message: error instanceof Error ? error.message : 'Failed to get Copilot edit suggestions',
      applied: false,
    };
  }
}

export async function getCurrentWorkingDirectory(): Promise<string> {
  try {
    const result = await executeCommand('pwd || cd');
    if (result.success && result.stdout.trim()) {
      return result.stdout.trim();
    }
    const homeResult = await executeCommand('echo %USERPROFILE% || echo $HOME');
    if (homeResult.success && homeResult.stdout.trim()) {
      return homeResult.stdout.trim();
    }
  } catch {
    /* ignore */
  }
  return '.';
}

// ─────────────────────────────────────────────────────────────────────────────
// OpenAI / Ollama (env on laptop)
// ─────────────────────────────────────────────────────────────────────────────

export interface OpenAIConfigResponse {
  success: boolean;
  message: string;
  model?: string;
}

export async function setOpenAIConfig(
  apiKey: string,
  model = 'gpt-4o-mini'
): Promise<OpenAIConfigResponse> {
  try {
    const result = await executeCommand(`setx JARVIS_OPENAI_API_KEY "${apiKey}"`);
    if (result.success) {
      return { success: true, message: 'OpenAI API key configured successfully', model };
    }
    return { success: false, message: 'Failed to set OpenAI API key' };
  } catch (error: unknown) {
    return {
      success: false,
      message: error instanceof Error ? error.message : 'Failed to configure OpenAI',
    };
  }
}

export async function getOpenAIStatus(): Promise<OpenAIConfigResponse> {
  try {
    const providers = await getAIProviders();
    const openaiProvider = providers.providers?.openai;
    return {
      success: openaiProvider?.available || false,
      message: openaiProvider?.message || 'OpenAI not configured',
    };
  } catch (error: unknown) {
    return {
      success: false,
      message: error instanceof Error ? error.message : 'Failed to check OpenAI status',
    };
  }
}

export interface OllamaConfigResponse {
  success: boolean;
  message: string;
  host?: string;
  model?: string;
  models?: string[];
}

export async function setOllamaConfig(
  host = 'http://localhost:11434',
  model = 'llama3.2'
): Promise<OllamaConfigResponse> {
  try {
    const hostResult = await executeCommand(`setx JARVIS_OLLAMA_HOST "${host}"`);
    const modelResult = await executeCommand(`setx JARVIS_OLLAMA_MODEL "${model}"`);
    if (hostResult.success && modelResult.success) {
      return { success: true, message: 'Ollama configuration updated successfully', host, model };
    }
    return { success: false, message: 'Failed to set Ollama configuration' };
  } catch (error: unknown) {
    return {
      success: false,
      message: error instanceof Error ? error.message : 'Failed to configure Ollama',
    };
  }
}

export async function getOllamaStatus(): Promise<OllamaConfigResponse> {
  try {
    const providers = await getAIProviders();
    const ollamaProvider = providers.providers?.ollama;
    return {
      success: ollamaProvider?.available || false,
      message: ollamaProvider?.message || 'Ollama not running',
    };
  } catch (error: unknown) {
    return {
      success: false,
      message: error instanceof Error ? error.message : 'Failed to check Ollama status',
    };
  }
}

export async function getOllamaModels(): Promise<string[]> {
  try {
    const result = await executeCommand('ollama list');
    if (result.success) {
      const lines = result.stdout.split('\n').slice(1);
      return lines
        .filter((line) => line.trim())
        .map((line) => line.split(/\s+/)[0])
        .filter((name) => name && !name.includes('NAME'));
    }
    return [];
  } catch {
    return [];
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Copilot CLI status
// ─────────────────────────────────────────────────────────────────────────────

export interface CopilotModelsResponse {
  current: string;
  models: Record<string, string[]>;
}

export interface CopilotStatusResponse {
  authentication: {
    status: 'authenticated' | 'not_authenticated' | 'error';
    message: string;
  };
  copilot: {
    status: 'available' | 'unavailable' | 'error';
    message: string;
  };
  model: {
    current: string;
    available_count: number;
  };
}

export async function getCopilotModels(): Promise<CopilotModelsResponse> {
  try {
    return await apiGet<CopilotModelsResponse>('/copilot/models');
  } catch (error: unknown) {
    return {
      current: 'gpt-5.2-codex',
      models: { Error: [error instanceof Error ? error.message : 'Failed to load models'] },
    };
  }
}

export async function setCopilotModel(
  model: string
): Promise<{ success: boolean; message: string }> {
  try {
    return await apiPost('/copilot/models/set', { model });
  } catch (error: unknown) {
    return {
      success: false,
      message: error instanceof Error ? error.message : 'Failed to set Copilot model',
    };
  }
}

export async function getCopilotStatus(): Promise<CopilotStatusResponse> {
  try {
    return await apiGet<CopilotStatusResponse>('/copilot/status');
  } catch (error: unknown) {
    const m = error instanceof Error ? error.message : 'Error';
    return {
      authentication: { status: 'error', message: m },
      copilot: { status: 'error', message: m },
      model: { current: 'unknown', available_count: 0 },
    };
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// GitHub token (legacy mobile endpoints)
// ─────────────────────────────────────────────────────────────────────────────

export interface GitHubTokenResponse {
  success: boolean;
  message: string;
  username?: string;
}

export async function setGitHubToken(token: string): Promise<GitHubTokenResponse> {
  try {
    return await apiPost<GitHubTokenResponse>('/github/token/set', { token });
  } catch (error: unknown) {
    return {
      success: false,
      message: error instanceof Error ? error.message : 'Failed to set GitHub token',
    };
  }
}

export async function getGitHubTokenStatus(): Promise<GitHubTokenResponse> {
  try {
    return await apiGet<GitHubTokenResponse>('/github/token/status');
  } catch {
    return { success: false, message: 'Failed to check token status' };
  }
}

export async function clearGitHubToken(): Promise<{ success: boolean; message: string }> {
  try {
    return await apiPost('/github/token/clear', {});
  } catch (error: unknown) {
    return {
      success: false,
      message: error instanceof Error ? error.message : 'Failed to clear token',
    };
  }
}

export async function getGitHubAuthStatus(): Promise<GitHubAuthStatus> {
  return apiGet<GitHubAuthStatus>('/github/auth/status');
}

export async function githubLogin(): Promise<{
  success: boolean;
  message: string;
  auth_url?: string;
}> {
  return apiPost('/github/auth/login', {});
}

export async function githubLogout(): Promise<{ success: boolean; message: string }> {
  return apiPost('/github/auth/logout', {});
}

// ─────────────────────────────────────────────────────────────────────────────
// Multi-device management
// ─────────────────────────────────────────────────────────────────────────────

export async function listDevices(): Promise<DeviceInfo[]> {
  return apiGet<DeviceInfo[]>('/devices');
}

export async function registerDevice(
  name: string,
  capabilities?: string[]
): Promise<DeviceWithToken> {
  return apiPost<DeviceWithToken>('/devices', { name, capabilities });
}

export async function deleteDevice(id: string): Promise<{ success: boolean }> {
  return apiDel(`/devices/${id}`);
}

export async function executeOnDevice(
  id: string,
  command: string,
  timeout = 120
): Promise<{
  success: boolean;
  stdout: string;
  stderr: string;
  exit_code: number;
  error?: string;
}> {
  return apiPost(`/devices/${id}/execute`, { command, timeout });
}

export async function getDeviceStatus(id: string): Promise<DeviceInfo> {
  return apiGet<DeviceInfo>(`/devices/${id}`);
}

export async function rotateDeviceToken(id: string): Promise<{ token: string }> {
  return apiPost(`/devices/${id}/rotate-token`, {});
}

// ─────────────────────────────────────────────────────────────────────────────
// Mission control & autonomous (paired laptop)
// ─────────────────────────────────────────────────────────────────────────────

export interface MissionTelemetry {
  cpu_percent?: number;
  memory_percent?: number;
  disk_percent?: number;
  hostname?: string;
  platform?: string;
  top_processes?: Array<{ pid?: number; name?: string; cpu_percent?: number }>;
}

export interface MissionDevice {
  pairing_code: string;
  online: boolean;
  hostname: string | null;
  platform: string | null;
  telemetry: MissionTelemetry | null;
  predictive_hints: string[];
}

export async function getMissionDevice(pairingCode: string): Promise<MissionDevice> {
  const code = pairingCode.trim().toUpperCase();
  return apiGet<MissionDevice>(`/api/v1/mission/device/${encodeURIComponent(code)}`);
}

export interface AutonomousExecuteResult {
  task_id: string;
  status: string;
  message: string;
  plan: Record<string, unknown> | null;
  step_results: Record<string, unknown>[];
  error?: string | null;
  duration_ms: number;
  specialist?: string;
  approval_required?: boolean;
  steps_for_approval?: Record<string, unknown>[];
}

export async function autonomousExecute(
  intent: string,
  options?: {
    approval_mode?: string;
    defer_approval?: boolean;
    use_multi_agent?: boolean;
    specialist?: string;
    capabilities?: string[];
    workspace_root?: string;
  }
): Promise<AutonomousExecuteResult> {
  const code = configManager.pairingCode;
  if (!code) {
    throw new Error('Pair with your laptop in Settings first.');
  }
  const workspace =
    options?.workspace_root?.trim() || configManager.workspaceRoot?.trim() || undefined;
  return apiPost<AutonomousExecuteResult>('/api/v1/autonomous/execute', {
    intent,
    pairing_code: code.trim().toUpperCase(),
    workspace_root: workspace,
    approval_mode: options?.approval_mode ?? 'confirm',
    defer_approval: options?.defer_approval ?? true,
    use_multi_agent: options?.use_multi_agent ?? true,
    specialist: options?.specialist,
    capabilities: options?.capabilities ?? ['shell', 'read_fs', 'write_fs', 'git'],
  });
}

export async function approveAutonomousRun(
  taskId: string,
  approved: boolean
): Promise<AutonomousExecuteResult> {
  const code = configManager.pairingCode;
  if (!code) throw new Error('Pair first');
  return apiPost<AutonomousExecuteResult>(`/api/v1/autonomous/runs/${encodeURIComponent(taskId)}/approve`, {
    approved,
    pairing_code: code.trim().toUpperCase(),
  });
}

export async function getAutonomousRunStatus(taskId: string): Promise<{
  task_id: string;
  status: string;
  pairing_code: string;
  intent_preview: string;
  plan: Record<string, unknown>;
  expires_in_seconds: number;
}> {
  return apiGet(`/api/v1/autonomous/runs/${encodeURIComponent(taskId)}`);
}

export async function mintAutonomousSession(ttlSeconds = 3600): Promise<{
  token: string;
  expires_in_seconds: number;
  pairing_code: string;
}> {
  const code = configManager.pairingCode;
  if (!code) throw new Error('Pair first');
  return apiPost('/api/v1/autonomous/session', {
    pairing_code: code.trim().toUpperCase(),
    ttl_seconds: ttlSeconds,
  });
}
