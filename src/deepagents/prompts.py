"""
Prompt loader for DeepAgents.

This module loads all prompt templates from the prompts/ directory.
Each prompt is stored as a separate .md file for easier maintenance and version control.
"""

import os
from pathlib import Path

# Get the directory where this file is located
_CURRENT_DIR = Path(__file__).parent
_PROMPTS_DIR = _CURRENT_DIR / "prompts"


def _load_prompt(category: str, filename: str) -> str:
    """
    Load a prompt from the prompts directory.

    Args:
        category: Subdirectory name (e.g., 'system_tool', 'system', 'base')
        filename: Name of the prompt file (without .md extension)

    Returns:
        The content of the prompt file as a string
    """
    filepath = _PROMPTS_DIR / category / f"{filename}.md"

    if not filepath.exists():
        raise FileNotFoundError(f"Prompt file not found: {filepath}")

    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


# ============================================================================
# Tool Descriptions (from prompts/system_tool/)
# ============================================================================

WRITE_TODOS_TOOL_DESCRIPTION = _load_prompt("system_tool", "write_todos_tool_description")
TASK_TOOL_DESCRIPTION = _load_prompt("system_tool", "task_tool_description")
LIST_FILES_TOOL_DESCRIPTION = _load_prompt("system_tool", "list_files_tool_description")
READ_FILE_TOOL_DESCRIPTION = _load_prompt("system_tool", "read_file_tool_description")
EDIT_FILE_TOOL_DESCRIPTION = _load_prompt("system_tool", "edit_file_tool_description")
WRITE_FILE_TOOL_DESCRIPTION = _load_prompt("system_tool", "write_file_tool_description")


# ============================================================================
# System Prompts (from prompts/system/)
# ============================================================================

WRITE_TODOS_SYSTEM_PROMPT = _load_prompt("system", "write_todos_system_prompt")
TASK_SYSTEM_PROMPT = _load_prompt("system", "task_system_prompt")
FILESYSTEM_SYSTEM_PROMPT = _load_prompt("system", "filesystem_system_prompt")


# ============================================================================
# Base Prompts (from prompts/base/)
# ============================================================================

BASE_AGENT_PROMPT = _load_prompt("base", "base_agent_prompt")


# ============================================================================
# Exports for backward compatibility
# ============================================================================

__all__ = [
    # Tool descriptions
    "WRITE_TODOS_TOOL_DESCRIPTION",
    "TASK_TOOL_DESCRIPTION",
    "LIST_FILES_TOOL_DESCRIPTION",
    "READ_FILE_TOOL_DESCRIPTION",
    "EDIT_FILE_TOOL_DESCRIPTION",
    "WRITE_FILE_TOOL_DESCRIPTION",
    # System prompts
    "WRITE_TODOS_SYSTEM_PROMPT",
    "TASK_SYSTEM_PROMPT",
    "FILESYSTEM_SYSTEM_PROMPT",
    "BASE_AGENT_PROMPT",
]
