# Jarvis-Ai

A local AI assistant that uses Ollama models for two modes:

- `task` mode: plans and executes coding/file/terminal steps
- `chat` mode: conversational interaction

Recent improvements include shared session context between chat/task, model fallback selection, safety-mode command blocking for risky operations, and stricter task completion checks.

## Project Structure

- `jarvis.py` - CLI entry point and mode switching (`task`/`chat`)
- `agent.py` - task loop (plan -> action -> execute)
- `router.py` - model selection by task type
- `ollama_client.py` - wrapper around Ollama chat calls
- `context.py` - shared runtime context (identity, chat/task session state)
- `memory_manager.py` - lightweight session persistence (`~/.jarvis/session/`)
- `tools/files.py` - file read/write/list helpers
- `tools/terminal.py` - terminal command execution helper
- `jarvis.bat` - Windows launcher

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com/) installed and running
- Python package:

```bash
pip install ollama
```

- Preferred models in `router.py` (fallback is automatic based on what is installed in Ollama):

```text
phi3:mini
qwen2.5-coder:3b
deepseek-coder:6.7b
gemma2:2b
```

Pull models (example):

```bash
ollama pull phi3:mini
ollama pull qwen2.5-coder:3b
ollama pull deepseek-coder:6.7b
ollama pull gemma2:2b
```

## Run

From the repository root:

```bash
python jarvis.py
```

On Windows, you can also use:

```bat
jarvis.bat
```

## Global `jarvis` Command (Windows)

To run Jarvis from any directory as `jarvis`, run this once from the repo root:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-jarvis-command.ps1
```

Then open a new terminal and run:

```powershell
jarvis
```

## Usage

When started, Jarvis shows two modes:

- `jarvis-task>` for autonomous task execution
- `jarvis-chat>` for conversation mode

Commands:

- `chat` - switch from task mode to chat mode
- `task` - switch from chat mode back to task mode
- `safe on` - block risky commands in task execution
- `safe off` - allow risky commands in task execution
- `safe status` - show current safety mode state
- `exit` or `quit` - stop Jarvis

## Notes

- Task mode executes shell commands with `shell=True` and writes files directly.
- Use in trusted directories and review prompts carefully.
- Current working directory is where you launch `jarvis.py` from.
- Task mode now performs preflight directory-awareness for mutation workflows and may reject `DONE` when required run/start verification has not succeeded.
- Session memory is persisted for continuity between restarts at `~/.jarvis/session/session-memory.json`.
