
DROP TABLE IF EXISTS voices;

CREATE TABLE voices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    posted_at TIMESTAMP NOT NULL,
    duration INTEGER,
    downloaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    filepath TEXT NOT NULL,
    koe_koe_id TEXT UNIQUE NOT NULL
);

DROP TABLE IF EXISTS favorites;

CREATE TABLE favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    voice_id INTEGER NOT NULL,
    FOREIGN KEY (voice_id) REFERENCES voices (id)
);

DROP TABLE IF EXISTS tags;

CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

DROP TABLE IF EXISTS voice_tags;

CREATE TABLE voice_tags (
    voice_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (voice_id, tag_id),
    FOREIGN KEY (voice_id) REFERENCES voices (id),
    FOREIGN KEY (tag_id) REFERENCES tags (id)
);
