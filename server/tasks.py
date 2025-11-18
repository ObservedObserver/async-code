"""Flask routes for task management"""

from flask import Blueprint, jsonify, request
import time
import threading
import logging
import json
import os
from models import TaskStatus
from database import DatabaseOperations
from utils import run_ai_code_task_v2
from utils.github_operations import validate_github_token, create_pull_request_from_patch
from utils.patch_manager import apply_patch_to_github_repo

logger = logging.getLogger(__name__)

tasks_bp = Blueprint('tasks', __name__)


@tasks_bp.route('/start-task', methods=['POST'])
def start_task():
    """Start a new Claude Code automation task"""
    try:
        data = request.get_json()
        user_id = request.headers.get('X-User-ID')

        if not user_id:
            return jsonify({'error': 'User ID required'}), 400

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        prompt = data.get('prompt')
        repo_url = data.get('repo_url')
        branch = data.get('branch', 'main')
        github_token = data.get('github_token')
        model = data.get('model', 'claude')
        project_id = data.get('project_id')

        if not all([prompt, repo_url, github_token]):
            return jsonify({'error': 'prompt, repo_url, and github_token are required'}), 400

        if model not in ['claude', 'codex']:
            return jsonify({'error': 'model must be either "claude" or "codex"'}), 400

        # Create initial chat message
        chat_messages = [{
            'role': 'user',
            'content': prompt.strip(),
            'timestamp': time.time()
        }]

        # Create task in database
        task = DatabaseOperations.create_task(
            user_id=user_id,
            project_id=project_id,
            repo_url=repo_url,
            target_branch=branch,
            agent=model,
            chat_messages=chat_messages
        )

        if not task:
            return jsonify({'error': 'Failed to create task'}), 500

        # Start task in background thread
        thread = threading.Thread(target=run_ai_code_task_v2, args=(task['id'], user_id, github_token))
        thread.daemon = True
        thread.start()

        return jsonify({
            'status': 'success',
            'task_id': task['id'],
            'message': 'Task started successfully'
        })

    except Exception as e:
        logger.error(f"Error starting task: {str(e)}")
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/task-status/<int:task_id>', methods=['GET'])
def get_task_status(task_id):
    """Get the status of a specific task"""
    try:
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({'error': 'User ID required'}), 400

        task = DatabaseOperations.get_task_by_id(task_id, user_id)
        if not task:
            logger.warning(f"🔍 Frontend polling for unknown task: {task_id}")
            return jsonify({'error': 'Task not found'}), 404

        logger.info(f"📊 Frontend polling task {task_id}: status={task['status']}")

        # Get the latest user prompt from chat messages
        prompt = _extract_prompt_from_task(task)

        return jsonify({
            'status': 'success',
            'task': {
                'id': task['id'],
                'status': task['status'],
                'prompt': prompt,
                'repo_url': task['repo_url'],
                'branch': task['target_branch'],
                'model': task.get('agent', 'claude'),
                'commit_hash': task.get('commit_hash'),
                'changed_files': task.get('changed_files', []),
                'error': task.get('error'),
                'created_at': task['created_at'],
                'project_id': task.get('project_id')
            }
        })

    except Exception as e:
        logger.error(f"Error fetching task status: {str(e)}")
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/tasks', methods=['GET'])
def list_all_tasks():
    """List all tasks for the authenticated user"""
    try:
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({'error': 'User ID required'}), 400

        project_id = request.args.get('project_id', type=int)
        tasks = DatabaseOperations.get_user_tasks(user_id, project_id)

        # Format tasks for response
        formatted_tasks = {}
        for task in tasks:
            prompt = _extract_prompt_from_task(task)

            formatted_tasks[str(task['id'])] = {
                'id': task['id'],
                'status': task['status'],
                'created_at': task['created_at'],
                'prompt': prompt[:50] + '...' if len(prompt) > 50 else prompt,
                'has_patch': bool(task.get('git_patch')),
                'project_id': task.get('project_id'),
                'repo_url': task.get('repo_url'),
                'agent': task.get('agent', 'claude'),
                'chat_messages': task.get('chat_messages', [])
            }

        return jsonify({
            'status': 'success',
            'tasks': formatted_tasks,
            'total_tasks': len(tasks)
        })

    except Exception as e:
        logger.error(f"Error listing tasks: {str(e)}")
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/tasks/<int:task_id>', methods=['GET'])
def get_task_details(task_id):
    """Get detailed information about a specific task"""
    try:
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({'error': 'User ID required'}), 400

        task = DatabaseOperations.get_task_by_id(task_id, user_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404

        return jsonify({
            'status': 'success',
            'task': task
        })

    except Exception as e:
        logger.error(f"Error fetching task details: {str(e)}")
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/tasks/<int:task_id>/chat', methods=['POST'])
def add_chat_message(task_id):
    """Add a chat message to a task"""
    try:
        data = request.get_json()
        user_id = request.headers.get('X-User-ID')

        if not user_id:
            return jsonify({'error': 'User ID required'}), 400

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        content = data.get('content')
        role = data.get('role', 'user')

        if not content:
            return jsonify({'error': 'content is required'}), 400

        if role not in ['user', 'assistant']:
            return jsonify({'error': 'role must be either "user" or "assistant"'}), 400

        task = DatabaseOperations.add_chat_message(task_id, user_id, role, content)
        if not task:
            return jsonify({'error': 'Task not found'}), 404

        return jsonify({
            'status': 'success',
            'task': task
        })

    except Exception as e:
        logger.error(f"Error adding chat message: {str(e)}")
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/git-diff/<int:task_id>', methods=['GET'])
def get_git_diff(task_id):
    """Get git diff for a task (legacy endpoint for compatibility)"""
    try:
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({'error': 'User ID required'}), 400

        task = DatabaseOperations.get_task_by_id(task_id, user_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404

        return jsonify({
            'status': 'success',
            'git_diff': task.get('git_diff', ''),
            'task_id': task_id
        })

    except Exception as e:
        logger.error(f"Error fetching git diff: {str(e)}")
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/validate-token', methods=['POST'])
def validate_token():
    """Validate GitHub token and check permissions"""
    try:
        data = request.get_json()
        github_token = data.get('github_token')
        repo_url = data.get('repo_url', '')

        if not github_token:
            return jsonify({'error': 'github_token is required'}), 400

        result = validate_github_token(github_token, repo_url)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Token validation error: {str(e)}")
        return jsonify({'error': f'Token validation failed: {str(e)}'}), 401


@tasks_bp.route('/create-pr/<int:task_id>', methods=['POST'])
def create_pull_request(task_id):
    """Create a pull request by applying the saved patch to a fresh repo clone"""
    try:
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({'error': 'User ID required'}), 400

        logger.info(f"🔍 PR creation requested for task: {task_id}")

        task = DatabaseOperations.get_task_by_id(task_id, user_id)
        if not task:
            logger.error(f"❌ Task {task_id} not found")
            return jsonify({'error': 'Task not found'}), 404

        if task['status'] != 'completed':
            return jsonify({'error': 'Task not completed yet'}), 400

        if not task.get('git_patch'):
            return jsonify({'error': 'No patch data available for this task'}), 400

        data = request.get_json() or {}

        # Get prompt from chat messages
        prompt = _extract_prompt_from_task(task)

        pr_title = data.get('title', f"Claude Code: {prompt[:50]}...")
        pr_body = data.get('body', f"Automated changes generated by Claude Code.\n\nPrompt: {prompt}\n\nChanged files:\n" + '\n'.join(f"- {f}" for f in task.get('changed_files', [])))
        github_token = data.get('github_token')

        if not github_token:
            return jsonify({'error': 'github_token is required'}), 400

        # Create PR using helper function
        result = create_pull_request_from_patch(
            task,
            github_token,
            pr_title,
            pr_body,
            apply_patch_to_github_repo
        )

        # Update task with PR information
        DatabaseOperations.update_task(task_id, user_id, {
            'pr_branch': result['branch'],
            'pr_number': result['pr_number'],
            'pr_url': result['pr_url']
        })

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error creating PR: {str(e)}")
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/migrate-legacy-tasks', methods=['POST'])
def migrate_legacy_tasks():
    """Migrate tasks from legacy JSON storage to Supabase"""
    try:
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({'error': 'User ID required'}), 400

        legacy_file = 'tasks_backup.json'
        if not os.path.exists(legacy_file):
            return jsonify({
                'status': 'success',
                'message': 'No legacy tasks file found',
                'migrated': 0
            })

        with open(legacy_file, 'r') as f:
            legacy_tasks = json.load(f)

        migrated_count = 0
        for task_id, task_data in legacy_tasks.items():
            try:
                # Check if already migrated
                existing = DatabaseOperations.get_task_by_legacy_id(task_id)
                if existing:
                    continue

                # Migrate task
                DatabaseOperations.migrate_legacy_task(task_data, user_id)
                migrated_count += 1
            except Exception as e:
                logger.warning(f"Failed to migrate task {task_id}: {e}")

        return jsonify({
            'status': 'success',
            'message': f'Migrated {migrated_count} tasks',
            'migrated': migrated_count
        })

    except Exception as e:
        logger.error(f"Error migrating legacy tasks: {str(e)}")
        return jsonify({'error': str(e)}), 500


def _extract_prompt_from_task(task):
    """Helper function to extract prompt from task chat messages"""
    if task.get('chat_messages'):
        for msg in task['chat_messages']:
            if msg.get('role') == 'user':
                return msg.get('content', '')
    return ""
