"""Command builder for AI code task containers"""

import json
import logging
import os

logger = logging.getLogger(__name__)


def build_environment_variables(task, user_preferences):
    """Build environment variables for container execution

    Args:
        task: Task dict with agent type
        user_preferences: User preferences dict

    Returns:
        Dict of environment variables
    """
    env_vars = {
        'CI': 'true',
        'TERM': 'dumb',
        'NO_COLOR': '1',
        'FORCE_COLOR': '0',
        'NONINTERACTIVE': '1',
        'DEBIAN_FRONTEND': 'noninteractive',
    }

    model_cli = task.get('agent', 'claude')

    if user_preferences:
        logger.info(f"🔧 Found user preferences for {model_cli}: {list(user_preferences.keys())}")

    if model_cli == 'claude':
        claude_env = {
            'ANTHROPIC_API_KEY': os.getenv('ANTHROPIC_API_KEY'),
            'ANTHROPIC_NONINTERACTIVE': '1'
        }
        claude_config = user_preferences.get('claudeCode', {})
        if claude_config and claude_config.get('env'):
            claude_env.update(claude_config['env'])
        env_vars.update(claude_env)
    elif model_cli == 'codex':
        codex_env = {
            'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
            'OPENAI_NONINTERACTIVE': '1',
            'CODEX_QUIET_MODE': '1',
            'CODEX_UNSAFE_ALLOW_NO_SANDBOX': '1',
            'CODEX_DISABLE_SANDBOX': '1',
            'CODEX_NO_SANDBOX': '1'
        }
        codex_config = user_preferences.get('codex', {})
        if codex_config and codex_config.get('env'):
            codex_env.update(codex_config['env'])
        env_vars.update(codex_env)

    return env_vars


def get_credentials_content(task, user_preferences, task_id):
    """Get Claude credentials content from user preferences

    Args:
        task: Task dict
        user_preferences: User preferences dict
        task_id: Task ID for logging

    Returns:
        Tuple of (credentials_content, escaped_credentials)
    """
    model_cli = task.get('agent', 'claude')
    credentials_content = ""
    escaped_credentials = ""

    if model_cli == 'claude':
        logger.info(f"🔍 Looking for Claude credentials in user preferences for task {task_id}")

        claude_config = user_preferences.get('claudeCode', {})
        credentials_json = claude_config.get('credentials') if claude_config else None

        has_meaningful_credentials = (
            credentials_json is not None and
            credentials_json != {} and
            credentials_json != "" and
            (isinstance(credentials_json, dict) and len(credentials_json) > 0)
        )

        if has_meaningful_credentials:
            try:
                credentials_content = json.dumps(credentials_json)
                logger.info(f"📋 Successfully loaded Claude credentials from user preferences ({len(credentials_content)} characters) for task {task_id}")
                escaped_credentials = credentials_content.replace("'", "'\"'\"'").replace('\n', '\\n')
                logger.info(f"📋 Credentials content escaped for shell injection")
            except Exception as e:
                logger.error(f"❌ Failed to process Claude credentials: {e}")
                credentials_content = ""
                escaped_credentials = ""
        else:
            logger.info(f"ℹ️  No meaningful Claude credentials found for task {task_id}")

    return credentials_content, escaped_credentials


