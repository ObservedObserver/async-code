import logging
import docker
import docker.types
import uuid
import time
from datetime import datetime
from database import DatabaseOperations
from .code_task import MODEL_HANDLERS, claude as claude_module
from .code_task.common import TaskContext

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Docker client
docker_client = docker.from_env()

def cleanup_orphaned_containers():
    """Clean up orphaned AI code task containers aggressively"""
    try:
        # Get all containers with our naming pattern
        containers = docker_client.containers.list(all=True, filters={'name': 'ai-code-task-'})
        orphaned_count = 0
        current_time = time.time()
        
        for container in containers:
            try:
                # Get container creation time
                created_at = container.attrs['Created']
                # Parse ISO format timestamp and convert to epoch time
                created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00')).timestamp()
                age_hours = (current_time - created_time) / 3600
                
                # Remove containers that are:
                # 1. Not running (exited, dead, created)
                # 2. OR older than 2 hours (stuck containers)
                # 3. OR in error state
                should_remove = (
                    container.status in ['exited', 'dead', 'created'] or
                    age_hours > 2 or
                    container.status == 'restarting'
                )
                
                if should_remove:
                    logger.info(f"🧹 Removing orphaned container {container.id[:12]} (status: {container.status}, age: {age_hours:.1f}h)")
                    container.remove(force=True)
                    orphaned_count += 1
                
            except Exception as e:
                logger.warning(f"⚠️  Failed to cleanup container {container.id[:12]}: {e}")
                # If we can't inspect it, try to force remove it anyway
                try:
                    container.remove(force=True)
                    orphaned_count += 1
                    logger.info(f"🧹 Force removed problematic container: {container.id[:12]}")
                except Exception as force_error:
                    logger.warning(f"⚠️  Could not force remove container {container.id[:12]}: {force_error}")
        
        if orphaned_count > 0:
            logger.info(f"🧹 Cleaned up {orphaned_count} orphaned containers")
        
    except Exception as e:
        logger.warning(f"⚠️  Failed to cleanup orphaned containers: {e}")

