import os
import subprocess
import time


def run_command(cmd, cwd):

    print("\n--------------------------------")
    print(f"RUNNING TERMINAL COMMAND")
    print(f"Directory: {cwd}")
    print(f"Command: {cmd}")
    print("--------------------------------")

    start = time.time()

    if os.name == "nt":
        # Use PowerShell on Windows so commands like rm/ls/cat are supported.
        run_args = {
            "args": ["powershell", "-NoProfile", "-Command", cmd],
            "shell": False,
        }
    else:
        run_args = {
            "args": cmd,
            "shell": True,
        }

    result = subprocess.run(
        cwd=cwd,
        capture_output=True,
        text=True,
        **run_args,
    )

    end = time.time()

    print("\nTERMINAL OUTPUT")
    print(result.stdout)

    if result.stderr:
        print("TERMINAL ERROR")
        print(result.stderr)

    print(f"\nCOMMAND TIME: {round(end-start,2)} seconds")
    print("--------------------------------\n")

    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "code": result.returncode
    }