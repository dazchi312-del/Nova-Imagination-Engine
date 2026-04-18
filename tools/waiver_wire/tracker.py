# tracker.py
# Nova Waiver Wire — Decision Log
# Big Dan Baseball | League 46348

import json
import os
from datetime import datetime

TRACKER_FILE = "waiver_log.json"


def load_log():
    if not os.path.exists(TRACKER_FILE):
        return []
    with open(TRACKER_FILE, "r") as f:
        return json.load(f)


def save_log(log):
    with open(TRACKER_FILE, "w") as f:
        json.dump(log, f, indent=2)


def log_add(player_name, stat_name, score_result, notes=""):
    """
    Call this when you make an add decision.
    Records the full scoring breakdown + timestamp.
    """
    log = load_log()

    entry = {
        "timestamp":      datetime.now().strftime("%Y-%m-%d %H:%M"),
        "player":         player_name,
        "stat_name":      stat_name,
        "raw_score":      score_result["raw_score"],
        "context_mod":    score_result["context_modifier"],
        "risk_mod":       score_result["risk_modifier"],
        "final_score":    score_result["final_score"],
        "recommendation": score_result["recommendation"],
        "notes":          notes,
        "outcome":        None,   # fill in after the week
        "cats_gained":    [],     # fill in after the week
    }

    log.append(entry)
    save_log(log)
    print(f"  [LOGGED] {player_name} — {score_result['recommendation']} @ {entry['timestamp']}")
    return entry


def log_outcome(player_name, outcome, cats_gained):
    """
    Update an existing entry with the week's result.
    outcome: 'hit' | 'miss' | 'partial'
    cats_gained: list of categories won because of this add
    """
    log = load_log()

    for entry in reversed(log):
        if entry["player"] == player_name and entry["outcome"] is None:
            entry["outcome"]   = outcome
            entry["cats_gained"] = cats_gained
            save_log(log)
            print(f"  [UPDATED] {player_name} — outcome: {outcome} | cats: {cats_gained}")
            return

    print(f"  [WARN] No open entry found for {player_name}")


def show_log():
    """
    Print all logged decisions in a clean summary.
    """
    log = load_log()

    if not log:
        print("\n  No decisions logged yet.")
        return

    print("\n" + "="*55)
    print("NOVA WAIVER WIRE — DECISION LOG")
    print("Big Dan Baseball | League 46348")
    print("="*55)

    for entry in log:
        outcome_str = entry["outcome"] if entry["outcome"] else "PENDING"
        cats_str    = ", ".join(entry["cats_gained"]) if entry["cats_gained"] else "—"

        print(f"\n  {entry['timestamp']}  |  {entry['player']}")
        print(f"  Stat: {entry['stat_name']}  |  Score: {entry['final_score']}  |  {entry['recommendation']}")
        print(f"  Outcome: {outcome_str}  |  Cats Gained: {cats_str}")
        if entry["notes"]:
            print(f"  Notes: {entry['notes']}")

    print("\n" + "="*55)

    hits     = sum(1 for e in log if e["outcome"] == "hit")
    misses   = sum(1 for e in log if e["outcome"] == "miss")
    partials = sum(1 for e in log if e["outcome"] == "partial")
    pending  = sum(1 for e in log if e["outcome"] is None)

    print(f"  TOTALS — Hit: {hits} | Partial: {partials} | Miss: {misses} | Pending: {pending}")
    print("="*55 + "\n")


if __name__ == "__main__":
    print("\ntracker.py — module ready.")
    print("Import log_add(), log_outcome(), show_log() from this file.")
    print("Run cli.py for the full interface.\n")
