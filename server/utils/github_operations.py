"""GitHub operations utilities"""

import logging
import time
from github import Github

logger = logging.getLogger(__name__)


def validate_github_token(github_token, repo_url=None):
    """Validate GitHub token and check permissions

    Args:
        github_token: GitHub personal access token
        repo_url: Optional repository URL to check access

    Returns:
        Dict with validation results:
        - user: GitHub username
        - repo: Repository info (if repo_url provided)
        - error: Error message if validation failed

    Raises:
        Exception: If token is invalid or insufficient permissions
    """
    try:
        # Create GitHub client
        g = Github(github_token)

        # Test basic authentication
        user = g.get_user()
        logger.info(f"🔐 Token belongs to user: {user.login}")

        # Test token scopes
        rate_limit = g.get_rate_limit()
        logger.info(f"📊 Rate limit info: {rate_limit.core.remaining}/{rate_limit.core.limit}")

        # If repo URL provided, test repo access
        repo_info = {}
        if repo_url:
            repo_parts = repo_url.replace('https://github.com/', '').replace('.git', '')
            repo = g.get_repo(repo_parts)

            # Test various permissions
            permissions = {
                'read': True,  # If we got here, we can read
                'write': False,
                'admin': False
            }

            try:
                # Test if we can read branches
                branches = list(repo.get_branches())
                permissions['read_branches'] = True
                logger.info(f"✅ Can read branches ({len(branches)} found)")

                # Test if we can create branches
                test_branch_name = f"test-permissions-{int(time.time())}"
                try:
                    main_branch = repo.get_branch(repo.default_branch)
                    test_ref = repo.create_git_ref(f"refs/heads/{test_branch_name}", main_branch.commit.sha)
                    permissions['create_branches'] = True
                    logger.info(f"✅ Can create branches - test successful")

                    # Clean up test branch immediately
                    test_ref.delete()
                    logger.info(f"🧹 Cleaned up test branch")

                except Exception as branch_error:
                    permissions['create_branches'] = False
                    logger.warning(f"❌ Cannot create branches: {branch_error}")

            except Exception as e:
                permissions['read_branches'] = False
                permissions['create_branches'] = False
                logger.warning(f"❌ Cannot read branches: {e}")

            try:
                # Check if we can write (without actually writing)
                repo_perms = repo.permissions
                permissions['write'] = repo_perms.push
                permissions['admin'] = repo_perms.admin
                logger.info(f"📋 Repo permissions: push={repo_perms.push}, admin={repo_perms.admin}")
            except Exception as e:
                logger.warning(f"⚠️ Could not check repo permissions: {e}")

            repo_info = {
                'name': repo.full_name,
                'private': repo.private,
                'permissions': permissions,
                'default_branch': repo.default_branch
            }

        return {
            'status': 'success',
            'user': user.login,
            'repo': repo_info,
            'message': 'Token is valid and has repository access'
        }

    except Exception as e:
        logger.error(f"Token validation error: {str(e)}")
        raise


def create_pull_request_from_patch(task, github_token, pr_title, pr_body, apply_patch_callback):
    """Create a pull request by applying a patch to a fresh repo clone

    Args:
        task: Task dict with repo info and patch data
        github_token: GitHub access token
        pr_title: Pull request title
        pr_body: Pull request body
        apply_patch_callback: Function to apply patch to repo

    Returns:
        Dict with PR info:
        - pr_url: Pull request URL
        - pr_number: Pull request number
        - branch: Branch name
        - files_updated: Number of files updated

    Raises:
        Exception: If PR creation fails
    """
    logger.info(f"🚀 Creating PR for task {task['id']}")

    # Extract repo info from URL
    repo_parts = task['repo_url'].replace('https://github.com/', '').replace('.git', '')

    # Create GitHub client
    g = Github(github_token)
    repo = g.get_repo(repo_parts)

    # Determine branch strategy
    base_branch = task['target_branch']
    pr_branch = f"claude-code-{task['id']}"

    logger.info(f"📋 Creating PR branch '{pr_branch}' from base '{base_branch}'")

    # Get the latest commit from the base branch
    base_branch_obj = repo.get_branch(base_branch)
    base_sha = base_branch_obj.commit.sha

    # Create new branch for the PR
    try:
        # Check if branch already exists
        try:
            existing_branch = repo.get_branch(pr_branch)
            logger.warning(f"⚠️ Branch '{pr_branch}' already exists, deleting it first...")
            repo.get_git_ref(f"heads/{pr_branch}").delete()
            logger.info(f"🗑️ Deleted existing branch '{pr_branch}'")
        except:
            pass  # Branch doesn't exist, which is what we want

        # Create the new branch
        new_ref = repo.create_git_ref(f"refs/heads/{pr_branch}", base_sha)
        logger.info(f"✅ Created branch '{pr_branch}' from {base_sha[:8]}")

    except Exception as branch_error:
        logger.error(f"❌ Failed to create branch '{pr_branch}': {str(branch_error)}")

        # Provide specific error messages based on the error
        error_msg = str(branch_error).lower()
        if "resource not accessible" in error_msg:
            detailed_error = (
                f"GitHub token lacks permission to create branches. "
                f"Please ensure your token has 'repo' scope (not just 'public_repo'). "
                f"Error: {branch_error}"
            )
        elif "already exists" in error_msg:
            detailed_error = f"Branch '{pr_branch}' already exists. Please try again or use a different task."
        else:
            detailed_error = f"Failed to create branch '{pr_branch}': {branch_error}"

        raise Exception(detailed_error)

    # Apply the patch
    logger.info(f"📦 Applying patch with {len(task.get('changed_files', []))} changed files...")
    patch_content = task['git_patch']
    files_updated = apply_patch_callback(repo, pr_branch, patch_content, task)

    if not files_updated:
        raise Exception('Failed to apply patch - no file changes extracted')

    logger.info(f"✅ Applied patch, updated {len(files_updated)} files")

    # Create pull request
    pr = repo.create_pull(
        title=pr_title,
        body=pr_body,
        head=pr_branch,
        base=base_branch
    )

    logger.info(f"🎉 Created PR #{pr.number}: {pr.html_url}")

    return {
        'status': 'success',
        'pr_url': pr.html_url,
        'pr_number': pr.number,
        'branch': pr_branch,
        'files_updated': len(files_updated)
    }
