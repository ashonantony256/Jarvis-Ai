from ollama_client import run_model
from router import choose_model
from tools.terminal import run_command


def run_task(prompt):

    model = choose_model("plan")

    plan = run_model(model, prompt)

    while True:

        model = choose_model("code")

        action = run_model(model, plan)

        if action.startswith("RUN:"):

            cmd = action.replace("RUN:", "").strip()

            result = run_command(cmd)

            if result["code"] != 0:

                model = choose_model("debug")

                fix_prompt = f"""
                Command failed.

                Command:
                {cmd}

                Error:
                {result['stderr']}

                Fix the problem and output the next command.
                """

                plan = run_model(model, fix_prompt)

            else:
                print(result["stdout"])
                break