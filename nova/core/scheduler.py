"""
core/scheduler.py
Standalone scheduler process for Nova.
Run alongside nova loop: python core/scheduler.py
Polls nova.db every 5 seconds and executes due tasks.
"""

import time
import json
import sys
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from nova.core.scheduler_db import (
    init_scheduler_schema,
    get_due_tasks,
    mark_running,
    mark_done,
    mark_failed,
    reschedule,
    write_result,
    log_event,
)
from nova.core.tools import (
    get_system_stats,
    list_processes,
    kill_process,
    read_file,
    write_file,
    list_files,
    run_shell,
)

POLL_INTERVAL = 5  # seconds

# ── Tool dispatch table ───────────────────────────────────────────────────────

TOOL_MAP = {
    'get_system_stats': get_system_stats,
    'list_processes':   list_processes,
    'kill_process':     kill_process,
    'read_file':        read_file,
    'write_file':       write_file,
    'list_files':       list_files,
    'run_shell':        run_shell,
}


def dispatch(tool: str, args: dict) -> str:
    """Call the named tool with args. Returns string output."""
    fn = TOOL_MAP.get(tool)
    if fn is None:
        return f'[error] unknown tool: {tool}'
    try:
        result = fn(**args)
        # Tools may return str or dict — normalise to str
        if isinstance(result, dict):
            return json.dumps(result, indent=2)
        return str(result)
    except Exception as e:
        return f'[error] {tool} raised: {e}'


# ── Main loop ─────────────────────────────────────────────────────────────────

def run() -> None:
    print('[scheduler] starting — polling nova.db every 5s')
    log_event('scheduler', 'started', f'pid={Path("/proc/self").resolve().name if Path("/proc/self").exists() else "win"}')
    init_scheduler_schema()

    while True:
        try:
            due = get_due_tasks()
            if due:
                print(f'[scheduler] {len(due)} task(s) due')

            for task in due:
                task_id   = task['id']
                task_name = task['name']
                tool      = task['tool']
                args      = json.loads(task['args'])
                interval  = task['interval_s']

                print(f'[scheduler] running task {task_id}: {task_name}')
                mark_running(task_id)
                log_event('scheduler', 'task_start', task_name)

                output = dispatch(tool, args)
                write_result(task_id, output)
                log_event('scheduler', 'task_done', task_name)

                if interval:
                    next_run = time.time() + interval
                    reschedule(task_id, next_run)
                    print(f'[scheduler] rescheduled {task_name} in {interval}s')
                else:
                    mark_done(task_id)
                    print(f'[scheduler] one-shot {task_name} complete')

        except KeyboardInterrupt:
            print('\n[scheduler] shutdown requested — exiting cleanly')
            log_event('scheduler', 'stopped', 'KeyboardInterrupt')
            break
        except Exception as e:
            print(f'[scheduler] loop error: {e}')
            log_event('scheduler', 'loop_error', str(e))

        time.sleep(POLL_INTERVAL)


if __name__ == '__main__':
    run()
