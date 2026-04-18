"""
Project Nova - Obsidian Bridge
Layer 6/7 interface: reads vault .md files, parses frontmatter,
exposes search and read methods to the core loop.
"""

import os
import re
import json
from pathlib import Path
from datetime import datetime
from typing import Optional


# ── Config ────────────────────────────────────────────────────────────────────

VAULT_PATH = Path("C:/Users/dazch/nova/vault")

FOLDER_PRIORITY = {
    "identity":     1,
    "architecture": 2,
    "sessions":     3,
    "insights":     4,
    "projects":     5,
    "inbox":        6,
}
# ── Frontmatter Parser ─────────────────────────────────────────────────────────

def parse_frontmatter(content: str) -> tuple[dict, str]:
    """
    Splits a markdown file into frontmatter dict and body text.
    Returns ({}, full_content) if no frontmatter found.
    """
    if not content.startswith("---"):
        return {}, content

    end = content.find("---", 3)
    if end == -1:
        return {}, content

    raw = content[3:end].strip()
    body = content[end + 3:].strip()
    meta = {}

    for line in raw.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()

    return meta, body


# ── Note Object ────────────────────────────────────────────────────────────────

class Note:
    def __init__(self, path: Path):
        self.path     = path
        self.filename = path.stem
        self.folder   = path.parent.name
        self.priority = FOLDER_PRIORITY.get(self.folder, 99)

        raw = path.read_text(encoding="utf-8")
        self.meta, self.body = parse_frontmatter(raw)

        self.title  = self.meta.get("title", self.filename)
        self.tags   = self.meta.get("tags", "")
        self.date   = self.meta.get("date", "")
        self.signal = self.meta.get("signal", "")

    def preview(self, chars: int = 200) -> str:
        return self.body[:chars].replace("\n", " ").strip()

    def __repr__(self):
        return f"<Note [{self.folder}] {self.title}>"


# ── Bridge ─────────────────────────────────────────────────────────────────────

class ObsidianBridge:
    def __init__(self, vault_path: Path = VAULT_PATH):
        self.vault_path = vault_path
        self.notes: list[Note] = []
        self.index()

    def index(self):
        """
        Walk the vault and load all .md files into memory.
        """
        self.notes = []
        for md_file in self.vault_path.rglob("*.md"):
            try:
                note = Note(md_file)
                self.notes.append(note)
            except Exception as e:
                print(f"[Bridge] Skipped {md_file.name}: {e}")

        # Sort by folder priority, then filename
        self.notes.sort(key=lambda n: (n.priority, n.filename))
        print(f"[Bridge] Indexed {len(self.notes)} notes from vault.")

    def search(self, query: str, top_k: int = 5) -> list[Note]:
        """
        Simple keyword search across title, tags, and body.
        Returns top_k most relevant notes.
        """
        query_lower = query.lower()
        scored = []

        for note in self.notes:
            score = 0
            if query_lower in note.title.lower():   score += 10
            if query_lower in note.tags.lower():    score += 8
            if query_lower in note.body.lower():    score += 3
            score -= note.priority  # higher priority folders rank up

            if score > 0:
                scored.append((score, note))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [note for _, note in scored[:top_k]]

    def get_by_folder(self, folder: str) -> list[Note]:
        """
        Return all notes from a specific folder.
        """
        return [n for n in self.notes if n.folder == folder]

    def get_by_filename(self, filename: str) -> Optional[Note]:
        """
        Return a single note by filename (without .md extension).
        """
        for note in self.notes:
            if note.filename == filename:
                return note
        return None

    def context_block(self, query: str, top_k: int = 3) -> str:
        """
        Returns a formatted string ready to inject into an LLM prompt.
        Pulls top_k notes relevant to query.
        """
        results = self.search(query, top_k=top_k)
        if not results:
            return "[No relevant vault context found]"

        blocks = []
        for note in results:
            block = (
                f"## {note.title}\n"
                f"_Folder: {note.folder} | Signal: {note.signal}_\n\n"
                f"{note.body[:600]}\n"
            )
            blocks.append(block)

        return "\n---\n".join(blocks)

    def identity_context(self) -> str:
        """
        Always-on context: loads identity + architecture notes.
        Use this at session start.
        """
        core_notes = (
            self.get_by_folder("identity") +
            self.get_by_folder("architecture")
        )
        if not core_notes:
            return "[No identity/architecture context found]"

        blocks = []
        for note in core_notes[:5]:  # cap at 5 to save tokens
            blocks.append(f"## {note.title}\n{note.body[:400]}")

        return "\n---\n".join(blocks)

    def summary(self) -> dict:
        """
        Returns a quick stats dict for debugging.
        """
        folders = {}
        for note in self.notes:
            folders[note.folder] = folders.get(note.folder, 0) + 1
        return {
            "total_notes": len(self.notes),
            "by_folder": folders,
            "vault_path": str(self.vault_path),
        }

    def status(self) -> dict:
        """
        Returns a status dict for the /status command in loop.py.
        """
        data = self.summary()
        return {
            "vault_path":  data["vault_path"],
            "note_count":  data["total_notes"],
            "by_folder":   data["by_folder"],
        }

    def debug_summary(self):
        """
        Prints full vault breakdown to terminal for the /debug command.
        """
        data = self.summary()
        print(f"\n[Debug] Vault path : {data['vault_path']}")
        print(f"[Debug] Total notes: {data['total_notes']}")
        print(f"[Debug] By folder  :")
        for folder, count in sorted(data["by_folder"].items()):
            print(f"         {folder:<14} {count} note(s)")
        print("\n[Debug] Note index:")
        for note in self.notes:
            print(f"  [{note.folder}] {note.title}")
        print()


# ── Quick Test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    bridge = ObsidianBridge()

    print("\n── Vault Summary ──────────────────────────────")
    print(json.dumps(bridge.summary(), indent=2))

    print("\n── Identity Context (session start) ───────────")
    print(bridge.identity_context()[:800])

    print("\n── Search: 'nova' ─────────────────────────────")
    results = bridge.search("nova", top_k=3)
    for r in results:
        print(f"  {r.folder}/{r.filename}")
        print(f"  Preview: {r.preview(120)}\n")

