import os
import sys
from agent import run_task
from router import choose_model
from ollama_client import run_model, run_chat_model

def run_chat(prompt):
    """Run a chat conversation with the gemma2:2b model"""
    model = "gemma2:2b"

    print(f"\n===================================")
    print(f"CHAT MODE - USING MODEL: {model}")
    print(f"===================================\n")

    response = run_chat_model(model, prompt)
    print(f"AI Response:\n{response}\n")

    print(f"===================================")
    print(f"CHAT TURN COMPLETE")
    print(f"===================================\n")

def main():
    # Use the current working directory where the command is run, not where the script is located
    cwd = os.getcwd()

    print(f"\nJarvis AI Assistant")
    print(f"Active in: {cwd}")
    print(f"Commands: 'chat' for conversation mode, 'task' for task mode, 'exit' or 'quit' to exit")
    print(f"Press Ctrl+C to force quit at any time\n")

    chat_mode = False

    try:
        while True:
            if chat_mode:
                prompt = input("jarvis-chat> ")

                if prompt in ["exit", "quit", "task"]:
                    if prompt in ["exit", "quit"]:
                        break
                    chat_mode = False
                    print("\nSwitched to task mode.\n")
                    continue

                run_chat(prompt)
            else:
                prompt = input("jarvis-task> ")

                if prompt in ["exit", "quit"]:
                    break
                elif prompt == "chat":
                    chat_mode = True
                    print("\nSwitched to chat mode. Type 'task' to return to task mode.\n")
                    continue

                print(f"\nExecuting task: {prompt}")
                run_task(prompt, cwd)

    except KeyboardInterrupt:
        print("\n\n[Jarvis interrupted by user - Ctrl+C]")
        print("Exiting...\n")
        sys.exit(0)


if __name__ == "__main__":
    main()