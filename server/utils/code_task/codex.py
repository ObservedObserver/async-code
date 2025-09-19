"""Codex-specific helpers for AI code tasks."""

import fcntl
import os
import random
import time
from typing import Any, Dict, Iterable

from .common import TaskContext, build_command as build_common_command

CONTAINER_IMAGE = "codex-automation:latest"


def get_environment(user_preferences: Dict[str, Any]) -> Dict[str, str]:
    """Return environment variables required for Codex execution."""

    env = {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "OPENAI_NONINTERACTIVE": "1",
        "CODEX_QUIET_MODE": "1",
        "CODEX_UNSAFE_ALLOW_NO_SANDBOX": "1",
        "CODEX_DISABLE_SANDBOX": "1",
        "CODEX_NO_SANDBOX": "1",
    }

    codex_config = user_preferences.get("codex", {})
    if isinstance(codex_config, dict):
        custom_env = codex_config.get("env", {})
        if isinstance(custom_env, dict):
            env.update(custom_env)

    return {key: value for key, value in env.items() if value is not None}


def prepare_for_run(task_id: int, logger) -> None:
    """Mitigate Codex concurrency issues with delays and locking."""

    stagger_delay = random.uniform(0.5, 2.0)
    logger.info("🕐 Adding %.1fs staggered start delay for Codex task %s", stagger_delay, task_id)
    time.sleep(stagger_delay)

    lock_file_path = "/tmp/codex_execution_lock"
    try:
        logger.info("🔒 Acquiring Codex execution lock for task %s", task_id)
        with open(lock_file_path, "w", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            logger.info("✅ Codex execution lock acquired for task %s", task_id)
    except (OSError, BlockingIOError) as exc:  # pylint: disable=broad-except
        logger.warning("⚠️  Could not acquire Codex execution lock for task %s: %s", task_id, exc)
        additional_delay = random.uniform(1.0, 3.0)
        logger.info("🕐 Adding additional %.1fs delay due to lock conflict", additional_delay)
        time.sleep(additional_delay)


def build_model_lines(_: TaskContext) -> Iterable[str]:
    """Codex CLI invocation logic."""

    return [
        'echo "Using Codex (OpenAI Codex) CLI..."',
        "",
        "# Set environment variables for non-interactive mode",
        "export CODEX_QUIET_MODE=1",
        "export CODEX_UNSAFE_ALLOW_NO_SANDBOX=1",
        "export CODEX_DISABLE_SANDBOX=1",
        "export CODEX_NO_SANDBOX=1",
        "",
        "# Debug: Verify environment variables are set",
        'echo "=== CODEX DEBUG INFO ==="',
        'echo "CODEX_QUIET_MODE: $CODEX_QUIET_MODE"',
        'echo "CODEX_UNSAFE_ALLOW_NO_SANDBOX: $CODEX_UNSAFE_ALLOW_NO_SANDBOX"',
        'echo "OPENAI_API_KEY: $(echo $OPENAI_API_KEY | head -c 8)..."',
        'echo "USING OFFICIAL CODEX FLAGS: --approval-mode full-auto --quiet for non-interactive operation"',
        'echo "======================="',
        "",
        "# Read the prompt from file",
        'PROMPT_TEXT=$(cat /tmp/prompt.txt)',
        "",
        "# Check for codex installation",
        'if [ -f /usr/local/bin/codex ]; then',
        '    echo "Found codex at /usr/local/bin/codex"',
        '    echo "Running Codex in non-interactive mode..."',
        "",
        "    # Use official non-interactive flags for Docker environment",
        "    # Using --approval-mode full-auto as per official Codex documentation",
        "    # Also disable Codex's internal sandboxing to prevent conflicts with Docker",
        '    /usr/local/bin/codex --approval-mode full-auto --quiet "$PROMPT_TEXT"',
        '    CODEX_EXIT_CODE=$?',
        '    echo "Codex finished with exit code: $CODEX_EXIT_CODE"',
        "",
        '    if [ $CODEX_EXIT_CODE -ne 0 ]; then',
        '        echo "ERROR: Codex failed with exit code $CODEX_EXIT_CODE"',
        '        exit $CODEX_EXIT_CODE',
        "    fi",
        "",
        '    echo "✅ Codex completed successfully"',
        "elif command -v codex >/dev/null 2>&1; then",
        '    echo "Using codex from PATH..."',
        '    echo "Running Codex in non-interactive mode..."',
        "",
        "    # Use official non-interactive flags for Docker environment",
        "    # Using --approval-mode full-auto as per official Codex documentation",
        "    # Also disable Codex's internal sandboxing to prevent conflicts with Docker",
        '    codex --approval-mode full-auto --quiet "$PROMPT_TEXT"',
        '    CODEX_EXIT_CODE=$?',
        '    echo "Codex finished with exit code: $CODEX_EXIT_CODE"',
        "",
        '    if [ $CODEX_EXIT_CODE -ne 0 ]; then',
        '        echo "ERROR: Codex failed with exit code $CODEX_EXIT_CODE"',
        '        exit $CODEX_EXIT_CODE',
        "    fi",
        "",
        '    echo "✅ Codex completed successfully"',
        "else",
        '    echo "ERROR: codex command not found anywhere"',
        '    echo "Please ensure Codex CLI is installed in the container"',
        "    exit 1",
        "fi",
        "",
    ]


def get_container_overrides() -> Dict[str, Any]:  # pragma: no cover - simple data
    """Return Docker configuration overrides required for Codex."""

    return {
        "security_opt": [
            "seccomp=unconfined",
            "apparmor=unconfined",
            "no-new-privileges=false",
        ],
        "cap_add": ["ALL"],
        "privileged": True,
        "pid_mode": "host",
    }


def build_command(context: TaskContext) -> str:
    """Build the Codex-specific container command."""

    return build_common_command(context, model_lines=build_model_lines(context))
