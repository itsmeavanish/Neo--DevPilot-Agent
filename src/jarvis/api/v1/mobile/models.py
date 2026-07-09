"""
Request/Response Models for Mobile API endpoints.
"""
from typing import Any, Optional
from pydantic import BaseModel, Field

class CommandRequest(BaseModel):
    command: str

class CommandResponse(BaseModel):
    status: str
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    exit_code: Optional[int] = None
    message: Optional[str] = None

class SystemInfo(BaseModel):
    status: str
    platform: str
    platform_version: str
    hostname: str
    cpu_percent: Optional[float] = None
    memory_total_gb: Optional[float] = None
    memory_used_gb: Optional[float] = None
    memory_percent: Optional[float] = None
    disk_total_gb: Optional[float] = None
    disk_used_gb: Optional[float] = None
    disk_percent: Optional[float] = None

class DirectoryRequest(BaseModel):
    path: str
    show_hidden: bool = False

class FileInfo(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: int
    extension: str

class DirectoryListing(BaseModel):
    path: str
    files: list[FileInfo]
    count: int
    error: Optional[str] = None

class FileReadRequest(BaseModel):
    path: str
    max_lines: int = 500

class FileContent(BaseModel):
    path: str
    content: str
    lines: int
    language: str
    size: int
    error: Optional[str] = None

class ProjectInfoRequest(BaseModel):
    path: str

class ProjectInfo(BaseModel):
    path: str
    name: str
    type: str
    code_files: int
    has_git: bool
    has_package_json: bool
    has_requirements: bool
    error: Optional[str] = None

class OpenPathRequest(BaseModel):
    path: str

class SearchRequest(BaseModel):
    query: str
    path: str
    max_results: int = 50
    case_sensitive: bool = False
    file_pattern: Optional[str] = None

class SearchResponse(BaseModel):
    results: list[dict[str, Any]]
    total_matches: int
    error: Optional[str] = None

class AIProviderStatus(BaseModel):
    available: bool
    message: str
    selected: bool

class AIProvidersResponse(BaseModel):
    current: str
    providers: dict

class SetProviderRequest(BaseModel):
    provider: str

class AIAskRequest(BaseModel):
    prompt: str
    code_context: Optional[str] = None
    file_path: Optional[str] = None
    language: Optional[str] = None
    session_id: Optional[str] = None
    workspace_root: Optional[str] = None
    pairing_code: Optional[str] = None

class AIAskStreamRequest(BaseModel):
    prompt: str
    code_context: Optional[str] = None
    file_path: Optional[str] = None
    session_id: Optional[str] = None
    workspace_root: Optional[str] = None
    pairing_code: Optional[str] = None

class AIResponse(BaseModel):
    status: str
    response: str
    error: Optional[str] = None
    session_id: Optional[str] = None

class AgentStreamRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = None
    pairing_code: Optional[str] = None
    workspace_root: Optional[str] = None
    max_steps: int = Field(default=8, ge=1, le=30)

class AIKeysRequest(BaseModel):
    freellm_api_key: Optional[str] = None
    freellm_api_url: Optional[str] = None
    freellm_model: Optional[str] = None

class CopilotModelRequest(BaseModel):
    model: str

class CopilotModelsResponse(BaseModel):
    current: str
    models: dict[str, list[str]]

class OllamaConfigRequest(BaseModel):
    host: Optional[str] = None
    model: Optional[str] = None
    pull: bool = False

class IDEAgentActionRequest(BaseModel):
    intent: str = Field(..., min_length=1, max_length=2000)
    pairing_code: Optional[str] = None
    workspace_root: Optional[str] = None

class IDEAgentActionResponse(BaseModel):
    handled: bool
    success: bool
    message: str
    steps: list[dict[str, Any]] = []
    summary: Optional[str] = None

class GitHubAuthStatus(BaseModel):
    authenticated: bool
    username: Optional[str] = None
    account_type: Optional[str] = None
    scopes: list[str] = []
    message: str
    has_token: bool = False

class GitHubLoginResponse(BaseModel):
    success: bool
    message: str
    auth_url: Optional[str] = None

class GitHubTokenRequest(BaseModel):
    token: str

class GitHubTokenResponse(BaseModel):
    success: bool
    message: str
    username: Optional[str] = None

class FileWriteRequest(BaseModel):
    path: str
    content: str
    create_backup: bool = True

class FileWriteResponse(BaseModel):
    success: bool
    path: str
    message: str
    backup_path: Optional[str] = None

class CopilotEditRequest(BaseModel):
    file_path: str
    instruction: str
    apply_changes: bool = False

class CopilotEditResponse(BaseModel):
    success: bool
    original_content: str
    suggested_content: str
    diff: str
    message: str
    applied: bool = False
