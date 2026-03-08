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
You are a coding agent.

You MUST respond only using these commands:

WRITE: <file_path>
<file content>

RUN: <terminal command>

READ: <file_path>

DONE

User request:
{prompt}

Important guidelines:
1. All file paths should be relative to the current working directory
2. When creating Python files, make sure the content is valid Python code
3. Break down complex tasks into smaller steps
"""

    plan = run_model(model, planning_prompt)

    print("PLAN GENERATED\n")

    # Track executed commands
    executed_commands = ""

    while True:

        print("STEP 2: Generating action")

        model = choose_model("code")

        action_prompt = f"""
You are a coding agent.

Respond with EXACTLY ONE command at a time:

WRITE: <file_path>
<file content>

RUN: <command>

READ: <file_path>

DONE

Current task:
{prompt}

Execution history:
{executed_commands}

Important guidelines:
1. All file paths should be relative to the current working directory
2. When creating Python files, make sure the content is valid Python code
3. Respond with exactly one command at a time
4. Only use DONE when the task is completely finished
"""

        action = run_model(model, action_prompt)

        print("ACTION RETURNED:")
        print(action)
        print()

        # Add this action to the execution history
        executed_commands += f"\n{action}"

        if action.startswith("RUN:"):

            cmd = action.replace("RUN:", "").strip()

            print(f"EXECUTING COMMAND: {cmd}")

            result = run_command(cmd, cwd)

            if result["code"] != 0:

                print("\nERROR DETECTED -> DEBUGGING\n")

                debug_prompt = f"""
The following command failed.

Command:
{cmd}

Error:
{result['stderr']}

Respond with a FIX using the allowed commands:

WRITE: <file_path>
<content>

RUN: <command>

READ: <file_path>

DONE
"""

                model = choose_model("debug")

                plan = run_model(model, debug_prompt)

            else:
                print("COMMAND SUCCESS\n")


        elif action.startswith("READ:"):

            path = action.replace("READ:", "").strip()

            print(f"READING FILE: {path}")

            content = read_file(os.path.join(cwd, path))

            print(f"FILE CONTENT:\n{content}\n")

            executed_commands += f"\nFile content:\n{content}"


        elif action.startswith("WRITE:"):

            lines = action.strip().split("\n")

            # First line contains "WRITE: <file_path>"
            file_path = lines[0].replace("WRITE:", "").strip()

            # Content is everything after the first line until we hit another command
            content_lines = []
            for line in lines[1:]:
                if line.startswith(("RUN:", "READ:", "WRITE:", "DONE")):
                    break
                content_lines.append(line)

            content = "\n".join(content_lines)

            print(f"WRITING FILE: {file_path}")
            print(f"CONTENT:\n{content}\n")

            write_file(os.path.join(cwd, file_path), content)

            executed_commands += f"\nWRITE: {file_path}\n{content}"

            print("FILE UPDATED\n")


        elif action.startswith("DONE"):

            break

        else:

            print("INVALID ACTION FORMAT — retrying...\n")

    total_end = time.time()

    print("\n===================================")
    print("TASK FINISHED")
    print(f"TOTAL TIME: {round(total_end-total_start,2)} seconds")
    print("===================================\n")