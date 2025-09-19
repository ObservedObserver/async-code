"""Claude-specific helpers for AI code tasks."""

import json
import os
from typing import Any, Dict, Iterable, List, Tuple

from .common import TaskContext, build_command as build_common_command

CONTAINER_IMAGE = "claude-code-automation:latest"


def get_environment(user_preferences: Dict[str, Any]) -> Dict[str, str]:
    """Return environment variables required for Claude execution."""

    env = {
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
        "ANTHROPIC_NONINTERACTIVE": "1",
    }

    claude_config = user_preferences.get("claudeCode", {})
    if isinstance(claude_config, dict):
        custom_env = claude_config.get("env", {})
        if isinstance(custom_env, dict):
            env.update(custom_env)

    return {key: value for key, value in env.items() if value is not None}


def extract_credentials(
    user_preferences: Dict[str, Any], task_id: int, logger
) -> Tuple[str, str]:
    """Load Claude credentials from user preferences."""

    credentials_content = ""
    escaped_credentials = ""

    claude_config = user_preferences.get("claudeCode", {})
    credentials_json = claude_config.get("credentials") if isinstance(claude_config, dict) else None

    has_credentials = (
        credentials_json is not None
        and credentials_json != {}
        and credentials_json != ""
        and isinstance(credentials_json, dict)
        and len(credentials_json) > 0
    )

    if has_credentials:
        try:
            credentials_content = json.dumps(credentials_json)
            logger.info(
                "📋 Successfully loaded Claude credentials from user preferences and stringified (%s characters) for task %s",
                len(credentials_content),
                task_id,
            )
            escaped_credentials = (
                credentials_content.replace("'", "'\"'\"'").replace("\n", "\\n")
            )
            logger.info("📋 Credentials content escaped for shell injection")
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("❌ Failed to process Claude credentials from user preferences: %s", exc)
            credentials_content = ""
            escaped_credentials = ""
    else:
        logger.info(
            "ℹ️  No meaningful Claude credentials found in user preferences for task %s - skipping credentials setup (credentials: %s)",
            task_id,
            credentials_json,
        )

    return credentials_content, escaped_credentials


def build_pre_model_lines(context: TaskContext) -> List[str]:
    """Shell lines that configure Claude credentials."""

    lines: List[str] = [
        "# Setup Claude credentials for Claude tasks",
        'echo "Setting up Claude credentials..."',
        "",
        "# Create ~/.claude directory if it doesn't exist",
        "mkdir -p ~/.claude",
        "",
    ]

    if context.credentials_content:
        lines.extend(
            [
                "# Write credentials content directly to file",
                'echo "📋 Writing credentials to ~/.claude/.credentials.json"',
                "cat << 'CREDENTIALS_EOF' > ~/.claude/.credentials.json",
                context.credentials_content,
                "CREDENTIALS_EOF",
                'echo "✅ Claude credentials configured"',
            ]
        )
    else:
        lines.append('echo "⚠️  No credentials content available"')

    lines.append("")
    return lines


