def choose_model(task):

    if task == "plan":
        return "phi3:mini"

    if task == "debug":
        return "deepseek-coder:6.7b"

    if task == "code":
        return "qwen2.5-coder:3b"

    if task == "chat":
        return "gemma2:2b"

    return "gemma2:2b"