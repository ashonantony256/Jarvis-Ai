import os
from agent import run_task

def main():

    cwd = os.getcwd()

    print(f"\nJarvis active in: {cwd}\n")

    while True:

        prompt = input("jarvis> ")

        if prompt in ["exit", "quit"]:
            break

        run_task(prompt, cwd)


if __name__ == "__main__":
    main()