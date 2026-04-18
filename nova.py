import sys
import subprocess
import os
from core.loop import run_loop, interactive_loop

if __name__ == "__main__":
    scheduler_path = os.path.join(os.path.dirname(__file__), "core", "scheduler.py")
    subprocess.Popen(
        [sys.executable, scheduler_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]

    if args:
        prompt = " ".join(args)
        response = run_loop(prompt, dry_run=dry_run)
        print(response)
    else:
        interactive_loop(dry_run=dry_run)
