// ==============================================
// JARVIS API Client
// Single app for single laptop - pairing code based
// ==============================================

import configManager, { DEFAULT_NGROK_URL } from './config';

// Update API config from configManager
export function updateApiConfig() {
  // Config is managed by configManager
}

// Get current API URL (for display)
export function getApiUrl(): string {
  return configManager.backendUrl || DEFAULT_NGROK_URL;
}

export interface CommandResponse {
  status: 'success' | 'error' | 'info';
  stdout?: string;
  stderr?: string;
  exit_code?: number;
  message?: string;
}

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

async function apiCall<T>(path: string, options: RequestInit = {}): Promise<T> {
  const baseUrl = configManager.backendUrl || DEFAULT_NGROK_URL;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'ngrok-skip-browser-warning': 'true',
    ...(options.headers as Record<string, string>),
  };

  const res = await fetch(`${baseUrl}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || body.message || `API error ${res.status}`);
  }

  return res.json();
}

// ============ Pairing & Laptop Access ============

// Check if the pairing code is valid and laptop is online
export async function checkPairingCode(code: string): Promise<LaptopStatus> {
  try {
    const response = await apiCall<{ success: boolean; agent: any }>(`/api/v1/ws/agents/${code}`);
    if (response.success && response.agent) {
      return {
        online: response.agent.status === 'online',
        hostname: response.agent.hostname || 'Unknown',
        platform: response.agent.platform || 'Unknown',
        pairingCode: code,
      };
    }
    throw new Error('Laptop not found');
  } catch (error) {
    throw new Error('Invalid pairing code or laptop not connected');
  }
}

// Get paired laptop status
export async function getPairedLaptopStatus(): Promise<LaptopStatus | null> {
  const code = configManager.pairingCode;
  if (!code) return null;

  try {
    return await checkPairingCode(code);
  } catch {
    return null;
  }
}

// Execute command on paired laptop
export async function executeCommand(command: string, timeout: number = 120): Promise<CommandResult> {
  const code = configManager.pairingCode;
  if (!code) {
    throw new Error('No laptop paired. Please enter your pairing code first.');
  }

  return apiCall(`/api/v1/ws/agents/${code}/execute`, {
    method: 'POST',
    body: JSON.stringify({ command, timeout }),
  });
}

// ============ Health Check ============

export async function checkHealth(): Promise<{ status: string; agent: string; version: string }> {
  return apiCall('/');
}

// ============ AI Chat ============

export interface AIResponse {
  status: string;
  response: string;
  error?: string;
}

export interface AIProvidersResponse {
  current: string;
  providers: Record<string, { available: boolean; message: string }>;
}

export async function askAI(
  prompt: string,
  codeContext?: string,
  filePath?: string,
  language?: string
): Promise<AIResponse> {
  return apiCall('/project/ai/ask', {
    method: 'POST',
    body: JSON.stringify({
      prompt,
      code_context: codeContext,
      file_path: filePath,
      language,
    }),
  });
}

// Legacy Copilot function (for compatibility)
export async function runCopilot(prompt: string): Promise<CommandResponse> {
  try {
    const aiResponse = await askAI(prompt);
    return {
      status: aiResponse.status as 'success' | 'error' | 'info',
      message: aiResponse.response,
    };
  } catch (error: any) {
    return {
      status: 'error',
      message: error.message || 'AI request failed',
    };
  }
}

// AI Providers - Real implementation
export async function getAIProviders(): Promise<AIProvidersResponse> {
  try {
    return await apiCall<AIProvidersResponse>('/project/ai/providers');
  } catch (error: any) {
    // Fallback if API is not available
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

export async function setAIProvider(provider: string): Promise<{ success: boolean; message: string }> {
  try {
    return await apiCall('/project/ai/set-provider', {
      method: 'POST',
      body: JSON.stringify({ provider }),
    });
  } catch (error: any) {
    return {
      success: false,
      message: error.message || 'Failed to set AI provider',
    };
  }
}

// ============ System Commands ============

export async function runSystemCommand(command: string): Promise<CommandResponse> {
  // Use the paired laptop to run commands
  const result = await executeCommand(command);
  return {
    status: result.success ? 'success' : 'error',
    stdout: result.stdout,
    stderr: result.stderr,
    exit_code: result.exit_code,
    message: result.error,
  };
}

// ============ VS Code & IDE Commands ============

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

// ============ Git Commands ============

export async function runGitCommand(command: string): Promise<CommandResponse> {
  return runSystemCommand(`git ${command}`);
}

// ============ File System ============

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
  name: string;
  type: string;
  has_git: boolean;
  code_files: number;
  error?: string;
}

export async function listDirectory(path: string, showHidden = false): Promise<DirectoryListing> {
  // Use the mobile API endpoint that handles platform detection server-side
  try {
    return await apiCall('/project/list', {
      method: 'POST',
      body: JSON.stringify({ path, show_hidden: showHidden }),
    });
  } catch (error: any) {
    return {
      path,
      files: [],
      count: 0,
      error: error.message || 'Failed to list directory',
    };
  }
}

export async function readFile(path: string, maxLines = 500): Promise<FileContent> {
  // Use the mobile API endpoint that handles platform detection server-side
  try {
    return await apiCall('/project/read', {
      method: 'POST',
      body: JSON.stringify({ path, max_lines: maxLines }),
    });
  } catch (error: any) {
    return {
      path,
      content: '',
      lines: 0,
      language: path.includes('.') ? path.split('.').pop() || 'text' : 'text',
      size: 0,
      error: error.message || 'Failed to read file',
    };
  }
}

export async function getProjectInfo(path: string): Promise<ProjectInfo> {
  try {
    return await apiCall<ProjectInfo>('/project/info', {
      method: 'POST',
      body: JSON.stringify({ path }),
    });
  } catch (error: any) {
    const normalized = path.replace(/\\/g, '/').split('/').filter(Boolean);
    const inferredName = normalized[normalized.length - 1] || path || 'Project';
    return {
      name: inferredName,
      type: 'folder',
      has_git: false,
      code_files: 0,
      error: error.message || 'Failed to load project info',
    };
  }
}

// ============ File Write API ============

export interface FileWriteResponse {
  success: boolean;
  path: string;
  message: string;
  backup_path?: string;
}

export async function writeFile(path: string, content: string, createBackup = true): Promise<FileWriteResponse> {
  // Use the mobile API endpoint that handles platform detection server-side
  try {
    return await apiCall('/project/write', {
      method: 'POST',
      body: JSON.stringify({ path, content, create_backup: createBackup }),
    });
  } catch (error: any) {
    return {
      success: false,
      path,
      message: error.message || 'Failed to write file',
    };
  }
}

// ============ Copilot Edit API ============

export interface CopilotEditResponse {
  success: boolean;
  original_content: string;
  suggested_content: string;
  diff: string;
  message: string;
  applied: boolean;
}

export async function copilotEdit(
  filePath: string,
  instruction: string,
  applyChanges = false
): Promise<CopilotEditResponse> {
  try {
    return await apiCall('/copilot/edit', {
      method: 'POST',
      body: JSON.stringify({
        file_path: filePath,
        instruction,
        apply_changes: applyChanges,
      }),
    });
  } catch (error: any) {
    return {
      success: false,
      original_content: '',
      suggested_content: '',
      diff: '',
      message: error.message || 'Failed to get Copilot edit suggestions',
      applied: false,
    };
  }
}

export async function getCurrentWorkingDirectory(): Promise<string> {
  // Get the current working directory from the connected laptop
  try {
    const result = await executeCommand('pwd || cd');
    if (result.success && result.stdout.trim()) {
      return result.stdout.trim();
    }
    // Fallback - try to get user home directory
    const homeResult = await executeCommand('echo %USERPROFILE% || echo $HOME');
    if (homeResult.success && homeResult.stdout.trim()) {
      return homeResult.stdout.trim();
    }
  } catch (error) {
    console.warn('Failed to get working directory:', error);
  }

  // Last resort fallback
  return '.';
}

// ============ System Info ============

export interface SystemInfo {
  status: string;
  platform?: string;
  hostname?: string;
  cpu_percent?: number;
  memory_percent?: number;
  memory_used_gb?: number;
  memory_total_gb?: number;
  disk_percent?: number;
  disk_used_gb?: number;
  disk_total_gb?: number;
}

export async function getSystemInfo(): Promise<SystemInfo> {
  // Use the mobile API endpoint to get system info from the connected laptop
  try {
    return await apiCall('/system/info');
  } catch (error: any) {
    return {
      status: 'error',
      platform: 'unknown',
      hostname: 'unknown',
    };
  }
}

// ============ OpenAI API Management ============

export interface OpenAIConfigResponse {
  success: boolean;
  message: string;
  model?: string;
}

export async function setOpenAIConfig(apiKey: string, model = 'gpt-4o-mini'): Promise<OpenAIConfigResponse> {
  try {
    // Note: In a real implementation, this should be handled securely server-side
    // For now, we'll use environment variables or config files on the laptop
    const result = await executeCommand(`setx JARVIS_OPENAI_API_KEY "${apiKey}"`);
    if (result.success) {
      return {
        success: true,
        message: 'OpenAI API key configured successfully',
        model,
      };
    } else {
      return {
        success: false,
        message: 'Failed to set OpenAI API key',
      };
    }
  } catch (error: any) {
    return {
      success: false,
      message: error.message || 'Failed to configure OpenAI',
    };
  }
}

export async function getOpenAIStatus(): Promise<OpenAIConfigResponse> {
  try {
    // Check if OpenAI is configured by testing a simple API call
    const providers = await getAIProviders();
    const openaiProvider = providers.providers?.openai;

    return {
      success: openaiProvider?.available || false,
      message: openaiProvider?.message || 'OpenAI not configured',
    };
  } catch (error: any) {
    return {
      success: false,
      message: 'Failed to check OpenAI status',
    };
  }
}

// ============ Ollama Configuration ============

export interface OllamaConfigResponse {
  success: boolean;
  message: string;
  host?: string;
  model?: string;
  models?: string[];
}

export async function setOllamaConfig(host = 'http://localhost:11434', model = 'llama3.2'): Promise<OllamaConfigResponse> {
  try {
    // Configure Ollama host and model
    const hostResult = await executeCommand(`setx JARVIS_OLLAMA_HOST "${host}"`);
    const modelResult = await executeCommand(`setx JARVIS_OLLAMA_MODEL "${model}"`);

    if (hostResult.success && modelResult.success) {
      return {
        success: true,
        message: 'Ollama configuration updated successfully',
        host,
        model,
      };
    } else {
      return {
        success: false,
        message: 'Failed to set Ollama configuration',
      };
    }
  } catch (error: any) {
    return {
      success: false,
      message: error.message || 'Failed to configure Ollama',
    };
  }
}

export async function getOllamaStatus(): Promise<OllamaConfigResponse> {
  try {
    // Check if Ollama is running and get available models
    const providers = await getAIProviders();
    const ollamaProvider = providers.providers?.ollama;

    return {
      success: ollamaProvider?.available || false,
      message: ollamaProvider?.message || 'Ollama not running',
    };
  } catch (error: any) {
    return {
      success: false,
      message: 'Failed to check Ollama status',
    };
  }
}

export async function getOllamaModels(): Promise<string[]> {
  try {
    // Try to get list of available Ollama models
    const result = await executeCommand('ollama list');
    if (result.success) {
      const lines = result.stdout.split('\n').slice(1); // Skip header
      return lines
        .filter(line => line.trim())
        .map(line => line.split(/\s+/)[0]) // Get model name (first column)
        .filter(name => name && !name.includes('NAME')); // Filter out header artifacts
    }
    return [];
  } catch (error) {
    return [];
  }
}

// ============ GitHub Copilot CLI API (No tokens required!) ============

export interface CopilotModelsResponse {
  current: string;
  models: Record<string, string[]>; // Category -> list of models
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

// Get available Copilot models
export async function getCopilotModels(): Promise<CopilotModelsResponse> {
  try {
    return await apiCall('/copilot/models');
  } catch (error: any) {
    return {
      current: 'gpt-5.2-codex',
      models: {
        'Error': [`Failed to load models: ${error.message}`]
      }
    };
  }
}

// Set Copilot model
export async function setCopilotModel(model: string): Promise<{ success: boolean; message: string }> {
  try {
    return await apiCall('/copilot/models/set', {
      method: 'POST',
      body: JSON.stringify({ model }),
    });
  } catch (error: any) {
    return {
      success: false,
      message: error.message || 'Failed to set Copilot model',
    };
  }
}

// Get detailed Copilot status
export async function getCopilotStatus(): Promise<CopilotStatusResponse> {
  try {
    return await apiCall('/copilot/status');
  } catch (error: any) {
    return {
      authentication: { status: 'error', message: `Error: ${error.message}` },
      copilot: { status: 'error', message: `Error: ${error.message}` },
      model: { current: 'unknown', available_count: 0 }
    };
  }
}

// ============ GitHub Token API (Legacy - kept for compatibility) ============

export interface GitHubTokenResponse {
  success: boolean;
  message: string;
  username?: string;
}

export async function setGitHubToken(token: string): Promise<GitHubTokenResponse> {
  try {
    return await apiCall('/github/token/set', {
      method: 'POST',
      body: JSON.stringify({ token }),
    });
  } catch (error: any) {
    return {
      success: false,
      message: error.message || 'Failed to set GitHub token',
    };
  }
}

export async function getGitHubTokenStatus(): Promise<GitHubTokenResponse> {
  try {
    return await apiCall('/github/token/status');
  } catch (error: any) {
    return {
      success: false,
      message: 'Failed to check token status',
    };
  }
}

export async function clearGitHubToken(): Promise<{ success: boolean; message: string }> {
  try {
    return await apiCall('/github/token/clear', {
      method: 'POST',
    });
  } catch (error: any) {
    return {
      success: false,
      message: error.message || 'Failed to clear token',
    };
  }
}