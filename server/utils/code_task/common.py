"""Shared helpers for building AI code task commands."""

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class TaskContext:
    """Context information required to build the container command."""

    task_id: int
    task: Dict[str, Any]
    prompt: str
    github_token: str
    model_cli: str
    credentials_content: str = ""
    escaped_credentials: str = ""

    def __post_init__(self) -> None:
        self.model_cli = (self.model_cli or "claude").lower()
        self.escaped_prompt = (
            self.prompt.replace('"', '\\"')
            .replace("$", "\\$")
            .replace("`", "\\`")
        )

    @property
    def repo_url(self) -> str:
        return self.task.get("repo_url", "")

    @property
    def target_branch(self) -> str:
        return self.task.get("target_branch", "main")

    @property
    def model_upper(self) -> str:
        return self.model_cli.upper()

    @property
    def model_capitalized(self) -> str:
        return self.model_cli.capitalize()

    @property
    def short_escaped_prompt(self) -> str:
        return self.escaped_prompt[:100]


def build_common_setup_lines(context: TaskContext) -> List[str]:
    """Return shell lines that prepare the repository and prompt."""

    return [
        "set -e",
        'echo "Setting up repository..."',
        "",
        "# Clone repository with authentication",
        "# Convert GitHub URL to use token authentication",
        f'REPO_URL_WITH_TOKEN=$(echo "{context.repo_url}" | sed "s|https://github.com/|https://{context.github_token}@github.com/|")',
        f'git clone -b {context.target_branch} "$REPO_URL_WITH_TOKEN" /workspace/repo',
        "cd /workspace/repo",
        "",
        "# Configure git",
        'git config user.email "claude-code@automation.com"',
        'git config user.name "Claude Code Automation"',
        "",
        "# We'll extract the patch instead of pushing directly",
        'echo "📋 Will extract changes as patch for later PR creation..."',
        "",
        f'echo "Starting {context.model_upper} Code with prompt..."',
        "",
        "# Create a temporary file with the prompt using heredoc for proper handling",
        "cat << 'PROMPT_EOF' > /tmp/prompt.txt",
        context.prompt,
        "PROMPT_EOF",
        "",
    ]


def build_finalize_lines(context: TaskContext) -> List[str]:
    """Return shell lines that collect results and diff information."""

    return [
        "# Check if there are changes",
        "if git diff --quiet; then",
        f'    echo "ℹ️  No changes made by {context.model_upper} - this is a valid outcome"',
        '    echo "The AI tool ran successfully but decided not to make changes"',
        "",
        "    # Create empty patch and diff for consistency",
        '    echo "=== PATCH START ==="',
        '    echo "No changes were made"',
        '    echo "=== PATCH END ==="',
        "",
        '    echo "=== GIT DIFF START ==="',
        '    echo "No changes were made"',
        '    echo "=== GIT DIFF END ==="',
        "",
        '    echo "=== CHANGED FILES START ==="',
        '    echo "No files were changed"',
        '    echo "=== CHANGED FILES END ==="',
        "",
        '    echo "=== FILE CHANGES START ==="',
        '    echo "No file changes to display"',
        '    echo "=== FILE CHANGES END ==="',
        "",
        "    # Set empty commit hash",
        '    echo "COMMIT_HASH="',
        "else",
        "    # Commit changes locally",
        "    git add .",
        f'    git commit -m "{context.model_capitalized}: {context.short_escaped_prompt}"',
        "",
        "    # Get commit info",
        '    COMMIT_HASH=$(git rev-parse HEAD)',
        '    echo "COMMIT_HASH=$COMMIT_HASH"',
        "",
        "    # Generate patch file for later application",
        '    echo "📦 Generating patch file..."',
        '    git format-patch HEAD~1 --stdout > /tmp/changes.patch',
        '    echo "=== PATCH START ==="',
        '    cat /tmp/changes.patch',
        '    echo "=== PATCH END ==="',
        "",
        "    # Also get the diff for display",
        '    echo "=== GIT DIFF START ==="',
        '    git diff HEAD~1 HEAD',
        '    echo "=== GIT DIFF END ==="',
        "",
        "    # List changed files for reference",
        '    echo "=== CHANGED FILES START ==="',
        '    git diff --name-only HEAD~1 HEAD',
        '    echo "=== CHANGED FILES END ==="',
        "",
        "    # Get before/after content for merge view",
        '    echo "=== FILE CHANGES START ==="',
        '    for file in $(git diff --name-only HEAD~1 HEAD); do',
        '        echo "FILE: $file"',
        '        echo "=== BEFORE START ==="',
        '        git show HEAD~1:"$file" 2>/dev/null || echo "FILE_NOT_EXISTS"',
        '        echo "=== BEFORE END ==="',
        '        echo "=== AFTER START ==="',
        '        cat "$file" 2>/dev/null || echo "FILE_DELETED"',
        '        echo "=== AFTER END ==="',
        '        echo "=== FILE END ==="',
        "    done",
        '    echo "=== FILE CHANGES END ==="',
        "fi",
        "",
    ]


def build_command(
    context: TaskContext,
    *,
    pre_model_lines: Optional[Iterable[str]] = None,
    model_lines: Iterable[str],
) -> str:
    """Build the full shell command for the container."""

    lines: List[str] = []
    lines.extend(build_common_setup_lines(context))

    if pre_model_lines:
        lines.extend(pre_model_lines)

    lines.extend(model_lines)
    lines.extend(build_finalize_lines(context))
    lines.extend(
        [
            "# Explicitly exit with success code",
            'echo "Container work completed successfully"',
            "exit 0",
        ]
    )
    return "\n".join(lines)
