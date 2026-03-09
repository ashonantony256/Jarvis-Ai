import ollama
import time


def get_available_models():
    try:
        payload = ollama.list()
        models = payload.get("models", [])
        result = []
        for item in models:
            name = item.get("model") or item.get("name")
            if name:
                result.append(name)
        return result
    except Exception:
        return []


def _build_messages(prompt, system_prompt=None, history=None):
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})
    return messages


def run_model(model, prompt, system_prompt=None, history=None):

    print("\n==============================")
    print(f"MODEL STARTED: {model}")
    print("==============================")

    start = time.time()

    response = ollama.chat(
        model=model,
        messages=_build_messages(prompt, system_prompt=system_prompt, history=history),
    )

    end = time.time()

    print(f"MODEL FINISHED: {model}")
    print(f"TIME TAKEN: {round(end - start,2)} seconds")
    print("==============================\n")

    return response["message"]["content"]


def run_chat_model(model, prompt, system_prompt=None, history=None):
    """Run a chat model for conversational interaction"""
    print("\n==============================")
    print(f"CHAT MODEL STARTED: {model}")
    print("==============================")

    start = time.time()

    response = ollama.chat(
        model=model,
        messages=_build_messages(prompt, system_prompt=system_prompt, history=history),
    )

    end = time.time()

    print(f"CHAT MODEL FINISHED: {model}")
    print(f"TIME TAKEN: {round(end - start,2)} seconds")
    print("==============================\n")

    return response["message"]["content"]