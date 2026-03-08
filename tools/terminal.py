import subprocess
import time


def run_command(cmd, cwd):

    print("\n--------------------------------")
    print(f"RUNNING TERMINAL COMMAND")
    print(f"Directory: {cwd}")
    print(f"Command: {cmd}")
    print("--------------------------------")

    start = time.time()

    result = subprocess.run(
        cmd,
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True
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