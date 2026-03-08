import time

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
"""

    plan = run_model(model, planning_prompt)

    print("PLAN GENERATED\n")

    while True:

        print("STEP 2: Generating action")

        model = choose_model("code")

        action_prompt = f"""
You are a coding agent.

Only respond with one of these commands:

WRITE: <file_path>
<file content>

RUN: <command>

READ: <file_path>

DONE

Current task:
{plan}
"""

        action = run_model(model, action_prompt)

        print("ACTION RETURNED:")
        print(action)
        print()

        if action.startswith("RUN:"):

            cmd = action.replace("RUN:", "").strip()

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

            content = read_file(f"{cwd}/{path}")

            plan = f"File content:\n{content}"


        elif action.startswith("WRITE:"):

            parts = action.split("\n", 1)

            file_path = parts[0].replace("WRITE:", "").strip()

            content = parts[1] if len(parts) > 1 else ""

            write_file(f"{cwd}/{file_path}", content)

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