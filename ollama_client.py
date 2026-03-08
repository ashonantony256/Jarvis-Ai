import ollama
import time


def run_model(model, prompt):

    print("\n==============================")
    print(f"MODEL STARTED: {model}")
    print("==============================")

    start = time.time()

    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )

    end = time.time()

    print(f"MODEL FINISHED: {model}")
    print(f"TIME TAKEN: {round(end - start,2)} seconds")
    print("==============================\n")

    return response["message"]["content"]


def run_chat_model(model, prompt):
    """Run a chat model for conversational interaction"""
    print("\n==============================")
    print(f"CHAT MODEL STARTED: {model}")
    print("==============================")

    start = time.time()

    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )

    end = time.time()

    print(f"CHAT MODEL FINISHED: {model}")
    print(f"TIME TAKEN: {round(end - start,2)} seconds")
    print("==============================\n")

    return response["message"]["content"]