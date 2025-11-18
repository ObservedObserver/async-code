"""Docker container management utilities for AI code tasks"""

import docker
import logging
import time
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)
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


def create_container(task_id, container_image, container_command, env_vars, model_cli):
    """Create and configure a Docker container for AI code task execution

    Args:
        task_id: The task ID
        container_image: Docker image name
        container_command: Command to run in container
        env_vars: Environment variables dict
        model_cli: Model CLI type ('claude' or 'codex')

    Returns:
        Container object or None on failure
    """
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
        'name': f'ai-code-task-{task_id}-{int(time.time())}-{uuid.uuid4().hex[:8]}',
        'mem_limit': '2g',  # Limit memory usage to prevent resource conflicts
        'cpu_shares': 1024,  # Standard CPU allocation
        'ulimits': [docker.types.Ulimit(name='nofile', soft=1024, hard=2048)]
    }

    # Add essential Docker configuration for Codex compatibility
    if model_cli == 'codex':
        logger.warning(f"⚠️  Running Codex with enhanced Docker privileges to bypass seccomp/landlock restrictions")
        container_kwargs.update({
            'security_opt': [
                'seccomp=unconfined',
                'apparmor=unconfined',
                'no-new-privileges=false'
            ],
            'cap_add': ['ALL'],
            'privileged': True,
            'pid_mode': 'host'
        })

    # Retry container creation with enhanced conflict handling
    container = None
    max_retries = 5
    for attempt in range(max_retries):
        try:
            logger.info(f"🔄 Container creation attempt {attempt + 1}/{max_retries}")
            container = docker_client.containers.run(**container_kwargs)
            logger.info(f"✅ Container created successfully: {container.id[:12]} (name: {container_kwargs['name']})")
            return container
        except docker.errors.APIError as e:
            error_msg = str(e)
            if "Conflict" in error_msg and "already in use" in error_msg:
                logger.warning(f"🔄 Container name conflict on attempt {attempt + 1}, generating new name...")
                new_name = f'ai-code-task-{task_id}-{int(time.time())}-{uuid.uuid4().hex[:8]}'
                container_kwargs['name'] = new_name
                logger.info(f"🆔 New container name: {new_name}")
                cleanup_orphaned_containers()
            else:
                logger.warning(f"⚠️  Docker API error on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    raise Exception(f"Failed to create container after {max_retries} attempts: {e}")
            time.sleep(2 ** attempt)
        except Exception as e:
            logger.error(f"❌ Unexpected error creating container on attempt {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)

    return None


def wait_for_container(container, timeout=300):
    """Wait for container to complete and return result

    Args:
        container: Docker container object
        timeout: Timeout in seconds

    Returns:
        Tuple of (result dict, logs string)
    """
    try:
        logger.info(f"🔄 Waiting for container script to complete naturally...")

        # Check initial container state
        container.reload()
        logger.info(f"🔍 Container initial state: {container.status}")

        # Use standard wait - container should exit when bash script finishes
        logger.info(f"🔄 Calling container.wait() - container should exit when script completes...")
        result = container.wait(timeout=timeout)
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

        return result, logs

    except Exception as e:
        logger.error(f"⏰ Container timeout or error: {str(e)}")
        # Try to get logs even on error
        try:
            logs = container.logs().decode('utf-8')
        except Exception as log_error:
            logs = f"Container failed and logs unavailable: {log_error}"
        raise Exception(f"Container execution timeout or error: {str(e)}")


def cleanup_container(container):
    """Clean up a Docker container after execution

    Args:
        container: Docker container object
    """
    try:
        container.reload()
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
