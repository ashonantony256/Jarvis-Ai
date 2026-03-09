import os
import subprocess
import time


def _trim_output(text, max_chars=6000):
    safe_text = text or ""
    if len(safe_text) <= max_chars:
        return safe_text

    head = safe_text[:3000]
    tail = safe_text[-3000:]
    omitted = len(safe_text) - len(head) - len(tail)
    return f"{head}\n... [omitted {omitted} chars] ...\n{tail}"


def _categorize_error(stderr_text, exit_code, timed_out):
    lower = (stderr_text or "").lower()
    if timed_out:
        return "timeout"
    if exit_code == 0:
        return "none"
    if "not recognized" in lower or "command not found" in lower:
        return "missing-command"
    if "permission" in lower or "access is denied" in lower:
        return "permission"
    if "enoent" in lower or "no such file" in lower:
        return "missing-file"
    if "network" in lower or "econn" in lower or "etimedout" in lower:
        return "network"
    return "runtime"


def run_command(cmd, cwd, timeout_seconds=180):

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

    timed_out = False
    try:
        result = subprocess.run(
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            **run_args,
        )
        stdout = result.stdout
        stderr = result.stderr
        code = result.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + f"\nCommand timed out after {timeout_seconds} seconds."
        code = 124

    end = time.time()

    print("\nTERMINAL OUTPUT")
    print(stdout)

    if stderr:
        print("TERMINAL ERROR")
        print(stderr)

    print(f"\nCOMMAND TIME: {round(end-start,2)} seconds")
    print("--------------------------------\n")

    return {
        "stdout": stdout,
        "stderr": stderr,
        "stdout_trimmed": _trim_output(stdout),
        "stderr_trimmed": _trim_output(stderr),
        "code": code,
        "timed_out": timed_out,
        "error_type": _categorize_error(stderr, code, timed_out),
    }