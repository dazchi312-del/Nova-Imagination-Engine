# scorer.py
# Nova Fantasy Asset — Scoring Engine
# Big Dan Baseball v1.0

from config import (
    STAT_BASELINES,
    INVERSE_CATEGORIES,
    THRESHOLDS,
    SIGNAL_REQUIREMENTS,
    NOISE_INDICATORS
)

# ─────────────────────────────────────────
# LAYER 1: RAW OUTLIER SCORE
# ─────────────────────────────────────────

def raw_outlier_score(recent_stat, season_stat, stat_name):
    """
    Measures deviation from baseline.
    Returns 0-100.
    Inverse categories (ERA, WHIP, L) are flipped.
    """

    if stat_name not in STAT_BASELINES:
        print(f"  [WARN] Unknown stat: {stat_name}. Returning neutral 50.")
        return 50.0

    baseline = STAT_BASELINES[stat_name]
    std_dev   = baseline["std_dev"]

    if std_dev == 0:
        return 50.0

    delta = recent_stat - season_stat

    if stat_name in INVERSE_CATEGORIES:
        delta = -delta

    z_score = delta / std_dev
    score   = 50 + (z_score * 18)

    return round(max(0.0, min(100.0, score)), 1)


# ─────────────────────────────────────────
# LAYER 2: CONTEXTUAL MODIFIER
# ─────────────────────────────────────────

def contextual_modifier(player_context):
    """
    Adjusts raw score based on real-world context.

    player_context keys:
        role_secure        True/False
        starts_next_week   int (0-2)
        team_offense_rank  int (1-30)
        opponent_rank      int (1-30, 1=hardest)
        days_since_injury  int or None
        platoon_risk       True/False
    """

    modifier = 1.0

    if player_context.get("role_secure") == False:
        modifier *= 0.7
    elif player_context.get("role_secure") == True:
        modifier *= 1.1

    starts = player_context.get("starts_next_week", 1)
    if starts == 2:
        modifier *= 1.2
    elif starts == 0:
        modifier *= 0.4

    team_rank = player_context.get("team_offense_rank", 15)
    if team_rank <= 5:
        modifier *= 1.1
    elif team_rank >= 25:
        modifier *= 0.85

    opp_rank = player_context.get("opponent_rank", 15)
    if opp_rank >= 25:
        modifier *= 1.15
    elif opp_rank <= 5:
        modifier *= 0.85

    days_back = player_context.get("days_since_injury", None)
    if days_back is not None:
        if days_back < 7:
            modifier *= 0.75
        elif days_back < 14:
            modifier *= 0.90

    if player_context.get("platoon_risk") == True:
        modifier *= 0.85

    return round(max(0.5, min(1.5, modifier)), 3)


# ─────────────────────────────────────────
# LAYER 3: RISK PROFILE MULTIPLIER
# ─────────────────────────────────────────

def risk_profile_multiplier(profile, need_level, week_position):
    """
    Adjusts for personal risk tolerance and standings context.

    profile:        aggressive | neutral | conservative
    need_level:     desperate | moderate | comfortable
    week_position:  ahead | close | behind
    """

    multiplier = 1.0

    profile_map = {
        "aggressive":   1.2,
        "neutral":      1.0,
        "conservative": 0.85,
    }
    multiplier *= profile_map.get(profile, 1.0)

    need_map = {
        "desperate":   1.2,
        "moderate":    1.0,
        "comfortable": 0.9,
    }
    multiplier *= need_map.get(need_level, 1.0)

    position_map = {
        "behind": 1.15,
        "close":  1.0,
        "ahead":  0.9,
    }
    multiplier *= position_map.get(week_position, 1.0)

    return round(max(0.7, min(1.4, multiplier)), 3)


# ─────────────────────────────────────────
# LAYER 4: SIGNAL CLASSIFIER
# ─────────────────────────────────────────

