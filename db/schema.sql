CREATE TABLE IF NOT EXISTS creative_sessions (
    session_id TEXT PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    base_prompt TEXT
);

CREATE TABLE IF NOT EXISTS creative_ideas (
    idea_id TEXT PRIMARY KEY,
    session_id TEXT,
    domain TEXT,
    lens TEXT,
    constraint_rule TEXT,
    raw_concept TEXT,
    synthesized_concept TEXT,
    status TEXT CHECK(status IN ('championed', 'orphaned', 'discarded')),
    FOREIGN KEY(session_id) REFERENCES creative_sessions(session_id)
);

CREATE TABLE IF NOT EXISTS taste_profile (
    topic TEXT PRIMARY KEY,
    affinity_score REAL CHECK(affinity_score >= 0.0 AND affinity_score <= 1.0),
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS creative_arguments (
    argument_id TEXT PRIMARY KEY,
    idea_id TEXT,
    champion_thesis TEXT,
    devil_critique TEXT,
    resolution TEXT,
    FOREIGN KEY(idea_id) REFERENCES creative_ideas(idea_id)
);