def run_ai_code_task_v2(task_id: int, user_id: str, github_token: str):
    """Run AI Code automation (Claude or Codex) in a container - Supabase version"""
    try:
        # Get task from database to check the model type
        task = DatabaseOperations.get_task_by_id(task_id, user_id)
        if not task:
            logger.error(f"Task {task_id} not found in database")
            return
        
        model_cli = task.get('agent', 'claude')
        
        # With comprehensive sandboxing fixes, both Claude and Codex can now run in parallel
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
    """Internal implementation of AI Code automation - called directly for Claude or via queue for Codex"""
    try:
        # Clean up any orphaned containers before starting new task
        cleanup_orphaned_containers()
        
        # Get task from database (v2 function)
        task = DatabaseOperations.get_task_by_id(task_id, user_id)
        if not task:
            logger.error(f"Task {task_id} not found in database")
            return
        
        # Update task status to running
        DatabaseOperations.update_task(task_id, user_id, {'status': 'running'})

        model_cli = str(task.get('agent', 'claude') or 'claude').lower()
        if model_cli not in MODEL_HANDLERS:
            logger.warning(
                "ℹ️  Unknown model '%s' requested for task %s; defaulting to Claude",
                model_cli,
                task_id,
            )
            model_cli = 'claude'

        model_name = model_cli.upper()
        logger.info(f"🚀 Starting {model_name} Code task {task_id}")
        
        # Get prompt from chat messages
        prompt = ""
        if task.get('chat_messages'):
            for msg in task['chat_messages']:
                if msg.get('role') == 'user':
                    prompt = msg.get('content', '')
                    break
        
        if not prompt:
            error_msg = "No user prompt found in chat messages"
            logger.error(error_msg)
            DatabaseOperations.update_task(task_id, user_id, {
                'status': 'failed',
                'error': error_msg
            })
            return
        
        logger.info(f"📋 Task details: prompt='{prompt[:50]}...', repo={task['repo_url']}, branch={task['target_branch']}, model={model_name}")
        logger.info(f"Starting {model_name} task {task_id}")
        
        base_env = {
            'CI': 'true',
            'TERM': 'dumb',
            'NO_COLOR': '1',
            'FORCE_COLOR': '0',
            'NONINTERACTIVE': '1',
            'DEBIAN_FRONTEND': 'noninteractive',
        }

        user = DatabaseOperations.get_user_by_id(user_id)
        user_preferences = user.get('preferences', {}) if user else {}

        if user_preferences:
            logger.info(f"🔧 Found user preferences for {model_cli}: {list(user_preferences.keys())}")

        model_module = MODEL_HANDLERS.get(model_cli, claude_module)
        container_image = getattr(model_module, 'CONTAINER_IMAGE', 'claude-code-automation:latest')

        env_vars = dict(base_env)
        env_vars.update(model_module.get_environment(user_preferences))

        if hasattr(model_module, 'prepare_for_run'):
            model_module.prepare_for_run(task_id, logger)

        credentials_content = ''
        escaped_credentials = ''

        if hasattr(model_module, 'extract_credentials'):
            logger.info(
                "🔍 Looking for %s credentials in user preferences for task %s",
                model_cli.capitalize(),
                task_id,
            )
            credentials_content, escaped_credentials = model_module.extract_credentials(
                user_preferences,
                task_id,
                logger,
            )

        context = TaskContext(
            task_id=task_id,
            task=task,
            prompt=prompt,
            github_token=github_token,
            model_cli=model_cli,
            credentials_content=credentials_content,
            escaped_credentials=escaped_credentials,
        )

        container_command = model_module.build_command(context)

        # Run container with unified AI Code tools (supports both Claude and Codex)
        logger.info(f"🐳 Creating Docker container for task {task_id} using {container_image} (model: {model_name})")
        
        # Configure Docker security options for Codex compatibility
        container_kwargs = {
            'image': container_image,
            'command': ['bash', '-c', container_command],
            'environment': env_vars,
            'detach': True,
            'remove': False,  # Don't auto-remove so we can get logs
            'working_dir': '/workspace',
            'network_mode': 'bridge',  # Ensure proper networking
            'tty': False,  # Don't allocate TTY - may prevent clean exit
            'stdin_open': False,  # Don't keep stdin open - may prevent clean exit
            'name': f'ai-code-task-{task_id}-{int(time.time())}-{uuid.uuid4().hex[:8]}',  # Highly unique container name with UUID
            'mem_limit': '2g',  # Limit memory usage to prevent resource conflicts
            'cpu_shares': 1024,  # Standard CPU allocation
            'ulimits': [docker.types.Ulimit(name='nofile', soft=1024, hard=2048)]  # File descriptor limits
        }
        
        container_overrides = {}
        if hasattr(model_module, 'get_container_overrides'):
            container_overrides = model_module.get_container_overrides() or {}

        if container_overrides:
            if model_cli == 'codex':
                logger.warning(
                    "⚠️  Running Codex with enhanced Docker privileges to bypass seccomp/landlock restrictions"
                )
            container_kwargs.update(container_overrides)
        
        # Retry container creation with enhanced conflict handling
        container = None
        max_retries = 5  # Increased retries for better reliability
        for attempt in range(max_retries):
            try:
                logger.info(f"🔄 Container creation attempt {attempt + 1}/{max_retries}")
                container = docker_client.containers.run(**container_kwargs)
                logger.info(f"✅ Container created successfully: {container.id[:12]} (name: {container_kwargs['name']})")
                break
            except docker.errors.APIError as e:
                error_msg = str(e)
                if "Conflict" in error_msg and "already in use" in error_msg:
                    # Handle container name conflicts by generating a new unique name
                    logger.warning(f"🔄 Container name conflict on attempt {attempt + 1}, generating new name...")
                    new_name = f'ai-code-task-{task_id}-{int(time.time())}-{uuid.uuid4().hex[:8]}'
                    container_kwargs['name'] = new_name
                    logger.info(f"🆔 New container name: {new_name}")
                    # Try to clean up any conflicting containers
                    cleanup_orphaned_containers()
                else:
                    logger.warning(f"⚠️  Docker API error on attempt {attempt + 1}: {e}")
                    if attempt == max_retries - 1:
                        raise Exception(f"Failed to create container after {max_retries} attempts: {e}")
                time.sleep(2 ** attempt)  # Exponential backoff
            except Exception as e:
                logger.error(f"❌ Unexpected error creating container on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff
        
        # Update task with container ID (v2 function)
        DatabaseOperations.update_task(task_id, user_id, {'container_id': container.id})
        
        logger.info(f"⏳ Waiting for container to complete (timeout: 300s)...")
        
        # Wait for container to finish - should exit naturally when script completes
        try:
            logger.info(f"🔄 Waiting for container script to complete naturally...")
            
            # Check initial container state
            container.reload()
            logger.info(f"🔍 Container initial state: {container.status}")
            
            # Use standard wait - container should exit when bash script finishes
            logger.info(f"🔄 Calling container.wait() - container should exit when script completes...")
            result = container.wait(timeout=300)  # 5 minute timeout
            logger.info(f"🎯 Container exited naturally! Exit code: {result['StatusCode']}")
            
            # Verify final container state
            container.reload()
            logger.info(f"🔍 Final container state: {container.status}")
            
            # Get logs before any cleanup operations
            logger.info(f"📜 Retrieving container logs...")
            try:
                logs = container.logs().decode('utf-8')
                logger.info(f"📝 Retrieved {len(logs)} characters of logs")
                logger.info(f"🔍 First 200 chars of logs: {logs[:200]}...")
            except Exception as log_error:
                logger.warning(f"❌ Failed to get container logs: {log_error}")
                logs = f"Failed to retrieve logs: {log_error}"
            
            # Clean up container after getting logs
            try:
                container.reload()  # Refresh container state
                container.remove()
                logger.info(f"🧹 Successfully removed container {container.id[:12]}")
            except docker.errors.NotFound:
                logger.info(f"🧹 Container {container.id[:12]} already removed")
            except Exception as cleanup_error:
                logger.warning(f"⚠️  Failed to remove container {container.id[:12]}: {cleanup_error}")
                # Try force removal as fallback
                try:
                    container.remove(force=True)
                    logger.info(f"🧹 Force removed container {container.id[:12]}")
                except docker.errors.NotFound:
                    logger.info(f"🧹 Container {container.id[:12]} already removed")
                except Exception as force_cleanup_error:
                    logger.error(f"❌ Failed to force remove container {container.id[:12]}: {force_cleanup_error}")
                
        except Exception as e:
            logger.error(f"⏰ Container timeout or error: {str(e)}")
            logger.error(f"🔄 Updating task status to FAILED due to timeout/error...")
            
            DatabaseOperations.update_task(task_id, user_id, {
                'status': 'failed',
                'error': f"Container execution timeout or error: {str(e)}"
            })
            
            # Try to get logs even on error
            try:
                logs = container.logs().decode('utf-8')
            except Exception as log_error:
                logs = f"Container failed and logs unavailable: {log_error}"
            
            # Try to clean up container on error
            try:
                container.reload()  # Refresh container state
                container.remove(force=True)
                logger.info(f"Cleaned up failed container {container.id}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to remove failed container {container.id}: {cleanup_error}")
            return
        
        if result['StatusCode'] == 0:
            logger.info(f"✅ Container exited successfully (code 0) - parsing results...")
            # Parse output to extract commit hash, diff, and patch
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
                        # File processing complete
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
                    if line.strip():  # Only add non-empty lines
                        changed_files.append(line.strip())
            
            logger.info(f"🔄 Updating task status to COMPLETED...")
            
            # Update task in database
            DatabaseOperations.update_task(task_id, user_id, {
                'status': 'completed',
                'commit_hash': commit_hash,
                'git_diff': '\n'.join(git_diff),
                'git_patch': '\n'.join(git_patch),
                'changed_files': changed_files,
                'execution_metadata': {
                    'file_changes': file_changes,
                    'completed_at': datetime.now().isoformat()
                }
            })
            
            logger.info(f"🎉 {model_name} Task {task_id} completed successfully! Commit: {commit_hash[:8] if commit_hash else 'N/A'}, Diff lines: {len(git_diff)}")
            
        else:
            logger.error(f"❌ Container exited with error code {result['StatusCode']}")
            DatabaseOperations.update_task(task_id, user_id, {
                'status': 'failed',
                'error': f"Container exited with code {result['StatusCode']}: {logs}"
            })
            logger.error(f"💥 {model_name} Task {task_id} failed: {logs[:200]}...")
            
    except Exception as e:
        model_name = task.get('agent', 'claude').upper() if task else 'UNKNOWN'
        logger.error(f"💥 Unexpected exception in {model_name} task {task_id}: {str(e)}")
        
        try:
            DatabaseOperations.update_task(task_id, user_id, {
                'status': 'failed',
                'error': str(e)
            })
        except:
            logger.error(f"Failed to update task {task_id} status after exception")
        
        logger.error(f"🔄 {model_name} Task {task_id} failed with exception: {str(e)}")