def build_container_command(task, prompt, github_token, credentials_content, escaped_credentials):
    """Build the bash command to run inside the container

    Args:
        task: Task dict with repo info and agent type
        prompt: User prompt text
        github_token: GitHub access token
        credentials_content: Raw credentials content
        escaped_credentials: Shell-escaped credentials

    Returns:
        Command string
    """
    model_cli = task.get('agent', 'claude')
    escaped_prompt = prompt.replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')

    command = f'''
set -e
echo "Setting up repository..."

# Clone repository with authentication
REPO_URL_WITH_TOKEN=$(echo "{task['repo_url']}" | sed "s|https://github.com/|https://{github_token}@github.com/|")
git clone -b {task['target_branch']} "$REPO_URL_WITH_TOKEN" /workspace/repo
cd /workspace/repo

# Configure git
git config user.email "claude-code@automation.com"
git config user.name "Claude Code Automation"

echo "📋 Will extract changes as patch for later PR creation..."
echo "Starting {model_cli.upper()} Code with prompt..."

# Create a temporary file with the prompt
cat << 'PROMPT_EOF' > /tmp/prompt.txt
{prompt}
PROMPT_EOF

# Setup Claude credentials for Claude tasks
if [ "{model_cli}" = "claude" ]; then
    echo "Setting up Claude credentials..."
    mkdir -p ~/.claude

    if [ ! -z "{escaped_credentials}" ]; then
        echo "📋 Writing credentials to ~/.claude/.credentials.json"
        cat << 'CREDENTIALS_EOF' > ~/.claude/.credentials.json
{credentials_content}
CREDENTIALS_EOF
        echo "✅ Claude credentials configured"
    else
        echo "⚠️  No credentials content available"
    fi
fi

# Check which CLI tool to use based on model selection
if [ "{model_cli}" = "codex" ]; then
    echo "Using Codex (OpenAI Codex) CLI..."

    export CODEX_QUIET_MODE=1
    export CODEX_UNSAFE_ALLOW_NO_SANDBOX=1
    export CODEX_DISABLE_SANDBOX=1
    export CODEX_NO_SANDBOX=1

    echo "=== CODEX DEBUG INFO ==="
    echo "CODEX_QUIET_MODE: $CODEX_QUIET_MODE"
    echo "CODEX_UNSAFE_ALLOW_NO_SANDBOX: $CODEX_UNSAFE_ALLOW_NO_SANDBOX"
    echo "OPENAI_API_KEY: $(echo $OPENAI_API_KEY | head -c 8)..."
    echo "======================="

    PROMPT_TEXT=$(cat /tmp/prompt.txt)

    if [ -f /usr/local/bin/codex ]; then
        echo "Found codex at /usr/local/bin/codex"
        /usr/local/bin/codex --approval-mode full-auto --quiet "$PROMPT_TEXT"
        CODEX_EXIT_CODE=$?
        echo "Codex finished with exit code: $CODEX_EXIT_CODE"

        if [ $CODEX_EXIT_CODE -ne 0 ]; then
            echo "ERROR: Codex failed with exit code $CODEX_EXIT_CODE"
            exit $CODEX_EXIT_CODE
        fi
        echo "✅ Codex completed successfully"
    elif command -v codex >/dev/null 2>&1; then
        echo "Using codex from PATH..."
        codex --approval-mode full-auto --quiet "$PROMPT_TEXT"
        CODEX_EXIT_CODE=$?
        echo "Codex finished with exit code: $CODEX_EXIT_CODE"

        if [ $CODEX_EXIT_CODE -ne 0 ]; then
            echo "ERROR: Codex failed with exit code $CODEX_EXIT_CODE"
            exit $CODEX_EXIT_CODE
        fi
        echo "✅ Codex completed successfully"
    else
        echo "ERROR: codex command not found"
        exit 1
    fi
else
    echo "Using Claude CLI..."

    if [ -f /usr/local/bin/claude ]; then
        echo "Found claude at /usr/local/bin/claude"

        if head -1 /usr/local/bin/claude | grep -q "#!/bin/sh\\|#!/bin/bash\\|#!/usr/bin/env bash"; then
            echo "Detected shell script, running with sh..."
            sh /usr/local/bin/claude < /tmp/prompt.txt
        elif head -1 /usr/local/bin/claude | grep -q "#!/usr/bin/env.*node\\|#!/usr/bin/node"; then
            echo "Detected Node.js script..."
            if command -v node >/dev/null 2>&1; then
                echo "Using --print flag for non-interactive mode..."
                cat /tmp/prompt.txt | node /usr/local/bin/claude --print --allowedTools "Edit,Bash"
                CLAUDE_EXIT_CODE=$?
                echo "Claude Code finished with exit code: $CLAUDE_EXIT_CODE"

                if [ $CLAUDE_EXIT_CODE -ne 0 ]; then
                    echo "ERROR: Claude Code failed with exit code $CLAUDE_EXIT_CODE"
                    exit $CLAUDE_EXIT_CODE
                fi
                echo "✅ Claude Code completed successfully"
            else
                /usr/local/bin/claude < /tmp/prompt.txt
            fi
        else
            /usr/local/bin/claude < /tmp/prompt.txt
        fi
    elif command -v claude >/dev/null 2>&1; then
        echo "Using claude from PATH..."
        claude < /tmp/prompt.txt
    else
        echo "ERROR: claude command not found"
        exit 1
    fi
fi

# Check if there are changes
if git diff --quiet; then
    echo "ℹ️  No changes made - this is valid"
    echo "=== PATCH START ==="
    echo "No changes were made"
    echo "=== PATCH END ==="
    echo "=== GIT DIFF START ==="
    echo "No changes were made"
    echo "=== GIT DIFF END ==="
    echo "=== CHANGED FILES START ==="
    echo "No files were changed"
    echo "=== CHANGED FILES END ==="
    echo "=== FILE CHANGES START ==="
    echo "No file changes to display"
    echo "=== FILE CHANGES END ==="
    echo "COMMIT_HASH="
else
    git add .
    git commit -m "{model_cli.capitalize()}: {escaped_prompt[:100]}"

    COMMIT_HASH=$(git rev-parse HEAD)
    echo "COMMIT_HASH=$COMMIT_HASH"

    git format-patch HEAD~1 --stdout > /tmp/changes.patch
    echo "=== PATCH START ==="
    cat /tmp/changes.patch
    echo "=== PATCH END ==="

    echo "=== GIT DIFF START ==="
    git diff HEAD~1 HEAD
    echo "=== GIT DIFF END ==="

    echo "=== CHANGED FILES START ==="
    git diff --name-only HEAD~1 HEAD
    echo "=== CHANGED FILES END ==="

    echo "=== FILE CHANGES START ==="
    for file in $(git diff --name-only HEAD~1 HEAD); do
        echo "FILE: $file"
        echo "=== BEFORE START ==="
        git show HEAD~1:"$file" 2>/dev/null || echo "FILE_NOT_EXISTS"
        echo "=== BEFORE END ==="
        echo "=== AFTER START ==="
        cat "$file" 2>/dev/null || echo "FILE_DELETED"
        echo "=== AFTER END ==="
        echo "=== FILE END ==="
    done
    echo "=== FILE CHANGES END ==="
fi

echo "Container work completed successfully"
exit 0
'''

    return command
