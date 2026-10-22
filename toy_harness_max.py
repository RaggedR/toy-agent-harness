#!/usr/bin/env python3
"""
The toy harness, running on a Claude Max subscription.

No API key. Inference comes from headless Claude Code (`claude -p`) with its
own tools stripped off (`--tools ""`), which turns it into a plain
prompt-in / text-out endpoint. That is Claude Code being used as Claude Code,
so it is covered by your subscription.

    python3 toy_harness_max.py "how many Python files are in this directory?"

The catch, and the lesson: a text endpoint has no `tool_use` blocks. So this
harness has to invent its own tool protocol in prose and parse it back out.
That is how every agent worked before tool use was trained into the models
(the 2023 "ReAct" pattern), and living with it for ten minutes shows you
exactly what the structured blocks in toy_harness.py buy you for free.

Compare the two files side by side:

    toy_harness.py       messages: list[dict]   tool_use blocks   API key
    toy_harness_max.py   transcript: str        parsed prose      Max plan
"""

import os
import re
import subprocess
import sys

MODEL = os.environ.get("TOY_MODEL", "")   # "" = whatever `claude` defaults to
MAX_TURNS = 12
MAX_DEPTH = 2


# ------------------------------------------------------- 1. THE TOOL PROTOCOL
# With no tool_use blocks, the protocol IS the prompt. Every tool description,
# every argument, and the output grammar all have to live in this string -- and
# the model can violate it, because nothing enforces it.

PROTOCOL = """\
You are a small command-line agent. You work by emitting ONE line at a time,
in one of exactly three forms, and nothing else:

    BASH: <a shell command>
    SPAWN: <a complete, self-contained task for a fresh sub-agent>
    ANSWER: <your final answer, one or two sentences>

Rules:
- Emit exactly one line. No preamble, no explanation, no markdown fences.
- BASH returns the command's combined stdout and stderr.
- SPAWN delegates to a sub-agent that knows NOTHING about this conversation,
  and returns only its final answer. Use it for search-heavy sub-tasks whose
  intermediate output you don't need to see.
- Emit ANSWER as soon as you can answer. Do not narrate.
"""


# ------------------------------------------------------------------ 2. GATE
# Unchanged from toy_harness.py. The gate does not care where the intent came
# from -- structured block or parsed prose, it sees the same command string.

DENY = ("rm -rf", "sudo", "mkfs", ":(){", "> /dev/", "curl", "git push")
ALLOW = ("ls", "cat", "head", "tail", "wc", "grep", "rg", "find", "pwd", "echo")


def check_permission(command):
    if any(bad in command for bad in DENY):
        return f"Denied by policy: {command!r} matches a blocked pattern."
    if command.split() and command.split()[0] in ALLOW:
        return None
    reply = input(f"\n  ⚠  allow `{command}` ? [y/N] ").strip().lower()
    return None if reply == "y" else "The user declined to run this command."


# ------------------------------------------------------------- 3. INFERENCE
# The model call. Note what is NOT here: no message array, no roles, no
# content blocks. We hand over one string and get one string back. All the
# structure the API gave us, we now have to impose ourselves.

def complete(prompt):
    cmd = ["claude", "-p", prompt, "--tools", ""]
    if MODEL:
        cmd += ["--model", MODEL]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"claude exited {r.returncode}: {r.stderr.strip()[:300]}")
    return r.stdout.strip()          # stderr is dropped: it carries settings warnings


def run_bash(command):
    r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)
    return (r.stdout + r.stderr).strip() or "(no output)"


# ------------------------------------------------------------------ 4. LOOP
# Structurally identical to toy_harness.py. Only two things differ: the
# transcript is a string rather than a list of typed messages, and the step
# that reads the model's intent is a regex rather than a field access.

def run_agent(task, depth=0, log=print):
    pad = "  " * depth
    log(f"{pad}┌─ agent(depth={depth}): {task[:70]}")

    # TRANSCRIPT, with nowhere to hide. Each turn we rebuild this whole string
    # and re-send it: the protocol, the task, and every observation so far.
    # The API version does exactly this; here you can see the bytes.
    transcript = f"{PROTOCOL}\nTASK: {task}\n"
    if depth >= MAX_DEPTH:
        transcript += "\nNOTE: SPAWN is unavailable at this depth. Do the work yourself.\n"

    for turn in range(MAX_TURNS):
        line = complete(transcript)
        log(f"{pad}│  {line[:100]}")

        # Parsing prose is where this design leaks. A model that answers with
        # "Let me check: BASH: ls" or forgets the prefix entirely produces a
        # turn that silently does nothing -- no error, no tool run, and the
        # junk stays in the transcript and skews every later turn. Structured
        # tool_use blocks exist precisely to delete this failure mode.
        m = re.match(r"\s*(BASH|SPAWN|ANSWER)\s*:\s*(.*)", line, re.S)
        if not m:
            transcript += (
                f"\nYOU SAID: {line}\n"
                "OBSERVATION: that was not a valid line. Emit exactly one line "
                "beginning BASH:, SPAWN:, or ANSWER:.\n"
            )
            continue

        verb, arg = m.group(1), m.group(2).strip()

        if verb == "ANSWER":
            log(f"{pad}└─ done ({turn + 1} turns)")
            return arg

        if verb == "BASH":
            refusal = check_permission(arg)                        # GATE
            observation = refusal if refusal else run_bash(arg)
        else:                                                      # SPAWN
            if depth + 1 > MAX_DEPTH:
                observation = "Error: maximum delegation depth reached."
            else:
                # Same recursion as the API version: a sub-agent is this
                # function with a fresh transcript. Its turns never enter
                # ours -- only the string it returns does.
                observation = run_agent(arg, depth=depth + 1, log=log)

        log(f"{pad}│  ← {observation[:80]!r}")

        # The harness speaking back to the model. In toy_harness.py this was a
        # `user` message holding tool_result blocks; here it is text appended
        # to a string. Same move, less ceremony, more ways to go wrong.
        transcript += f"\n{verb}: {arg}\nOBSERVATION: {observation}\n"

    log(f"{pad}└─ hit the {MAX_TURNS}-turn cap")
    return "Turn limit reached without a final answer."


if __name__ == "__main__":
    if subprocess.run(["which", "claude"], capture_output=True).returncode != 0:
        sys.exit("`claude` not found on PATH — this backend needs the Claude Code CLI.")
    prompt = " ".join(sys.argv[1:]) or "Summarise what is in the current directory."
    print("\n" + run_agent(prompt) + "\n")
