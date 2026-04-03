BEGIN TRANSACTION;
CREATE TABLE creative_arguments (
    argument_id TEXT PRIMARY KEY,
    idea_id TEXT,
    champion_thesis TEXT,
    devil_critique TEXT,
    resolution TEXT,
    FOREIGN KEY(idea_id) REFERENCES creative_ideas(idea_id)
);
CREATE TABLE creative_ideas (
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
CREATE TABLE creative_sessions (
    session_id TEXT PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    base_prompt TEXT
);
INSERT INTO "creative_sessions" VALUES('66746061-98b5-4d75-b9cf-69c3b50dd037','2026-04-01 02:35:39','{''id'': ''66746061-98b5-4d75-b9cf-69c3b50dd037'', ''capability'': ''text''}');
INSERT INTO "creative_sessions" VALUES('b1ca1d76-49b0-4e5a-9e55-017566d140c9','2026-04-01 04:28:26','{"id": "b1ca1d76-49b0-4e5a-9e55-017566d140c9", "capability": "text"}');
INSERT INTO "creative_sessions" VALUES('4c4c9505-9607-40e2-ada8-0bf3eec389df','2026-04-01 04:39:06','{"id": "4c4c9505-9607-40e2-ada8-0bf3eec389df", "capability": "text"}');
INSERT INTO "creative_sessions" VALUES('65e9ccc9-8118-427e-a07a-77017fdc4ed1','2026-04-01 04:43:39','{"id": "65e9ccc9-8118-427e-a07a-77017fdc4ed1", "capability": "text"}');
CREATE TABLE taste_profile (
    topic TEXT PRIMARY KEY,
    affinity_score REAL CHECK(affinity_score >= 0.0 AND affinity_score <= 1.0),
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
);
COMMIT;