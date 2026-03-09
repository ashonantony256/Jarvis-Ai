import os
import sys
from agent import run_task
from router import choose_model
from ollama_client import get_available_models, run_chat_model
from context import JarvisContext
from memory_manager import SessionMemoryManager


def _session_memory_path():
    return os.path.join(os.path.expanduser("~"), ".jarvis", "session")


def _load_context(cwd):
    manager = SessionMemoryManager(_session_memory_path())
    snapshot = manager.load()

    context = JarvisContext(cwd=cwd)
    if snapshot:
        context.chat_history = snapshot.get("chat_history", [])[-20:]
        context.task_summaries = snapshot.get("task_summaries", [])[-15:]
        context.safety_mode = bool(snapshot.get("safety_mode", True))

    return context, manager


def _save_context(manager, context):
    manager.save(
        {
            "cwd": context.cwd,
            "chat_history": context.chat_history,
            "task_summaries": context.task_summaries,
            "safety_mode": context.safety_mode,
        }
    )


def run_chat(prompt, context, available_models):
    """Run a chat conversation with session context."""
    model = choose_model("chat", available_models=available_models)

    print(f"\n===================================")
    print(f"CHAT MODE - USING MODEL: {model}")
    print(f"===================================\n")

    response = run_chat_model(
        model,
        prompt,
        system_prompt=context.system_prompt,
        history=context.chat_history,
    )
    context.add_chat_turn(prompt, response)
    print(f"AI Response:\n{response}\n")

    print(f"===================================")
    print(f"CHAT TURN COMPLETE")
    print(f"===================================\n")

def main():
    # Use the current working directory where the command is run, not where the script is located
    cwd = os.getcwd()

    print(f"\nJarvis AI Assistant")
    print(f"Active in: {cwd}")
    print(
        "Commands: 'chat' for conversation mode, 'task' for task mode, "
        "'safe on', 'safe off', 'safe status', 'exit' or 'quit'"
    )
    print(f"Press Ctrl+C to force quit at any time\n")

    context, memory_manager = _load_context(cwd)
    available_models = get_available_models()

    chat_mode = False

    try:
        while True:
            if chat_mode:
                prompt = input("jarvis-chat> ")

                if prompt in ["exit", "quit", "task"]:
                    if prompt in ["exit", "quit"]:
                        break
                    chat_mode = False
                    context.mode = "task"
                    print("\nSwitched to task mode.\n")
                    continue

                run_chat(prompt, context, available_models)
                _save_context(memory_manager, context)
            else:
                prompt = input("jarvis-task> ")

                if prompt in ["exit", "quit"]:
                    break
                elif prompt == "chat":
                    chat_mode = True
                    context.mode = "chat"
                    print("\nSwitched to chat mode. Type 'task' to return to task mode.\n")
                    continue
                elif prompt == "safe on":
                    context.safety_mode = True
                    print("\nSafety mode is now ON.\n")
                    _save_context(memory_manager, context)
                    continue
                elif prompt == "safe off":
                    context.safety_mode = False
                    print("\nSafety mode is now OFF.\n")
                    _save_context(memory_manager, context)
                    continue
                elif prompt == "safe status":
                    print(f"\nSafety mode: {'ON' if context.safety_mode else 'OFF'}\n")
                    continue

                print(f"\nExecuting task: {prompt}")
                context.mode = "task"
                run_task(prompt, cwd, context=context, available_models=available_models)
                _save_context(memory_manager, context)

    except KeyboardInterrupt:
        print("\n\n[Jarvis interrupted by user - Ctrl+C]")
        print("Exiting...\n")
        _save_context(memory_manager, context)
        sys.exit(0)

    _save_context(memory_manager, context)


if __name__ == "__main__":
    main()