def classify_signal(spike_duration_days, confirming_stats, outlier_score):
    """
    Is this a SIGNAL, WATCH, or NOISE?
    This is the calm detector.
    """

    if (spike_duration_days <= NOISE_INDICATORS["max_duration_days"]
            and confirming_stats <= NOISE_INDICATORS["max_confirming_stats"]):
        return "NOISE"

    if (spike_duration_days >= SIGNAL_REQUIREMENTS["min_duration_days"]
            and confirming_stats >= SIGNAL_REQUIREMENTS["min_confirming_stats"]
            and outlier_score >= SIGNAL_REQUIREMENTS["min_magnitude"]):
        return "SIGNAL"

    return "WATCH"


# ─────────────────────────────────────────
# LAYER 5: FINAL SCORE
# ─────────────────────────────────────────

def final_score(
    recent_stat,
    season_stat,
    stat_name,
    player_context,
    profile="neutral",
    need_level="moderate",
    week_position="close"
):
    """
    Master scoring function.
    Combines all layers. Returns full breakdown dict.
    """

    raw         = raw_outlier_score(recent_stat, season_stat, stat_name)
    context_mod = contextual_modifier(player_context)
    risk_mod    = risk_profile_multiplier(profile, need_level, week_position)

    combined = raw * context_mod * risk_mod
    combined = round(max(0.0, min(100.0, combined)), 1)

    if combined >= THRESHOLDS["SIGNAL"]:
        recommendation = "ADD"
    elif combined >= THRESHOLDS["WATCH"]:
        recommendation = "WATCH"
    else:
        recommendation = "IGNORE"

    return {
        "raw_score":        raw,
        "context_modifier": context_mod,
        "risk_modifier":    risk_mod,
        "final_score":      combined,
        "recommendation":   recommendation,
    }


# ─────────────────────────────────────────
# TEST — Run this file directly
# ─────────────────────────────────────────

if __name__ == "__main__":

    print("\n" + "="*50)
    print("NOVA WAIVER WIRE SCORER — TEST RUN")
    print("Big Dan Baseball | League 46348")
    print("="*50)

    test_players = [
        {
            "name": "Pitcher A — K Spike, 2 Starts",
            "recent_stat": 11.2,
            "season_stat":  8.1,
            "stat_name":   "K/9",
            "context": {
                "role_secure":       True,
                "starts_next_week":  2,
                "team_offense_rank": 12,
                "opponent_rank":     22,
                "days_since_injury": None,
                "platoon_risk":      False,
            },
        },
        {
            "name": "Reliever B — HLD Spike, Role Unclear",
            "recent_stat": 2.5,
            "season_stat": 0.7,
            "stat_name":  "HLD",
            "context": {
                "role_secure":       False,
                "starts_next_week":  0,
                "team_offense_rank": 18,
                "opponent_rank":     15,
                "days_since_injury": None,
                "platoon_risk":      False,
            },
        },
        {
            "name": "Hitter C — 2B Spike, Just Off IL",
            "recent_stat": 2.1,
            "season_stat": 0.8,
            "stat_name":  "2B",
            "context": {
                "role_secure":       True,
                "starts_next_week":  1,
                "team_offense_rank": 7,
                "opponent_rank":     25,
                "days_since_injury": 5,
                "platoon_risk":      False,
            },
        },
    ]

    for player in test_players:
        print(f"\nPlayer: {player['name']}")
        print("-" * 40)

        result = final_score(
            recent_stat    = player["recent_stat"],
            season_stat    = player["season_stat"],
            stat_name      = player["stat_name"],
            player_context = player["context"],
            profile        = "neutral",
            need_level     = "desperate",
            week_position  = "close",
        )

        print(f"  Raw Score:         {result['raw_score']}")
        print(f"  Context Modifier:  {result['context_modifier']}")
        print(f"  Risk Modifier:     {result['risk_modifier']}")
        print(f"  Final Score:       {result['final_score']}")
        print(f"  Recommendation:    >>> {result['recommendation']} <<<")

    print("\n" + "="*50)
    print("scorer.py operational.")
    print("="*50 + "\n")

score_player = final_score
