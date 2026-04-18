# core/loop.py
# v0.9.0 — task/project commands, max_tokens 1024, reflector context, RAG debug

import json
import re
import os
import requests
from datetime import datetime
from core.identity import NOVA_IDENTITY
from core.memory import init_db, new_session, close_session, log_turn, get_session_context
from core.Obsidian_bridge import ObsidianBridge

with open("nova_config.json") as f:
    cfg = json.load(f)

PRIMARY_URL   = cfg["base_url"]
PRIMARY_MODEL = cfg["primary_model"]
REFLECT_URL   = cfg["reflector"]["base_url"]
REFLECT_MODEL = cfg["reflector"]["model"]

THRESHOLD = 0.75
PRIMARY_TIMEOUT   = 180
REFLECTOR_TIMEOUT = 30

VAULT_PATH = r"C:\Users\dazch\nova\vault"

bridge = ObsidianBridge()

# ── Task Helpers ──────────────────────────────────────────────────────────────

def get_tasks_path():
    return os.path.join(VAULT_PATH, "projects", "tasks.md")

def load_tasks():
    path = get_tasks_path()
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    tasks = []
    for line in lines:
        line = line.strip()
        if line.startswith("- [ ]") or line.startswith("- [x]"):
            tasks.append(line)
    return tasks

def save_tasks(tasks):
    path = get_tasks_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    header = f"# Tasks\n_Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(header)
        for t in tasks:
            f.write(t + "\n")

# ── Command Handler ───────────────────────────────────────────────────────────

