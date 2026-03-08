import time
import os

from router import choose_model
from ollama_client import run_model
from tools.terminal import run_command
from tools.files import read_file, write_file, list_files


def run_task(prompt, cwd):

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

    def parse_directory_change(cmd):
        """Parse simple directory-change commands and return target path if present."""
        raw = (cmd or "").strip()
        lower = raw.lower()

        prefixes = ["cd ", "chdir ", "set-location "]
        chosen_prefix = ""
        for prefix in prefixes:
            if lower.startswith(prefix):
                chosen_prefix = prefix
                break

        if not chosen_prefix:
            return None

        target = raw[len(chosen_prefix) :].strip()
        if not target:
            return None

        if (target.startswith('"') and target.endswith('"')) or (
            target.startswith("'") and target.endswith("'")
        ):
            target = target[1:-1]

        return target

    def resolve_next_cwd(current_cwd, target):
        """Resolve next working directory from a cd-like target."""
        if not target:
            return current_cwd

        expanded = os.path.expandvars(target)
        if os.path.isabs(expanded):
            return os.path.abspath(expanded)
        return os.path.abspath(os.path.join(current_cwd, expanded))

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

        model = choose_model("plan")

        planning_prompt = f"""
You are a planning agent. Create a SHORT, SIMPLE plan for another AI coding agent who can run terminal commands,Read/Write files, and write code.

Current directory: {cwd}

User request:
{prompt}

IMPORTANT:
1. Keep plans SHORT and SIMPLE
2. Do NOT include verification or confirmation steps
3. For file deletion: just delete the file, don't verify
4. For file creation: just create the file
5. Trust that exit code 0 means success
6. Use numbered steps
7. Do NOT include commands or code in the plan - just plain language descriptions of the steps needed to complete the task
"""

        plan = run_model(model, planning_prompt)

        print("\nPLAN:")
        print("===================================")
        print(plan)
        print("===================================\n")

        executed_commands = ""
        last_step_result = "No steps executed yet."
        pending_action = ""
        current_cwd = os.path.abspath(cwd)
        debug_mode = False
        last_failed_command = ""
        last_error_message = ""
        step_count = 0
        executed_action_count = 0
        mutating_action_count = 0
        debug_success_since_failure = 0
        last_action_success = False

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
                model = choose_model("debug" if debug_mode else "code")

                if debug_mode:
                    action_prompt = f"""
You are a debugging agent. Stay in debugging mode and fix the task.

ORIGINAL USER REQUEST:
{prompt}

TASK PLAN:
{plan}

FULL EXECUTION HISTORY:
{executed_commands}

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
"""

                raw_action = run_model(model, action_prompt)
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

                print(f"EXECUTING COMMAND: {cmd}")

                result = run_command(cmd, current_cwd)

                last_step_result = f"""Action: RUN
Command: {cmd}
Exit Code: {result.get('code', 'unknown')}
STDOUT:
{result.get('stdout', '')}
STDERR:
{result.get('stderr', '')}
"""

                run_details = f"""Exit Code: {result.get('code', 'unknown')}
STDOUT:
{truncate_for_history(result.get('stdout', ''))}
STDERR:
{truncate_for_history(result.get('stderr', ''))}
"""

                if result["code"] != 0:

                    print("\nERROR DETECTED -> DEBUGGING\n")
                    debug_mode = True
                    last_failed_command = cmd
                    last_error_message = result.get("stderr", "")
                    last_action_success = False
                    append_step_history("RUN", cmd, "failure", run_details)

                else:
                    print("COMMAND SUCCESS\n")
                    cd_target = parse_directory_change(cmd)
                    if cd_target:
                        next_cwd = resolve_next_cwd(current_cwd, cd_target)
                        if os.path.isdir(next_cwd):
                            current_cwd = next_cwd
                            print(f"WORKING DIRECTORY UPDATED: {current_cwd}\n")
                        else:
                            print(f"DIRECTORY NOT FOUND AFTER CD: {next_cwd}\n")
                    last_action_success = True
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

                target_path = os.path.join(current_cwd, path)

                try:
                    if os.path.isdir(target_path):
                        files = list_files(target_path)
                        rel_files = [os.path.relpath(file_path, current_cwd) for file_path in files]
                        rel_files = [
                            rel_path
                            for rel_path in rel_files
                            if not rel_path.startswith(".git\\")
                            and "__pycache__" not in rel_path
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

                content = "\n".join(lines[1:])

                print(f"WRITING FILE: {file_path}")

                print("\nCONTENT:")
                print("--------------------------------")
                print(content)
                print("--------------------------------\n")
                try:
                    write_file(os.path.join(current_cwd, file_path), content)

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
                elif prompt_requires_mutation and mutating_action_count == 0:
                    done_rejection_reason = (
                        "DONE rejected: Task requires file/system changes but no mutating action has succeeded yet. "
                        "Navigation/list commands are not completion."
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
        return

    total_end = time.time()

    print("\n===================================")
    print("TASK FINISHED")
    print(f"TOTAL TIME: {round(total_end-total_start,2)} seconds")
    print("===================================\n")