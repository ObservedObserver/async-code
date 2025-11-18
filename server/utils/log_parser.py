"""Log parser for extracting task results from container logs"""

import logging

logger = logging.getLogger(__name__)


def parse_container_logs(logs):
    """Parse container logs to extract task results

    Args:
        logs: Container log string

    Returns:
        Dict with extracted data:
        - commit_hash: Git commit hash
        - git_diff: List of diff lines
        - git_patch: List of patch lines
        - changed_files: List of changed file names
        - file_changes: List of file change dicts
    """
    lines = logs.split('\n')
    commit_hash = None
    git_diff = []
    git_patch = []
    changed_files = []
    file_changes = []

    capturing_diff = False
    capturing_patch = False
    capturing_files = False
    capturing_file_changes = False
    capturing_before = False
    capturing_after = False
    current_file = None
    current_before = []
    current_after = []

    for line in lines:
        if line.startswith('COMMIT_HASH='):
            commit_hash = line.split('=', 1)[1]
            logger.info(f"🔑 Found commit hash: {commit_hash}")
        elif line == '=== PATCH START ===':
            capturing_patch = True
            logger.info(f"📦 Starting to capture git patch...")
        elif line == '=== PATCH END ===':
            capturing_patch = False
            logger.info(f"📦 Finished capturing git patch ({len(git_patch)} lines)")
        elif line == '=== GIT DIFF START ===':
            capturing_diff = True
            logger.info(f"📊 Starting to capture git diff...")
        elif line == '=== GIT DIFF END ===':
            capturing_diff = False
            logger.info(f"📊 Finished capturing git diff ({len(git_diff)} lines)")
        elif line == '=== CHANGED FILES START ===':
            capturing_files = True
            logger.info(f"📁 Starting to capture changed files...")
        elif line == '=== CHANGED FILES END ===':
            capturing_files = False
            logger.info(f"📁 Finished capturing changed files ({len(changed_files)} files)")
        elif line == '=== FILE CHANGES START ===':
            capturing_file_changes = True
            logger.info(f"🔄 Starting to capture file changes...")
        elif line == '=== FILE CHANGES END ===':
            capturing_file_changes = False
            # Add the last file if we were processing one
            if current_file:
                file_changes.append({
                    'filename': current_file,
                    'before': '\n'.join(current_before),
                    'after': '\n'.join(current_after)
                })
            logger.info(f"🔄 Finished capturing file changes ({len(file_changes)} files)")
        elif capturing_file_changes:
            if line.startswith('FILE: '):
                # Save previous file data if exists
                if current_file:
                    file_changes.append({
                        'filename': current_file,
                        'before': '\n'.join(current_before),
                        'after': '\n'.join(current_after)
                    })
                # Start new file
                current_file = line.split('FILE: ', 1)[1]
                current_before = []
                current_after = []
                capturing_before = False
                capturing_after = False
            elif line == '=== BEFORE START ===':
                capturing_before = True
                capturing_after = False
            elif line == '=== BEFORE END ===':
                capturing_before = False
            elif line == '=== AFTER START ===':
                capturing_after = True
                capturing_before = False
            elif line == '=== AFTER END ===':
                capturing_after = False
            elif line == '=== FILE END ===':
                pass
            elif capturing_before:
                current_before.append(line)
            elif capturing_after:
                current_after.append(line)
        elif capturing_patch:
            git_patch.append(line)
        elif capturing_diff:
            git_diff.append(line)
        elif capturing_files:
            if line.strip():
                changed_files.append(line.strip())

    return {
        'commit_hash': commit_hash,
        'git_diff': '\n'.join(git_diff),
        'git_patch': '\n'.join(git_patch),
        'changed_files': changed_files,
        'file_changes': file_changes
    }