def handle_command(cmd, session_id):
    raw = cmd.strip()
    lower = raw.lower()

    if lower == "/status":
        info = bridge.status()
        print(f"\n[Status] Session: {session_id}")
        print(f"[Status] Vault: {info.get('vault_path')}")
        print(f"[Status] Notes indexed: {info.get('note_count')}")
        print(f"[Status] Primary model: {PRIMARY_MODEL} @ {PRIMARY_URL}")
        print(f"[Status] Reflector model: {REFLECT_MODEL} @ {REFLECT_URL}")
        print(f"[Status] Threshold: {THRESHOLD} | Primary timeout: {PRIMARY_TIMEOUT}s\n")
        return True

    if lower == "/debug":
        print("\n[Debug] Triggering vault index summary...")
        bridge.debug_summary()
        return True

    if lower == "/save":
        print("[Save] Session is auto-saved each turn. Nothing additional to flush.\n")
        return True

    if lower == "/clear":
        print("[Clear] Clearing terminal display...\n")
        os.system("cls" if os.name == "nt" else "clear")
        return True

    if lower == "/help":
        print("\nCommands:")
        print("  /status             — show system info and vault stats")
        print("  /debug              — print vault index summary")
        print("  /save               — confirm session is saved")
        print("  /clear              — clear terminal")
        print("  /help               — show this list")
        print("  /task add <text>    — add a task to projects/tasks.md")
        print("  /task list          — list all tasks")
        print("  /task done <number> — mark task complete by number")
        print("  /project new <name> — create a new project file")
        print("  /project status     — list all project files")
        print("  exit                — end session\n")
        return True

    # ── Task Commands ─────────────────────────────────────────────────────────

    if lower.startswith("/task add "):
        text = raw[len("/task add "):].strip()
        if not text:
            print("[Task] No task text provided.\n")
            return True
        tasks = load_tasks()
        tasks.append(f"- [ ] {text}")
        save_tasks(tasks)
        print(f"[Task] Added: {text}\n")
        return True

    if lower == "/task list":
        tasks = load_tasks()
        if not tasks:
            print("[Task] No tasks found. Use /task add <text> to create one.\n")
            return True
        print("\n[Tasks]")
        for i, t in enumerate(tasks, 1):
            print(f"  {i}. {t}")
        print()
        return True

    if lower.startswith("/task done "):
        try:
            num = int(raw[len("/task done "):].strip())
            tasks = load_tasks()
            if num < 1 or num > len(tasks):
                print(f"[Task] No task number {num}.\n")
                return True
            tasks[num - 1] = tasks[num - 1].replace("- [ ]", "- [x]", 1)
            save_tasks(tasks)
            print(f"[Task] Marked done: {tasks[num - 1]}\n")
        except ValueError:
            print("[Task] Usage: /task done <number>\n")
        return True

    # ── Project Commands ──────────────────────────────────────────────────────

    if lower.startswith("/project new "):
        name = raw[len("/project new "):].strip().replace(" ", "_").lower()
        if not name:
            print("[Project] No project name provided.\n")
            return True
        path = os.path.join(VAULT_PATH, "projects", f"{name}.md")
        if os.path.exists(path):
            print(f"[Project] Already exists: projects/{name}.md\n")
            return True
        os.makedirs(os.path.dirname(path), exist_ok=True)
        content = (
            f"# {name}\n"
            f"_Created: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n\n"
            f"## Goal\n\n## Status\nActive\n\n## Tasks\n\n## Notes\n"
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[Project] Created: vault/projects/{name}.md\n")
        return True

    if lower == "/project status":
        proj_dir = os.path.join(VAULT_PATH, "projects")
        if not os.path.exists(proj_dir):
            print("[Project] No projects folder found.\n")
            return True
        files = [f for f in os.listdir(proj_dir) if f.endswith(".md") and f != "tasks.md"]
        if not files:
            print("[Project] No projects yet. Use /project new <name>\n")
            return True
        print("\n[Projects]")
        for f in files:
            print(f"  — {f}")
        print()
        return True

    return False  # Not a command

# ── Primary Call ──────────────────────────────────────────────────────────────

def call_primary(messages):
    print("[Primary] Calling Nemotron 70B...")
    try:
        r = requests.post(
            f"{PRIMARY_URL}/chat/completions",
            json={
                "model": PRIMARY_MODEL,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 1024
            },
            timeout=PRIMARY_TIMEOUT
        )
        return r.json()["choices"][0]["message"]["content"]
    except requests.exceptions.Timeout:
        print("[Primary] Timeout — no response in 180s")
        return "I'm sorry, the primary model timed out. Please try again."
    except Exception as e:
        print(f"[Primary] Error: {e}")
        return "I'm sorry, the primary model encountered an error."

# ── Reflector Call ────────────────────────────────────────────────────────────

def call_reflector(original, response):
    print("[Reflector] Calling llama3.1:8b on MacBook...")
    payload = {
        "model": REFLECT_MODEL,
        "prompt": (
            f"You are evaluating a response from Nova, an AI assistant built by Daz — "
            f"a musician and systems thinker focused on creative tools and AI workflows.\n\n"
            f"Rate this response for accuracy, clarity, and helpfulness on a scale of 0.0 to 1.0.\n"
            f"Consider whether it serves a creative/technical builder context.\n\n"
            f"Q: {original}\n"
            f"A: {response}\n\n"
            f"Reply with a single decimal score only (e.g. 0.8):"
        ),
        "stream": False
    }
    try:
        r = requests.post(
            f"{REFLECT_URL}/api/generate",
            json=payload,
            timeout=REFLECTOR_TIMEOUT
        )
        raw = r.json()["response"].strip()
        match = re.search(r"\d+\.\d+|\d+", raw)
        if match:
            score = float(match.group())
            return min(max(score, 0.0), 1.0)
        print("[Reflector] Unparseable response — defaulting to 1.0")
        return 1.0
    except requests.exceptions.Timeout:
        print("[Reflector] Timeout — defaulting score to 1.0")
        return 1.0
    except Exception as e:
        print(f"[Reflector] Error: {e} — defaulting score to 1.0")
        return 1.0

# ── Message Builder ───────────────────────────────────────────────────────────

def build_messages(session_id, user_input):
    system_content = NOVA_IDENTITY

    vault_core = bridge.identity_context()
    if vault_core and "No identity" not in vault_core:
        system_content += f"\n\n---\nVAULT CONTEXT (Identity/Architecture):\n{vault_core}"

    vault_dynamic = bridge.context_block(user_input, top_k=2)
    if vault_dynamic and "No relevant" not in vault_dynamic:
        system_content += f"\n\n---\nVAULT CONTEXT (Relevant Notes):\n{vault_dynamic}"
        print(f"[RAG] Injected dynamic vault context for: '{user_input[:60]}'")
    else:
        print(f"[RAG] No dynamic vault match for: '{user_input[:60]}'")

    messages = [{"role": "system", "content": system_content}]
    history = get_session_context(session_id, n=6)
    messages.extend(history)
    messages.append({"role": "user", "content": user_input})
    return messages

# ── Turn Runner ───────────────────────────────────────────────────────────────

def run_turn(session_id, user_input, dry_run=False):
    if dry_run:
        response = f"[DRY RUN] Would send: {user_input}"
        score = 1.0
        log_turn(session_id, "user", user_input)
        log_turn(session_id, "assistant", response, score=score)
        return response, score

    messages = build_messages(session_id, user_input)
    response = call_primary(messages)
    score = call_reflector(user_input, response)
    print(f"[Reflector] Score: {score}")

    if score < THRESHOLD:
        print(f"[Reflector] Score {score:.2f} below threshold {THRESHOLD} — regenerating once...")
        response = call_primary(messages)
        score = call_reflector(user_input, response)
        print(f"[Reflector] Retry score: {score:.2f}")
        if score < THRESHOLD:
            print(f"[Reflector] Retry still below threshold — accepting anyway to prevent loop")

    log_turn(session_id, "user", user_input)
    log_turn(session_id, "assistant", response, score=score)
    return response, score

# ── Main Loop ─────────────────────────────────────────────────────────────────

def interactive_loop(dry_run=False):
    init_db()
    session_id = new_session()
    print(f"Nova v0.9.0 — session {session_id}")
    print("Type /help for commands or 'exit' to quit\n")
    try:
        while True:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() == "exit":
                break
            if user_input.startswith("/"):
                handle_command(user_input, session_id)
                continue
            response, score = run_turn(session_id, user_input, dry_run=dry_run)
            print(f"\nNova: {response}")
            print(f"[Score: {score:.2f}]\n")
    finally:
        close_session(session_id)
        print("[Memory] Session saved.")

if __name__ == "__main__":
    interactive_loop(dry_run=False)