def build_model_lines(_: TaskContext) -> Iterable[str]:
    """Claude CLI invocation logic."""

    return [
        'echo "Using Claude CLI..."',
        "",
        "# Try different ways to invoke claude",
        'echo "Checking claude installation..."',
        "",
        "if [ -f /usr/local/bin/claude ]; then",
        '    echo "Found claude at /usr/local/bin/claude"',
        '    echo "File type:"',
        '    file /usr/local/bin/claude || echo "file command not available"',
        '    echo "First few lines:"',
        '    head -5 /usr/local/bin/claude || echo "head command failed"',
        "",
        "    # Check if it's a shell script",
        '    if head -1 /usr/local/bin/claude | grep -q "#!/bin/sh\\|#!/bin/bash\\|#!/usr/bin/env bash"; then',
        '        echo "Detected shell script, running with sh..."',
        '        sh /usr/local/bin/claude < /tmp/prompt.txt',
        "    # Check if it's a Node.js script (including env -S node pattern)",
        '    elif head -1 /usr/local/bin/claude | grep -q "#!/usr/bin/env.*node\\|#!/usr/bin/node"; then',
        '        echo "Detected Node.js script..."',
        '        if command -v node >/dev/null 2>&1; then',
        '            echo "Running with node..."',
        "            # Try different approaches for Claude CLI",
        "",
        "            # First try with --help to see available options",
        '            echo "Checking claude options..."',
        '            node /usr/local/bin/claude --help 2>/dev/null || echo "Help not available"',
        "",
        "            # Try non-interactive approaches",
        '            echo "Attempting non-interactive execution..."',
        "",
        "            # Method 1: Use the official --print flag for non-interactive mode",
        '            echo "Using --print flag for non-interactive mode..."',
        '            cat /tmp/prompt.txt | node /usr/local/bin/claude --print --allowedTools "Edit,Bash"',
        '            CLAUDE_EXIT_CODE=$?',
        '            echo "Claude Code finished with exit code: $CLAUDE_EXIT_CODE"',
        "",
        '            if [ $CLAUDE_EXIT_CODE -ne 0 ]; then',
        '                echo "ERROR: Claude Code failed with exit code $CLAUDE_EXIT_CODE"',
        '                exit $CLAUDE_EXIT_CODE',
        "            fi",
        "",
        '            echo "✅ Claude Code completed successfully"',
        "        else",
        '            echo "Node.js not found, trying direct execution..."',
        '            /usr/local/bin/claude < /tmp/prompt.txt',
        '            CLAUDE_EXIT_CODE=$?',
        '            echo "Claude Code finished with exit code: $CLAUDE_EXIT_CODE"',
        '            if [ $CLAUDE_EXIT_CODE -ne 0 ]; then',
        '                echo "ERROR: Claude Code failed with exit code $CLAUDE_EXIT_CODE"',
        '                exit $CLAUDE_EXIT_CODE',
        "            fi",
        '            echo "✅ Claude Code completed successfully"',
        "        fi",
        "    # Check if it's a Python script",
        '    elif head -1 /usr/local/bin/claude | grep -q "#!/usr/bin/env python\\|#!/usr/bin/python"; then',
        '        echo "Detected Python script..."',
        '        if command -v python3 >/dev/null 2>&1; then',
        '            echo "Running with python3..."',
        '            python3 /usr/local/bin/claude < /tmp/prompt.txt',
        '            CLAUDE_EXIT_CODE=$?',
        '        elif command -v python >/dev/null 2>&1; then',
        '            echo "Running with python..."',
        '            python /usr/local/bin/claude < /tmp/prompt.txt',
        '            CLAUDE_EXIT_CODE=$?',
        "        else",
        '            echo "Python not found, trying direct execution..."',
        '            /usr/local/bin/claude < /tmp/prompt.txt',
        '            CLAUDE_EXIT_CODE=$?',
        "        fi",
        '        echo "Claude Code finished with exit code: $CLAUDE_EXIT_CODE"',
        '        if [ $CLAUDE_EXIT_CODE -ne 0 ]; then',
        '            echo "ERROR: Claude Code failed with exit code $CLAUDE_EXIT_CODE"',
        '            exit $CLAUDE_EXIT_CODE',
        "        fi",
        '        echo "✅ Claude Code completed successfully"',
        "    else",
        '        echo "Unknown script type, trying direct execution..."',
        '        /usr/local/bin/claude < /tmp/prompt.txt',
        '        CLAUDE_EXIT_CODE=$?',
        '        echo "Claude Code finished with exit code: $CLAUDE_EXIT_CODE"',
        '        if [ $CLAUDE_EXIT_CODE -ne 0 ]; then',
        '            echo "ERROR: Claude Code failed with exit code $CLAUDE_EXIT_CODE"',
        '            exit $CLAUDE_EXIT_CODE',
        "        fi",
        '        echo "✅ Claude Code completed successfully"',
        "    fi",
        "elif command -v claude >/dev/null 2>&1; then",
        '    echo "Using claude from PATH..."',
        '    CLAUDE_PATH=$(which claude)',
        '    echo "Claude found at: $CLAUDE_PATH"',
        '    claude < /tmp/prompt.txt',
        '    CLAUDE_EXIT_CODE=$?',
        '    echo "Claude Code finished with exit code: $CLAUDE_EXIT_CODE"',
        '    if [ $CLAUDE_EXIT_CODE -ne 0 ]; then',
        '        echo "ERROR: Claude Code failed with exit code $CLAUDE_EXIT_CODE"',
        '        exit $CLAUDE_EXIT_CODE',
        "    fi",
        '    echo "✅ Claude Code completed successfully"',
        "else",
        '    echo "ERROR: claude command not found anywhere"',
        '    echo "Checking available interpreters:"',
        '    which python3 2>/dev/null && echo "python3: available" || echo "python3: not found"',
        '    which python 2>/dev/null && echo "python: available" || echo "python: not found"',
        '    which node 2>/dev/null && echo "node: available" || echo "node: not found"',
        '    which sh 2>/dev/null && echo "sh: available" || echo "sh: not found"',
        "    exit 1",
        "fi",
        "",
    ]


def get_container_overrides() -> Dict[str, Any]:  # pragma: no cover - simple data
    """Return Claude-specific container overrides (none required)."""

    return {}


def build_command(context: TaskContext) -> str:
    """Build the Claude-specific container command."""

    return build_common_command(
        context,
        pre_model_lines=build_pre_model_lines(context),
        model_lines=build_model_lines(context),
    )
