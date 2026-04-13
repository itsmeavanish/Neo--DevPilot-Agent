"""Built-in tools for JARVIS."""

# Import all tools to trigger registration
from jarvis.tools.builtin.shell import RunCommandTool
from jarvis.tools.builtin.file import ReadFileTool, WriteFileTool, ListDirectoryTool
from jarvis.tools.builtin.git import GitTool
from jarvis.tools.builtin.vscode import VSCodeTool
from jarvis.tools.builtin.docker import DockerTool
from jarvis.tools.builtin.process import ProcessTool
from jarvis.tools.builtin.log import LogReaderTool
from jarvis.tools.builtin.system import SystemInfoTool
from jarvis.tools.builtin.ai_tools import CodeReviewTool, GenerateCodeTool, ExplainCommandTool

__all__ = [
    "RunCommandTool",
    "ReadFileTool",
    "WriteFileTool",
    "ListDirectoryTool",
    "GitTool",
    "VSCodeTool",
    "DockerTool",
    "ProcessTool",
    "LogReaderTool",
    "SystemInfoTool",
    "CodeReviewTool",
    "GenerateCodeTool",
    "ExplainCommandTool",
]
