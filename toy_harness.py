#!/usr/bin/env python3
"""
A toy agent harness, in one file.

Two tools: `bash` (run a shell command) and `spawn_agent` (delegate to a
sub-agent). Everything else is the loop, the transcript, and the gate.

    export ANTHROPIC_API_KEY=...        # or: ant auth login
    pip install anthropic
    python toy_harness.py "how many Python files are in this directory?"

The five concepts, made concrete:

    HARNESS    this file. It owns everything; the model owns nothing.
    TRANSCRIPT the `messages` list. The only memory that exists.
    LOOP       run_agent(). Tool results go back as *user* messages.
    BUDGET     a token count and a turn cap. Sub-agents exist to protect it.
    GATE       check_permission(). Runs between intent and execution.
"""

import json
import os
import subprocess
import sys

import anthropic

# Override with e.g. TOY_MODEL=claude-haiku-4-5 to experiment more cheaply.
# The loop is identical whichever model you point it at.
MODEL = os.environ.get("TOY_MODEL", "claude-opus-5")
MAX_TURNS = 12          # BUDGET: stop a runaway loop
MAX_DEPTH = 2           # BUDGET: sub-agents may not spawn sub-agents forever


# ---------------------------------------------------------------- 1. TOOLS
# A tool is a name, a prose description, and a JSON Schema. With strict=True
# the decoder cannot emit input that violates the schema. The description
# is the whole user interface: it is the only thing the model reads when
# deciding whether to call this. Write it for the model, not for the reader.

BASH_TOOL = {
    "name": "bash",
    "strict": True,          # guarantees `input` validates against the schema
    "description": (
        "Run a shell command and return its combined stdout and stderr. "
        "Use this to inspect files, search text, and check state. "
        "The working directory persists between calls."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The shell command to run."}
        },
        "required": ["command"],
        "additionalProperties": False,
    },
}

SPAWN_TOOL = {
    "name": "spawn_agent",
    "strict": True,
    "description": (
        "Delegate a self-contained task to a sub-agent and get back only its "
        "final answer. The sub-agent starts with NO knowledge of this "
        "conversation, so the task description must be complete on its own. "
        "Use this when a task needs a lot of searching whose intermediate "
        "output you do not need to see."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "The complete, self-contained task for the sub-agent.",
            }
        },
        "required": ["task"],
        "additionalProperties": False,
    },
}


# ----------------------------------------------------------------- 2. GATE
# Deterministic code between `tool_use` and execution. The model cannot
# route around this, which is what makes it different from an instruction.

DENY = ("rm -rf", "sudo", "mkfs", ":(){", "> /dev/", "curl", "git push")
ALLOW = ("ls", "cat", "head", "tail", "wc", "grep", "rg", "find", "pwd", "echo")


def check_permission(name, args):
    """Return None to allow, or a string explaining the refusal."""
    if name == "spawn_agent":
        # Delegating is harmless in itself: the child runs this same gate.
        return None

    if name == "bash":
        cmd = args["command"]
        if any(bad in cmd for bad in DENY):
            return f"Denied by policy: {cmd!r} matches a blocked pattern."
        words = cmd.split()
        if words and words[0] in ALLOW:
            return None
        reply = input(f"\n  ⚠  allow `{cmd}` ? [y/N] ").strip().lower()
        return None if reply == "y" else "The user declined to run this command."

    # Fail closed: a tool with no policy is refused, not waved through.
    return f"No policy for tool {name!r}."


# ------------------------------------------------------------ 3. EXECUTION

def run_bash(command):
    r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)
    return (r.stdout + r.stderr).strip() or "(no output)"


def dispatch(client, name, args, depth, log):
    """Execute one tool call and return its result as a string."""
    if name == "bash":
        return run_bash(args["command"])
    if name == "spawn_agent":
        if depth >= MAX_DEPTH:
            return "Error: maximum delegation depth reached. Do this work yourself."
        # THE WHOLE TRICK: a sub-agent is this same function, called with a
        # fresh transcript. Its tool calls never enter the parent's messages
        # list -- only the string returned here does. That is why delegation
        # actually saves context, and why it cannot see our conversation.
        return run_agent(client, args["task"], depth=depth + 1, log=log)
    return f"Error: no such tool {name!r}."


# ------------------------------------------------------------------ 4. LOOP

def run_agent(client, task, depth=0, log=print):
    pad = "  " * depth
    log(f"{pad}┌─ agent(depth={depth}): {task[:70]}")

    # TRANSCRIPT. Rebuilt and re-sent in full on every single API call.
    messages = [{"role": "user", "content": task}]
    tools = [BASH_TOOL] + ([SPAWN_TOOL] if depth < MAX_DEPTH else [])
    spent = 0

    for turn in range(MAX_TURNS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=(
                "You are a small command-line agent. Investigate with the "
                "tools available, then answer in one or two sentences. "
                "Your final message is the return value -- no preamble."
            ),
            tools=tools,
            messages=messages,
        )
        spent += response.usage.output_tokens

        # Echo the assistant turn back VERBATIM. `response.content` may hold
        # thinking blocks alongside text and tool_use; appending the list
        # whole keeps them intact. Rebuilding it by hand loses them.
        messages.append({"role": "assistant", "content": response.content})

        for block in response.content:
            if block.type == "text" and block.text.strip():
                log(f"{pad}│  {block.text.strip()[:100]}")

        if response.stop_reason != "tool_use":
            final = "".join(b.text for b in response.content if b.type == "text")
            log(f"{pad}└─ done ({turn + 1} turns, {spent} output tokens)")
            return final.strip()

        # Every tool_use block needs exactly one tool_result, and they all go
        # back in ONE user message. Splitting them teaches the model to stop
        # requesting parallel calls.
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            log(f"{pad}│  → {block.name}({json.dumps(block.input)[:80]})")

            refusal = check_permission(block.name, block.input)          # GATE
            if refusal:
                out, is_error = refusal, True
            else:
                try:
                    out, is_error = dispatch(client, block.name, block.input, depth, log), False
                except Exception as exc:
                    out, is_error = f"Tool raised: {exc}", True

            log(f"{pad}│  ← {out[:80]!r}")
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,     # must match, or the API 400s
                "content": out,
                "is_error": is_error,
            })

        # The harness impersonating the user. This is the mechanism of agency:
        # from inside, the filesystem and the human are the same channel.
        messages.append({"role": "user", "content": results})

    log(f"{pad}└─ hit the {MAX_TURNS}-turn cap")
    return "Turn limit reached without a final answer."


if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]) or "Summarise what is in the current directory."
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "No ANTHROPIC_API_KEY set. This calls the Messages API, which bills\n"
            "per token against credits from console.anthropic.com. A Claude Max\n"
            "subscription is a separate product and is not licensed for this;\n"
            "use toy_harness_max.py to run on Max instead. Otherwise:\n"
            "    export ANTHROPIC_API_KEY=sk-ant-...\n",
            file=sys.stderr,
        )
        sys.exit(1)
    print("\n" + run_agent(anthropic.Anthropic(), prompt) + "\n")
