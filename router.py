def choose_model(task):

    if task == "plan":
        return "gpt-oss:120b-cloud"

    if task == "debug":
        return "gpt-oss:120b-cloud"

    if task == "code":
        return "gpt-oss:120b-cloud"

    if task == "chat":
        return "gemma2:2b"

    return "gemma2:2b"