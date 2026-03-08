import time
import os

from router import choose_model
from ollama_client import run_model
from tools.terminal import run_command
from tools.files import read_file, write_file


def run_task(prompt, cwd):

    print("\n===================================")
    print("TASK STARTED")
    print("===================================\n")

    total_start = time.time()

    # STEP 1: Planning
    print("STEP 1: Planning task")

    model = choose_model("plan")

    planning_prompt = f"""
You are a planning agent.You are giving intstuctions to another agent who can execute cmd commands and write code,etc.
Create a step-by-step plan to complete the following task:

User request:
{prompt}

Important guidelines:
1. All file paths should be relative to the current working directory
2. Break down complex tasks into smaller steps
3. Be as detailed as possible
4. Use numbered steps
5. Do NOT include commands or code
"""

    plan = run_model(model, planning_prompt)

    print("\nPLAN:")
    print("===================================")
    print(plan)
    print("===================================\n")

    executed_commands = ""
    step_count = 0

    while True:

        step_count += 1

        if step_count > 50:
            print("STOPPING: Too many steps")
            break

        step_start = time.time()

        print("STEP 2: Generating action")

        model = choose_model("code")

        action_prompt = f"""
You are a coding agent.

Respond with EXACTLY ONE command.

Allowed commands:

WRITE: <file_path>
<file content>

RUN: <command>

READ: <file_path>

DONE

Current task plan:
{plan}

Execution history:
{executed_commands}

Rules:
1. Only ONE command per response
2. No explanations
3. Paths must be relative
"""

        raw_action = run_model(model, action_prompt)

        print("\nRAW MODEL OUTPUT:")
        print("--------------------------------")
        print(raw_action)
        print("--------------------------------\n")

        action = raw_action.strip().replace("```", "")

        # RUN COMMAND
        if "RUN:" in action:

            cmd = action.split("RUN:")[1].strip().split("\n")[0]

            print(f"EXECUTING COMMAND: {cmd}")

            result = run_command(cmd, cwd)

            executed_commands += f"""
RUN: {cmd}

OUTPUT:
{result.get('stdout','')}

ERROR:
{result.get('stderr','')}
"""

            if result["code"] != 0:

                print("\nERROR DETECTED -> DEBUGGING\n")

                debug_prompt = f"""
The following command failed.

Command:
{cmd}

Error:
{result['stderr']}

Respond with ONE command using:

WRITE: <file_path>
<content>

RUN: <command>

READ: <file_path>

DONE
"""

                model = choose_model("debug")

                debug_fix = run_model(model, debug_prompt)

                print("DEBUG RESPONSE:")
                print(debug_fix)

                executed_commands += f"\nDEBUG RESPONSE:\n{debug_fix}\n"

            else:
                print("COMMAND SUCCESS\n")

        # READ FILE
        elif "READ:" in action:

            path = action.split("READ:")[1].strip().split("\n")[0]

            print(f"READING FILE: {path}")

            content = read_file(os.path.join(cwd, path))

            print("\nFILE CONTENT:")
            print("--------------------------------")
            print(content)
            print("--------------------------------\n")

            executed_commands += f"""
READ: {path}

CONTENT:
{content}
"""

        # WRITE FILE
        elif "WRITE:" in action:

            lines = action.split("\n")

            file_path = lines[0].split("WRITE:")[1].strip()

            content = "\n".join(lines[1:])

            print(f"WRITING FILE: {file_path}")

            print("\nCONTENT:")
            print("--------------------------------")
            print(content)
            print("--------------------------------\n")

            write_file(os.path.join(cwd, file_path), content)

            executed_commands += f"""
WRITE: {file_path}

{content}
"""

            print("FILE UPDATED\n")

        # DONE
        elif "DONE" in action:

            print("TASK COMPLETE\n")
            break

        else:

            print("INVALID ACTION FORMAT — retrying...\n")

        step_end = time.time()

        print(f"STEP TIME: {round(step_end-step_start,2)} seconds\n")

    total_end = time.time()

    print("\n===================================")
    print("TASK FINISHED")
    print(f"TOTAL TIME: {round(total_end-total_start,2)} seconds")
    print("===================================\n")