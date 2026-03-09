import time
import os
from typing import Dict, Optional

from router import choose_model
from ollama_client import run_model
from tools.terminal import run_command
from tools.files import read_file, write_file, list_files


def run_task(prompt, cwd, context=None, available_models=None):

    def extract_single_action(raw_text):
        """Extract exactly one valid action from model output."""
        cleaned = raw_text.replace("```", "").strip()
        if not cleaned:
            return ""

        lines = cleaned.splitlines()

        def is_action_line(line):
            stripped = line.strip()
            return (
                stripped.startswith("WRITE:")
                or stripped.startswith("RUN:")
                or stripped.startswith("READ:")
                or stripped == "DONE"
                or stripped == "RESUME"
            )

        start_idx = -1
        for idx, line in enumerate(lines):
            if is_action_line(line):
                start_idx = idx
                break

        if start_idx == -1:
            return ""

        first = lines[start_idx].strip()

        if first.startswith("WRITE:"):
            content_lines = []
            for line in lines[start_idx + 1 :]:
                if is_action_line(line):
                    break
                content_lines.append(line)
            if content_lines:
                return first + "\n" + "\n".join(content_lines)
            return first + "\n"

        return first

    def truncate_for_history(text, limit=6000):
        """Keep history compact enough for prompt context while preserving key output."""
        safe_text = text if text is not None else ""
        if len(safe_text) <= limit:
            return safe_text
        truncated = len(safe_text) - limit
        return safe_text[:limit] + f"\n... [truncated {truncated} chars]"

    def is_risky_command(cmd):
        normalized = (cmd or "").strip().lower()
        risky_patterns = [
            "rm -rf",
            "del /f",
            "rmdir /s",
            "format ",
            "shutdown ",
            "pip install --upgrade pip",
            "npm install -g",
            "choco install",
            "winget install",
        ]
        return any(pattern in normalized for pattern in risky_patterns)

    def requires_run_verification(prompt_text):
        lower = (prompt_text or "").lower()
        return any(token in lower for token in ["run", "start", "serve", "launch"])

    def summarize_step_result(result: Dict[str, str], cmd: str):
        return f"""Action: RUN
Command: {cmd}
Exit Code: {result.get('code', 'unknown')}
Timed Out: {result.get('timed_out', False)}
Error Type: {result.get('error_type', 'unknown')}
STDOUT:
{result.get('stdout_trimmed', '')}
STDERR:
{result.get('stderr_trimmed', '')}
"""

    def is_navigation_or_noop_command(cmd):
        normalized = (cmd or "").strip().lower()
        if not normalized:
            return True

        if normalized in ["cd", "pwd", "ls", "dir", "get-location", "pushd", "popd"]:
            return True

        prefixes = [
            "cd ",
            "chdir ",
            "set-location ",
            "push-location ",
            "pop-location ",
            "ls ",
            "dir ",
            "get-childitem",
            "get-location",
        ]
        return any(normalized.startswith(prefix) for prefix in prefixes)

    def is_mutating_command(cmd):
        normalized = (cmd or "").strip().lower()
        if not normalized:
            return False

        mutating_prefixes = [
            "npm create",
            "npm init",
            "npm install",
            "npx create",
            "pnpm create",
            "pnpm add",
            "yarn create",
            "yarn add",
            "mkdir ",
            "md ",
            "rmdir ",
            "rm ",
            "del ",
            "erase ",
            "touch ",
            "new-item ",
            "set-content ",
            "add-content ",
            "move ",
            "mv ",
            "copy ",
            "cp ",
            "git clone",
            "git init",
            "pip install",
            "python -m venv",
            "dotnet new",
            "cargo new",
        ]

        if any(normalized.startswith(prefix) for prefix in mutating_prefixes):
            return True

        # Basic shell redirection often indicates file writes.
        if ">" in normalized:
            return True

        return False

    prompt_lower = prompt.lower()
    mutation_intent_keywords = [
        "create",
        "build",
        "setup",
        "set up",
        "generate",
        "init",
        "initialize",
        "write",
        "add",
        "update",
        "modify",
        "fix",
        "delete",
        "remove",
        "rename",
        "refactor",
        "install",
    ]
    prompt_requires_mutation = any(keyword in prompt_lower for keyword in mutation_intent_keywords)

    print("\n===================================")
    print("TASK STARTED")
    print("===================================\n")

    total_start = time.time()

    try:
        # STEP 1: Planning
        print("STEP 1: Planning task")

        model = choose_model("plan", available_models=available_models)

        planning_prompt = f"""
You are a planning agent. Create a SHORT, SIMPLE plan for another AI coding agent who can run terminal commands, read/write files, and write code.

Current directory: {cwd}

User request:
{prompt}

IMPORTANT:
1. Keep plans SHORT and SIMPLE
2. Include one preflight step to understand directory/files before mutation.
3. Include verification steps for critical outcomes (especially run/start tasks).
4. Use numbered steps
5. Do NOT include commands or code in the plan - just plain language descriptions of the steps needed to complete the task
"""

        history = context.chat_history[-8:] if context else None
        system_prompt = context.system_prompt if context else None
        plan = run_model(model, planning_prompt, system_prompt=system_prompt, history=history)

        print("\nPLAN:")
        print("===================================")
        print(plan)
        print("===================================\n")

        executed_commands = ""
        last_step_result = "No steps executed yet."
        pending_action = ""
        debug_mode = False
        last_failed_command = ""
        last_error_message = ""
        step_count = 0
        executed_action_count = 0
        mutating_action_count = 0
        debug_success_since_failure = 0
        last_action_success = False
        successful_run_count = 0
        preflight_done = False
        repeated_failure_counts = {}
        requires_run_success = requires_run_verification(prompt)

        def append_step_history(action_type, target, status, details):
            nonlocal executed_commands
            executed_commands += f"""
    --- STEP {executed_action_count} ---
    ACTION: {action_type}
    TARGET: {target}
    STATUS: {status}
    DETAILS:
    {details}
    --- END STEP ---
    """

        if prompt_requires_mutation:
            try:
                initial_files = list_files(cwd)
                rel_files = [os.path.relpath(path, cwd) for path in initial_files]
                rel_files = [
                    rel_path
                    for rel_path in rel_files
                    if not rel_path.startswith(".git\\")
                    and "__pycache__" not in rel_path
                    and "node_modules" not in rel_path
                ]
                visible = rel_files[:200]
                snapshot_text = "\n".join(visible)
                if len(rel_files) > 200:
                    snapshot_text += f"\n... truncated {len(rel_files) - 200} more files"
                preflight_done = True
                last_step_result = (
                    f"Preflight directory scan complete. Visible files: {len(visible)}. "
                    "Use this context before mutating actions."
                )
                append_step_history("PREFLIGHT", cwd, "success", truncate_for_history(snapshot_text))
            except Exception as e:
                append_step_history("PREFLIGHT", cwd, "failure", str(e))
                last_step_result = f"Preflight scan failed: {e}"

        while True:

            step_count += 1

            if step_count > 50:
                print("STOPPING: Too many steps")
                break

            step_start = time.time()

            print("STEP 2: Generating action")

            if pending_action:
                action = pending_action
                pending_action = ""
                print("USING DEBUG ACTION:")
                print("--------------------------------")
                print(action)
                print("--------------------------------\n")
            else:
                model = choose_model("debug" if debug_mode else "code", available_models=available_models)

                if debug_mode:
                    action_prompt = f"""
You are a debugging agent. Stay in debugging mode and fix the task.

ORIGINAL USER REQUEST:
{prompt}

TASK PLAN:
{plan}

FULL EXECUTION HISTORY:
{executed_commands}

SESSION SUMMARY:
{context.build_session_summary() if context else 'No session summary available.'}

LAST FAILED COMMAND:
{last_failed_command}

LAST ERROR MESSAGE:
{last_error_message}

LAST STEP RESULT:
{last_step_result}

Respond with EXACTLY ONE command:

WRITE: <file_path>
<content>

RUN: <command>

READ: <file_path>

DONE

RESUME

IMPORTANT:
1. Output ONLY ONE command, nothing else
2. No explanations
3. Paths must be relative to current directory
4. Do NOT use cd/chdir/set-location; command executor already runs in the correct working directory
5. Do NOT repeat failed commands without changing approach
6. Use command output and errors to decide your next step
7. Do NOT respond DONE before at least one recovery attempt action (RUN/READ/WRITE)
8. Remain in debugging flow until completion
9. Use RESUME only when the issue is fixed and normal coding flow should continue
10. If a mutating action is needed and preflight context is missing, do READ: . first
"""
                else:
                    action_prompt = f"""
You are a coding agent executing a task.

ORIGINAL USER REQUEST:
{prompt}

TASK PLAN:
{plan}

EXECUTION HISTORY:
{executed_commands}

LAST STEP RESULT:
{last_step_result}

SESSION SUMMARY:
{context.build_session_summary() if context else 'No session summary available.'}

Respond with EXACTLY ONE command from:

WRITE: <file_path>
<file content>

RUN: <command>

READ: <file_path>

DONE

CRITICAL RULES:
1. Only ONE command per response
2. No explanations or extra text
3. Paths must be relative to current directory
4. Do NOT use cd/chdir/set-location; command executor already runs in the correct working directory
5. You CANNOT respond DONE before at least one real action (RUN/READ/WRITE) has executed in this task
6. CHECK EXECUTION HISTORY - if a previous successful step completed the user's request, respond with: DONE
7. FOR DELETIONS: if you ran 'rm <file>' and got EXIT CODE: 0, the file is deleted. Respond with: DONE
8. FOR CREATIONS: if you wrote a file successfully, respond with: DONE
9. Do NOT verify, confirm, or re-check successful operations
10. Do NOT repeat any command that already succeeded (EXIT CODE: 0)
11. Do NOT repeat failed commands - try different approach or DONE if impossible
12. If a command failed because the desired state already exists, respond with: DONE
13. Use LAST STEP RESULT to decide the next best action for ANY task type
14. Before mutating actions, ensure directory context exists (READ . if needed)
"""

                history = context.chat_history[-8:] if context else None
                system_prompt = context.system_prompt if context else None
                raw_action = run_model(model, action_prompt, system_prompt=system_prompt, history=history)
                action = extract_single_action(raw_action)

                print("\nRAW MODEL OUTPUT:")
                print("--------------------------------")
                print(raw_action)
                print("--------------------------------\n")

            if not action:
                print("INVALID ACTION FORMAT — retrying...\n")
                last_step_result = "Invalid model response format (no executable action found)."
                step_end = time.time()
                print(f"STEP TIME: {round(step_end-step_start,2)} seconds\n")
                continue

            # RUN COMMAND
            if action.startswith("RUN:"):

                executed_action_count += 1

                cmd = action.split("RUN:")[1].strip().split("\n")[0]

                if context and context.safety_mode and is_risky_command(cmd):
                    last_step_result = (
                        f"Blocked by safety mode: '{cmd}'. "
                        "Disable safety mode from CLI with 'safe off' to allow risky command."
                    )
                    last_action_success = False
                    debug_mode = True
                    last_failed_command = cmd
                    last_error_message = "blocked-by-safety-mode"
                    append_step_history("RUN", cmd, "blocked", last_step_result)
                    print("COMMAND BLOCKED BY SAFETY MODE\n")
                    step_end = time.time()
                    print(f"STEP TIME: {round(step_end-step_start,2)} seconds\n")
                    continue

                if not preflight_done and (prompt_requires_mutation or is_mutating_command(cmd)):
                    last_step_result = "RUN rejected: preflight directory context missing. Use READ: . before mutating commands."
                    append_step_history("RUN", cmd, "rejected", last_step_result)
                    print("RUN REJECTED - PREFLIGHT REQUIRED\n")
                    step_end = time.time()
                    print(f"STEP TIME: {round(step_end-step_start,2)} seconds\n")
                    continue

                if debug_mode and repeated_failure_counts.get(cmd, 0) >= 2:
                    last_step_result = (
                        f"RUN rejected: command '{cmd}' already failed multiple times. "
                        "Choose a different recovery approach."
                    )
                    append_step_history("RUN", cmd, "rejected", last_step_result)
                    print("RUN REJECTED - REPEATED FAILURE\n")
                    step_end = time.time()
                    print(f"STEP TIME: {round(step_end-step_start,2)} seconds\n")
                    continue

                print(f"EXECUTING COMMAND: {cmd}")

                result = run_command(cmd, cwd, timeout_seconds=240)

                last_step_result = summarize_step_result(result, cmd)

                run_details = f"""Exit Code: {result.get('code', 'unknown')}
Timed Out: {result.get('timed_out', False)}
Error Type: {result.get('error_type', 'unknown')}
STDOUT:
{result.get('stdout_trimmed', '')}
STDERR:
{result.get('stderr_trimmed', '')}
"""

                if result["code"] != 0:

                    print("\nERROR DETECTED -> DEBUGGING\n")
                    debug_mode = True
                    last_failed_command = cmd
                    last_error_message = result.get("stderr_trimmed", "")
                    repeated_failure_counts[cmd] = repeated_failure_counts.get(cmd, 0) + 1
                    last_action_success = False
                    append_step_history("RUN", cmd, "failure", run_details)

                else:
                    print("COMMAND SUCCESS\n")
                    last_action_success = True
                    successful_run_count += 1
                    repeated_failure_counts[cmd] = 0
                    if is_mutating_command(cmd) and not is_navigation_or_noop_command(cmd):
                        mutating_action_count += 1
                    if debug_mode:
                        debug_success_since_failure += 1
                    append_step_history("RUN", cmd, "success", run_details)

            # READ FILE
            elif action.startswith("READ:"):

                executed_action_count += 1

                path = action.split("READ:")[1].strip().split("\n")[0]

                print(f"READING FILE: {path}")

                target_path = os.path.join(cwd, path)

                try:
                    if os.path.isdir(target_path):
                        files = list_files(target_path)
                        rel_files = [os.path.relpath(file_path, cwd) for file_path in files]
                        rel_files = [
                            rel_path
                            for rel_path in rel_files
                            if not rel_path.startswith(".git\\")
                            and "__pycache__" not in rel_path
                            and "node_modules" not in rel_path
                        ]
                        max_files = 200
                        visible_files = rel_files[:max_files]

                        content = "\n".join(visible_files)
                        if len(rel_files) > max_files:
                            content += f"\n... truncated {len(rel_files) - max_files} more files"

                        print("\nDIRECTORY CONTENT:")
                        print("--------------------------------")
                        print(content)
                        print("--------------------------------\n")
                        last_step_result = f"READ directory '{path}' succeeded. Returned {len(visible_files)} paths."
                        if path.strip() in [".", "./", ""]:
                            preflight_done = True
                        last_action_success = True
                        if debug_mode:
                            debug_success_since_failure += 1
                        append_step_history(
                            "READ",
                            path,
                            "success",
                            f"Type: directory\nReturned paths:\n{truncate_for_history(content)}",
                        )
                    else:
                        content = read_file(target_path)

                        print("\nFILE CONTENT:")
                        print("--------------------------------")
                        print(content)
                        print("--------------------------------\n")
                        last_step_result = f"READ file '{path}' succeeded. Content length: {len(content)} characters."
                        last_action_success = True
                        if debug_mode:
                            debug_success_since_failure += 1
                        append_step_history(
                            "READ",
                            path,
                            "success",
                            f"Type: file\nContent:\n{truncate_for_history(content)}",
                        )
                except Exception as e:
                    error_message = str(e)
                    print(f"READ FAILED: {error_message}\n")
                    last_step_result = f"READ '{path}' failed with error: {error_message}"
                    last_action_success = False
                    debug_mode = True
                    last_failed_command = f"READ {path}"
                    last_error_message = error_message
                    append_step_history("READ", path, "failure", error_message)

            # WRITE FILE
            elif action.startswith("WRITE:"):

                executed_action_count += 1

                lines = action.split("\n")

                file_path = lines[0].split("WRITE:")[1].strip()

                normalized_file_path = file_path.replace("/", "\\")
                if "..\\" in normalized_file_path or normalized_file_path.startswith(".."):
                    last_step_result = f"WRITE rejected: path traversal is not allowed ('{file_path}')."
                    append_step_history("WRITE", file_path, "rejected", last_step_result)
                    print("WRITE REJECTED - UNSAFE PATH\n")
                    step_end = time.time()
                    print(f"STEP TIME: {round(step_end-step_start,2)} seconds\n")
                    continue

                if not preflight_done and prompt_requires_mutation:
                    last_step_result = "WRITE rejected: preflight directory context missing. Use READ: . before write operations."
                    append_step_history("WRITE", file_path, "rejected", last_step_result)
                    print("WRITE REJECTED - PREFLIGHT REQUIRED\n")
                    step_end = time.time()
                    print(f"STEP TIME: {round(step_end-step_start,2)} seconds\n")
                    continue

                content = "\n".join(lines[1:])

                print(f"WRITING FILE: {file_path}")

                print("\nCONTENT:")
                print("--------------------------------")
                print(content)
                print("--------------------------------\n")
                try:
                    write_file(os.path.join(cwd, file_path), content)

                    last_step_result = f"WRITE '{file_path}' succeeded. Wrote {len(content)} characters."
                    last_action_success = True
                    mutating_action_count += 1
                    if debug_mode:
                        debug_success_since_failure += 1
                    append_step_history(
                        "WRITE",
                        file_path,
                        "success",
                        f"Wrote {len(content)} chars\nContent:\n{truncate_for_history(content)}",
                    )

                    print("FILE UPDATED\n")
                except Exception as e:
                    error_message = str(e)
                    print(f"WRITE FAILED: {error_message}\n")
                    last_step_result = f"WRITE '{file_path}' failed with error: {error_message}"
                    last_action_success = False
                    debug_mode = True
                    last_failed_command = f"WRITE {file_path}"
                    last_error_message = error_message
                    append_step_history("WRITE", file_path, "failure", error_message)

            # DONE
            elif action.strip() == "DONE":

                done_rejection_reason = ""

                if executed_action_count == 0:
                    done_rejection_reason = "DONE rejected: No action has been executed yet."
                elif prompt_requires_mutation and not preflight_done:
                    done_rejection_reason = "DONE rejected: mutation task requires preflight directory understanding first."
                elif prompt_requires_mutation and mutating_action_count == 0:
                    done_rejection_reason = (
                        "DONE rejected: Task requires file/system changes but no mutating action has succeeded yet. "
                        "Navigation/list commands are not completion."
                    )
                elif requires_run_success and successful_run_count == 0:
                    done_rejection_reason = (
                        "DONE rejected: request implies run/start verification, but no command completed successfully yet."
                    )
                elif debug_mode and not last_action_success and debug_success_since_failure == 0:
                    done_rejection_reason = "DONE rejected: Debug mode active and no successful recovery step has occurred yet."

                if done_rejection_reason:
                    print(f"{done_rejection_reason}\n")
                    last_step_result = done_rejection_reason
                    append_step_history("DONE", "task", "rejected", done_rejection_reason)
                    step_end = time.time()
                    print(f"STEP TIME: {round(step_end-step_start,2)} seconds\n")
                    continue

                print("TASK COMPLETE\n")
                if context:
                    context.add_task_summary(
                        f"Task: {prompt[:80]} | actions={executed_action_count} | runs={successful_run_count} | debug={'on' if debug_mode else 'off'}"
                    )
                break

            # RESUME
            elif action.strip() == "RESUME":

                if debug_mode:
                    debug_mode = False
                    debug_success_since_failure = 0
                    last_step_result = "Debugger returned RESUME. Switched back to coder model."
                    print("DEBUG MODE CLEARED -> RETURNING TO CODER\n")
                else:
                    last_step_result = "Received RESUME while not in debug mode."
                    print("RESUME IGNORED (not in debug mode)\n")

            else:

                print("INVALID ACTION FORMAT — retrying...\n")

            step_end = time.time()

            print(f"STEP TIME: {round(step_end-step_start,2)} seconds\n")

    except KeyboardInterrupt:
        print("\n\n[Task interrupted by user - Ctrl+C]")
        print("Stopping task execution...\n")
        if context:
            context.add_task_summary(
                f"Task interrupted: {prompt[:80]} | actions={executed_action_count if 'executed_action_count' in locals() else 0}"
            )
        return

    total_end = time.time()

    print("\n===================================")
    print("TASK FINISHED")
    print(f"TOTAL TIME: {round(total_end-total_start,2)} seconds")
    print("===================================\n")