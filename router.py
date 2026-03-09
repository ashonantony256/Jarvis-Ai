TASK_MODEL_PREFERENCES = {
    "plan": ["gpt-oss:120b-cloud","qwen2.5-coder:3b", "phi3:mini", "gemma2:2b"],
    "debug": ["gpt-oss:120b-cloud","deepseek-coder:6.7b", "qwen2.5-coder:3b", "phi3:mini"],
    "code": ["gpt-oss:120b-cloud","deepseek-coder:6.7b", "qwen2.5-coder:3b", "phi3:mini"],
    "chat": ["gpt-oss:120b-cloud","gemma2:2b", "phi3:mini", "qwen2.5-coder:3b"],
}


def choose_model(task, available_models=None):
    preferred = TASK_MODEL_PREFERENCES.get(task, TASK_MODEL_PREFERENCES["chat"])
    if not available_models:
        return preferred[0]

    available_set = set(available_models)
    for model_name in preferred:
        if model_name in available_set:
            return model_name

    # As a last resort, pick any available model to avoid hard failure.
    if available_models:
        return available_models[0]

    return preferred[0]