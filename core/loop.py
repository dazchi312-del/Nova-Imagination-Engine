from __future__ import annotations

import requests
from core.dispatcher import dispatch, TOOL_SCHEMA, DispatchError

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
MODEL = "llama-3.1-8b-instruct"
MAX_TOOL_ROUNDS = 5

SYSTEM_PROMPT = f"""You are Nova, a local AI agent with access to tools.
{TOOL_SCHEMA}
"""


def chat(messages: list[dict], temperature: float = 0.3) -> str:
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 1024,
        "stream": False,
    }
    response = requests.post(LM_STUDIO_URL, json=payload, timeout=60)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def run_loop(user_input: str, history: list[dict] | None = None) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_input})

    for round_num in range(MAX_TOOL_ROUNDS):
        nova_reply = chat(messages)
        tool_called, result = dispatch(nova_reply)

        if not tool_called:
            return nova_reply

        # Tool was called — feed result back to Nova
        messages.append({"role": "assistant", "content": nova_reply})
        messages.append({"role": "user", "content": f"[TOOL RESULT]\n{result}\n[/TOOL RESULT]"})

    return "[LOOP ERROR] Max tool rounds reached without final response."
