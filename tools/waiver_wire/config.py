# config.py
# Big Dan Baseball — League 46348
# Source of truth for all scoring

LEAGUE_CONFIG = {
    "name": "Big Dan Baseball",
    "platform": "Yahoo",
    "league_id": 46348,
    "format": "H2H Categories",
    "teams": 14,
    "max_adds_per_week": 5,
    "min_ip_per_week": 30,
    "risk_profile":   "high_probability",
    "need_level":     "normal",
    "il_status":      "full", 
}

HITTING_CATEGORIES = ["R", "2B", "HR", "RBI", "SB", "K", "AVG", "OBP"]
PITCHING_CATEGORIES = ["W", "L", "SV", "K", "HLD", "ERA", "WHIP", "QS"]

INVERSE_CATEGORIES = ["L", "ERA", "WHIP"]

ROSTER_CONFIG = {
    "C": 1, "1B": 1, "2B": 1, "3B": 1, "SS": 1,
    "OF": 3, "Util": 2, "SP": 2, "RP": 2, "P": 4,
    "BN": 5, "IL": 4
}

STAT_BASELINES = {
    "R":    {"mean": 3.8,   "std_dev": 1.4,  "type": "hitting"},
    "2B":   {"mean": 0.9,   "std_dev": 0.5,  "type": "hitting"},
    "HR":   {"mean": 0.8,   "std_dev": 0.6,  "type": "hitting"},
    "RBI":  {"mean": 3.2,   "std_dev": 1.5,  "type": "hitting"},
    "SB":   {"mean": 0.5,   "std_dev": 0.4,  "type": "hitting"},
    "K":    {"mean": 4.1,   "std_dev": 1.2,  "type": "hitting"},
    "AVG":  {"mean": 0.255, "std_dev": 0.028,"type": "hitting"},
    "OBP":  {"mean": 0.320, "std_dev": 0.032,"type": "hitting"},
    "W":    {"mean": 0.8,   "std_dev": 0.5,  "type": "pitching"},
    "L":    {"mean": 0.6,   "std_dev": 0.4,  "type": "pitching"},
    "SV":   {"mean": 0.7,   "std_dev": 0.8,  "type": "pitching"},
    "P_K":  {"mean": 7.2,   "std_dev": 2.1,  "type": "pitching"},
    "HLD":  {"mean": 0.6,   "std_dev": 0.4,  "type": "pitching"},
    "ERA":  {"mean": 4.10,  "std_dev": 0.85, "type": "pitching"},
    "WHIP": {"mean": 1.28,  "std_dev": 0.18, "type": "pitching"},
    "QS":   {"mean": 0.9,   "std_dev": 0.5,  "type": "pitching"},
    "K/9":  {"mean": 8.5,   "std_dev": 1.8,  "type": "pitching"},
    "K/BB": {"mean": 2.8,   "std_dev": 0.9,  "type": "pitching"},
}

THRESHOLDS = {
    "SIGNAL": 75,
    "WATCH":  55,
    "NOISE":  0,
}

SIGNAL_REQUIREMENTS = {
    "min_duration_days":    7,
    "min_confirming_stats": 3,
    "min_magnitude":        60,
}

NOISE_INDICATORS = {
    "max_duration_days":    2,
    "max_confirming_stats": 1,
}

