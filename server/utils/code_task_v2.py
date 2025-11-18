"""Main orchestrator for AI code tasks (Claude and Codex)"""

import logging
import time
import random
import fcntl
from datetime import datetime
from database import DatabaseOperations
from .container_manager import (
    cleanup_orphaned_containers,
    create_container,
    wait_for_container,
    cleanup_container
)
from .command_builder import (
    build_environment_variables,
    get_credentials_content,
    build_container_command
)
from .log_parser import parse_container_logs

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_ai_code_task_v2(task_id: int, user_id: str, github_token: str):
    """Run AI Code automation (Claude or Codex) in a container - Supabase version"""
    try:
        # Get task from database to check the model type
        task = DatabaseOperations.get_task_by_id(task_id, user_id)
        if not task:
            logger.error(f"Task {task_id} not found in database")
            return

        model_cli = task.get('agent', 'claude')
        logger.info(f"🚀 Running {model_cli.upper()} task {task_id} directly in parallel mode")
        return _run_ai_code_task_v2_internal(task_id, user_id, github_token)

    except Exception as e:
        logger.error(f"💥 Exception in run_ai_code_task_v2: {str(e)}")
        try:
            DatabaseOperations.update_task(task_id, user_id, {
                'status': 'failed',
                'error': str(e)
            })
        except:
            logger.error(f"Failed to update task {task_id} status after exception")


def _run_ai_code_task_v2_internal(task_id: int, user_id: str, github_token: str):
    """Internal implementation of AI Code automation"""
    try:
        # Clean up any orphaned containers before starting new task
        cleanup_orphaned_containers()

        # Get task from database
        task = DatabaseOperations.get_task_by_id(task_id, user_id)
        if not task:
            logger.error(f"Task {task_id} not found in database")
            return

        # Update task status to running
        DatabaseOperations.update_task(task_id, user_id, {'status': 'running'})

        model_name = task.get('agent', 'claude').upper()
        logger.info(f"🚀 Starting {model_name} Code task {task_id}")

        # Get prompt from chat messages
        prompt = _extract_prompt_from_task(task)
        if not prompt:
            _fail_task(task_id, user_id, "No user prompt found in chat messages")
            return

        logger.info(f"📋 Task details: prompt='{prompt[:50]}...', repo={task['repo_url']}, branch={task['target_branch']}, model={model_name}")

        # Get user preferences
        user = DatabaseOperations.get_user_by_id(user_id)
        user_preferences = user.get('preferences', {}) if user else {}

        # Build environment variables
        env_vars = build_environment_variables(task, user_preferences)

        # Get credentials
        credentials_content, escaped_credentials = get_credentials_content(task, user_preferences, task_id)

        # Build container command
        container_command = build_container_command(task, prompt, github_token, credentials_content, escaped_credentials)

        # Determine container image
        model_cli = task.get('agent', 'claude')
        container_image = 'codex-automation:latest' if model_cli == 'codex' else 'claude-code-automation:latest'

        # Add staggered start for Codex to prevent race conditions
        if model_cli == 'codex':
            _handle_codex_startup(task_id)

        # Create container
        logger.info(f"🐳 Creating Docker container for task {task_id} using {container_image} (model: {model_name})")
        container = create_container(task_id, container_image, container_command, env_vars, model_cli)

        if not container:
            _fail_task(task_id, user_id, "Failed to create container")
            return

        # Update task with container ID
        DatabaseOperations.update_task(task_id, user_id, {'container_id': container.id})

        logger.info(f"⏳ Waiting for container to complete (timeout: 300s)...")

        # Wait for container to finish
        try:
            result, logs = wait_for_container(container, timeout=300)
            cleanup_container(container)

            # Process results
            if result['StatusCode'] == 0:
                _handle_success(task_id, user_id, logs, model_name, task)
            else:
                _fail_task(task_id, user_id, f"Container exited with code {result['StatusCode']}: {logs}")

        except Exception as e:
            logger.error(f"⏰ Container error: {str(e)}")
            _fail_task(task_id, user_id, str(e))
            cleanup_container(container)
            return

    except Exception as e:
        model_name = task.get('agent', 'claude').upper() if task else 'UNKNOWN'
        logger.error(f"💥 Unexpected exception in {model_name} task {task_id}: {str(e)}")
        _fail_task(task_id, user_id, str(e))


def _extract_prompt_from_task(task):
    """Extract user prompt from task chat messages"""
    if task.get('chat_messages'):
        for msg in task['chat_messages']:
            if msg.get('role') == 'user':
                return msg.get('content', '')
    return ""


def _handle_codex_startup(task_id):
    """Handle Codex-specific startup delays and locking"""
    stagger_delay = random.uniform(0.5, 2.0)
    logger.info(f"🕐 Adding {stagger_delay:.1f}s staggered start delay for Codex task {task_id}")
    time.sleep(stagger_delay)

    # Add file-based locking for Codex
    lock_file_path = '/tmp/codex_execution_lock'
    try:
        logger.info(f"🔒 Acquiring Codex execution lock for task {task_id}")
        with open(lock_file_path, 'w') as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            logger.info(f"✅ Codex execution lock acquired for task {task_id}")
    except (IOError, OSError) as e:
        logger.warning(f"⚠️  Could not acquire Codex execution lock for task {task_id}: {e}")
        additional_delay = random.uniform(1.0, 3.0)
        logger.info(f"🕐 Adding additional {additional_delay:.1f}s delay due to lock conflict")
        time.sleep(additional_delay)


def _handle_success(task_id, user_id, logs, model_name, task):
    """Handle successful task completion"""
    logger.info(f"✅ Container exited successfully (code 0) - parsing results...")

    # Parse logs to extract results
    parsed_data = parse_container_logs(logs)

    logger.info(f"🔄 Updating task status to COMPLETED...")

    # Update task in database
    DatabaseOperations.update_task(task_id, user_id, {
        'status': 'completed',
        'commit_hash': parsed_data['commit_hash'],
        'git_diff': parsed_data['git_diff'],
        'git_patch': parsed_data['git_patch'],
        'changed_files': parsed_data['changed_files'],
        'execution_metadata': {
            'file_changes': parsed_data['file_changes'],
            'completed_at': datetime.now().isoformat()
        }
    })

    commit_hash = parsed_data['commit_hash']
    logger.info(f"🎉 {model_name} Task {task_id} completed successfully! Commit: {commit_hash[:8] if commit_hash else 'N/A'}")


def _fail_task(task_id, user_id, error_message):
    """Mark task as failed with error message"""
    logger.error(f"❌ Task {task_id} failed: {error_message[:200]}...")
    try:
        DatabaseOperations.update_task(task_id, user_id, {
            'status': 'failed',
            'error': error_message
        })
    except Exception as e:
        logger.error(f"Failed to update task {task_id} status: {e}")
