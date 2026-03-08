def choose_model(task):

    if "debug" in task:
        return "deepseek-coder:6.7b"

    if "plan" in task:
        return "phi3:mini"

    return "qwen2.5-coder:3b"