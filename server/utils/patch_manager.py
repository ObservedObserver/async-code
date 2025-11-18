"""Patch and diff management utilities for applying code changes"""

import logging

logger = logging.getLogger(__name__)


def apply_patch_to_github_repo(repo, branch, patch_content, task):
    """Apply a git patch to a GitHub repository using the GitHub API

    Args:
        repo: PyGithub repository object
        branch: Branch name to apply patch to
        patch_content: Git patch content
        task: Task dict with prompt and metadata

    Returns:
        List of updated file paths
    """
    try:
        logger.info(f"🔧 Parsing patch content...")

        # Parse git patch format to extract file changes
        files_to_update = {}
        lines = patch_content.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i]

            # Look for file headers in patch format
            if line.startswith('--- a/') or line.startswith('--- /dev/null'):
                # Next line should be +++ b/filename
                if i + 1 < len(lines) and lines[i + 1].startswith('+++ b/'):
                    current_file = lines[i + 1][6:]  # Remove '+++ b/'
                    logger.info(f"📄 Found file change: {current_file}")

                    # Get the original file content if it exists
                    try:
                        file_obj = repo.get_contents(current_file, ref=branch)
                        original_content = file_obj.decoded_content.decode('utf-8')
                        logger.info(f"📥 Got original content for {current_file}")
                    except:
                        original_content = ""  # New file
                        logger.info(f"📝 New file: {current_file}")

                    # Skip to the actual diff content (after @@)
                    j = i + 2
                    while j < len(lines) and not lines[j].startswith('@@'):
                        j += 1

                    if j < len(lines):
                        # Apply the diff changes
                        new_content = apply_diff_to_content(original_content, lines[j:], current_file)
                        if new_content is not None:
                            files_to_update[current_file] = new_content
                            logger.info(f"✅ Prepared update for {current_file}")

                    i = j
            i += 1

        # Create a single commit with all file changes using GitHub's Tree API
        if not files_to_update:
            logger.warning("⚠️ No files to update")
            return []

        updated_files = []
        commit_message = _build_commit_message(task)

        try:
            # Use tree-based commit creation for efficiency
            updated_files = _create_tree_based_commit(repo, branch, files_to_update, commit_message)
        except Exception as commit_error:
            logger.error(f"❌ Failed to create single commit: {commit_error}")
            # Fallback to individual file updates if tree method fails
            logger.info("🔄 Falling back to individual file updates...")
            updated_files = _update_files_individually(repo, branch, files_to_update, commit_message)

        return updated_files

    except Exception as e:
        logger.error(f"💥 Error applying patch: {str(e)}")
        return []


def apply_diff_to_content(original_content, diff_lines, filename):
    """Apply diff changes to original content - simplified implementation

    Args:
        original_content: Original file content
        diff_lines: Lines from the diff
        filename: Filename for logging

    Returns:
        Updated content string or None on error
    """
    try:
        result_lines = []
        original_lines = original_content.split('\n') if original_content else []

        # Find the actual diff content starting from @@ line
        diff_start = 0
        for i, line in enumerate(diff_lines):
            if line.startswith('@@'):
                diff_start = i + 1
                break

        # Simple reconstruction: take context and + lines, skip - lines
        for line in diff_lines[diff_start:]:
            if line.startswith('+++') or line.startswith('---'):
                continue
            elif line.startswith('+') and not line.startswith('+++'):
                result_lines.append(line[1:])  # Remove the +
            elif line.startswith(' '):  # Context line
                result_lines.append(line[1:])  # Remove the space
            elif line.startswith('-'):
                continue  # Skip removed lines
            elif line.strip() == '':
                continue  # Skip empty lines in diff
            else:
                # Check if we've reached the next file
                if line.startswith('diff --git') or line.startswith('--- a/'):
                    break

        # If we got content, return it, otherwise fall back to original
        if result_lines:
            return '\n'.join(result_lines)
        else:
            logger.warning(f"⚠️ Could not parse diff for {filename}, keeping original")
            return original_content

    except Exception as e:
        logger.error(f"❌ Error applying diff to {filename}: {str(e)}")
        return None


def _build_commit_message(task):
    """Build commit message from task"""
    # Get prompt from chat messages if available
    if task.get('chat_messages'):
        for msg in task['chat_messages']:
            if msg.get('role') == 'user':
                return f"Claude Code: {msg.get('content', '')[:100]}"
    return f"Claude Code: {task.get('prompt', 'Automated changes')[:100]}"


def _create_tree_based_commit(repo, branch, files_to_update, commit_message):
    """Create a single commit with all changes using GitHub's Tree API

    Args:
        repo: PyGithub repository object
        branch: Branch name
        files_to_update: Dict of {file_path: new_content}
        commit_message: Commit message

    Returns:
        List of updated file paths
    """
    updated_files = []

    # Get the current commit to build upon
    current_commit = repo.get_commit(branch)

    # Create tree elements for all changed files
    tree_elements = []

    for file_path, new_content in files_to_update.items():
        # Create a blob for the file content
        blob = repo.create_git_blob(new_content, "utf-8")

        # Add to tree elements
        tree_elements.append({
            "path": file_path,
            "mode": "100644",  # Normal file mode
            "type": "blob",
            "sha": blob.sha
        })

        logger.info(f"📝 Prepared blob for {file_path}")
        updated_files.append(file_path)

    # Create a new tree with all the changes
    new_tree = repo.create_git_tree(tree_elements, base_tree=current_commit.commit.tree)

    # Create a single commit with all the changes
    new_commit = repo.create_git_commit(
        message=commit_message,
        tree=new_tree,
        parents=[current_commit.commit]
    )

    # Update the branch to point to the new commit
    ref = repo.get_git_ref(f"heads/{branch}")
    ref.edit(new_commit.sha)

    logger.info(f"✅ Created single commit {new_commit.sha[:8]} with {len(updated_files)} files")

    return updated_files


def _update_files_individually(repo, branch, files_to_update, commit_message):
    """Fallback: Update files individually if tree-based commit fails

    Args:
        repo: PyGithub repository object
        branch: Branch name
        files_to_update: Dict of {file_path: new_content}
        commit_message: Commit message

    Returns:
        List of updated file paths
    """
    updated_files = []

    for file_path, new_content in files_to_update.items():
        try:
            # Check if file exists
            try:
                file_obj = repo.get_contents(file_path, ref=branch)
                # Update existing file
                repo.update_file(
                    path=file_path,
                    message=commit_message,
                    content=new_content,
                    sha=file_obj.sha,
                    branch=branch
                )
                logger.info(f"📝 Updated existing file: {file_path}")
            except:
                # Create new file
                repo.create_file(
                    path=file_path,
                    message=commit_message,
                    content=new_content,
                    branch=branch
                )
                logger.info(f"🆕 Created new file: {file_path}")

            updated_files.append(file_path)

        except Exception as file_error:
            logger.error(f"❌ Failed to update {file_path}: {file_error}")

    return updated_files
