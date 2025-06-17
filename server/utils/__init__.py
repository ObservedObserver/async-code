
import logging
import threading
import fcntl
import queue
import atexit

from .code_task_v2 import run_ai_code_task_v2, _run_ai_code_task_v2_internal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Global Codex execution queue and lock for sequential processing
codex_execution_queue = queue.Queue()
codex_execution_lock = threading.Lock()
codex_worker_thread = None
codex_lock_file = '/tmp/codex_global_lock'

def init_codex_sequential_processor():
    """Initialize the sequential Codex processor"""
    global codex_worker_thread
    
    def codex_worker():
        """Worker thread that processes Codex tasks sequentially"""
        logger.info("🔄 Codex sequential worker thread started")
        
        while True:
            try:
                # Get the next task from the queue (blocks if empty)
                task_data = codex_execution_queue.get(timeout=1.0)
                if task_data is None:  # Poison pill to stop the thread
                    logger.info("🛑 Codex worker thread stopping")
                    break
                    
                task_id, user_id, github_token, is_v2 = task_data
                logger.info(f"🎯 Processing Codex task {task_id} sequentially")
                
                # Acquire file-based lock for additional safety
                try:
                    with open(codex_lock_file, 'w') as lock_file:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                        logger.info(f"🔒 Global Codex lock acquired for task {task_id}")
                        
                        # Execute the task
                        if is_v2:
                            _execute_codex_task_v2(task_id, user_id, github_token)
                            
                        logger.info(f"✅ Codex task {task_id} completed")
                        
                except Exception as e:
                    logger.error(f"❌ Error executing Codex task {task_id}: {e}")
                finally:
                    codex_execution_queue.task_done()
                    
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"❌ Error in Codex worker thread: {e}")
                
    # Start the worker thread if not already running
    with codex_execution_lock:
        if codex_worker_thread is None or not codex_worker_thread.is_alive():
            codex_worker_thread = threading.Thread(target=codex_worker, daemon=True)
            codex_worker_thread.start()
            logger.info("🚀 Codex sequential processor initialized")

def queue_codex_task(task_id, user_id=None, github_token=None, is_v2=True):
    """Queue a Codex task for sequential execution"""
    init_codex_sequential_processor()
    
    logger.info(f"📋 Queuing Codex task {task_id} for sequential execution")
    codex_execution_queue.put((task_id, user_id, github_token, is_v2))
    
    # Wait for the task to be processed
    logger.info(f"⏳ Waiting for Codex task {task_id} to be processed...")
    codex_execution_queue.join()

def _execute_codex_task_v2(task_id: int, user_id: str, github_token: str):
    """Execute Codex task v2 - internal method called by sequential processor"""
    # This will contain the actual execution logic
    return _run_ai_code_task_v2_internal(task_id, user_id, github_token)


# Cleanup function to stop the worker thread
def cleanup_codex_processor():
    """Clean up the Codex processor on exit"""
    global codex_worker_thread
    if codex_worker_thread and codex_worker_thread.is_alive():
        logger.info("🧹 Shutting down Codex sequential processor")
        codex_execution_queue.put(None)  # Poison pill
        codex_worker_thread.join(timeout=5.0)

atexit.register(cleanup_codex_processor)

