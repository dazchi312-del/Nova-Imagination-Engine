# cli.py
# Nova Waiver Wire — Command Line Interface
# Big Dan Baseball | League 46348

from scorer import score_player
from tracker import log_add, log_outcome, show_log
from config import LEAGUE_CONFIG

BANNER = """
==================================================
  NOVA WAIVER WIRE TOOL
  Big Dan Baseball | League 46348
  14 Teams | H2H 8x8 | Yahoo ID: 46348
==================================================
"""

MENU = """
Commands:
  score    -- Score a player manually
  log      -- Log an add decision
  outcome  -- Record a week's result
  history  -- Show full decision log
  config   -- Show current league config
  help     -- Show this menu
  quit     -- Exit
"""


def cmd_score():
    print("\n  -- SCORE A PLAYER --")
    print("  Enter player details\n")

    name = input("  Player name: ").strip()
    stat = input("  Stat category (K, HR, SV, ERA, etc): ").strip().upper()

    try:
        recent = float(input("  Recent value (last 7-14 days): ").strip())
        season = float(input("  Season average: ").strip())
    except ValueError:
        print("  [ERROR] Enter numbers for recent and season values.")
        return

    two_start = input("  Two-start week? (y/n): ").strip().lower() == "y"
    role_secure = input("  Role secure? (y/n): ").strip().lower() == "y"

    result = score_player(
        stat_name=stat,
        recent_value=recent,
        season_avg=season,
        two_start_week=two_start,
        role_secure=role_secure
    )

    print("\n  ----------------------------------------")
    print("  Player: " + name + " -- " + stat + " Signal")
    print("  Raw Score:         " + str(result["raw_score"]))
    print("  Context Modifier:  " + str(result["context_modifier"]))
    print("  Risk Modifier:     " + str(result["risk_modifier"]))
    print("  Final Score:       " + str(result["final_score"]))
    print("  Recommendation:    >>> " + result["recommendation"] + " <<<")
    print("  ----------------------------------------\n")

    if input("  Log this decision? (y/n): ").strip().lower() == "y":
        notes = input("  Notes (optional): ").strip()
        log_add(name, stat, result, notes)


def cmd_log():
    print("\n  -- LOG A DECISION --")
    name = input("  Player name: ").strip()
    stat = input("  Stat category: ").strip().upper()

    try:
        final = float(input("  Final score: ").strip())
    except ValueError:
        print("  [ERROR] Score must be a number.")
        return

    rec = input("  Recommendation (ADD/WATCH/IGNORE): ").strip().upper()
    notes = input("  Notes (optional): ").strip()

    result = {
        "raw_score": "--",
        "context_modifier": "--",
        "risk_modifier": "--",
        "final_score": final,
        "recommendation": rec
    }

    log_add(name, stat, result, notes)


def cmd_outcome():
    print("\n  -- RECORD OUTCOME --")
    name = input("  Player name: ").strip()
    outcome = input("  Outcome (hit/miss/partial): ").strip().lower()

    cats_input = input("  Categories gained (comma separated, or Enter for none): ").strip()
    cats = [c.strip().upper() for c in cats_input.split(",")] if cats_input else []

    log_outcome(name, outcome, cats)


def cmd_config():
    print("\n  -- CURRENT LEAGUE CONFIG --\n")
    print("  League ID:     " + str(LEAGUE_CONFIG["league_id"]))
    print("  Platform:      " + str(LEAGUE_CONFIG["platform"]))
    print("  Format:        " + str(LEAGUE_CONFIG["format"]))
    print("  Teams:         " + str(LEAGUE_CONFIG["teams"]))
    print("  Max Adds/Week: " + str(LEAGUE_CONFIG["max_adds_per_week"]))
    print("  Min IP/Week:   " + str(LEAGUE_CONFIG["min_ip_per_week"]))
    print("  Risk Profile:  " + str(LEAGUE_CONFIG.get("risk_profile", "high_probability")))
    print("  Need Level:    " + str(LEAGUE_CONFIG["need_level"]))
    print("  IL Status:     " + str(LEAGUE_CONFIG["il_status"]) + "\n")


def main():
    print(BANNER)
    print(MENU)

    while True:
        try:
            cmd = input("nova-waiver > ").strip().lower()
        except KeyboardInterrupt:
            print("\n\n  Session ended.\n")
            break

        if cmd == "score":
            cmd_score()
        elif cmd == "log":
            cmd_log()
        elif cmd == "outcome":
            cmd_outcome()
        elif cmd == "history":
            show_log()
        elif cmd == "config":
            cmd_config()
        elif cmd == "help":
            print(MENU)
        elif cmd in ("quit", "exit", "q"):
            print("\n  Session ended.\n")
            break
        else:
            print("\n  Unknown command: " + cmd + " -- type help for options\n")


if __name__ == "__main__":
    main()
