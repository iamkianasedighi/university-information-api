"""Check the analytics queries against the supplied demo rows."""

import re
import sqlite3
from pathlib import Path

from API_uni import CLASS_ENROLLMENTS_SQL, OVERVIEW_SQL


SEED = Path(__file__).resolve().parents[1] / "uni.sql"


def test_analytics_matches_seed():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE PROFinfo (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE STDinfo (id INTEGER PRIMARY KEY, name TEXT, phone TEXT UNIQUE);
        CREATE TABLE CLASSinfo (id INTEGER PRIMARY KEY, name TEXT, teacher INTEGER);
        CREATE TABLE ENROLLinfo (id INTEGER PRIMARY KEY, STDid INTEGER, CLASSid INTEGER,
                                 UNIQUE (STDid, CLASSid));
    """)

    seed_sql = SEED.read_text(encoding="utf-8")
    # INSERT syntax is shared by MySQL and SQLite for these simple demo records.
    inserts = re.findall(r"INSERT INTO \w+\s*\([^;]*?;", seed_sql, flags=re.I | re.S)
    assert len(inserts) == 4
    db.executescript("\n".join(inserts))

    totals = dict(db.execute(OVERVIEW_SQL).fetchone())
    counts = [dict(row) for row in db.execute(CLASS_ENROLLMENTS_SQL)]
    assert totals == {
        "total_students": 20,
        "total_classes": 6,
        "total_enrollments": 18,
        "students_without_enrollments": 7,
    }
    assert [(row["class_name"], row["enrollment_count"]) for row in counts] == [
        ("Databases", 5),
        ("Algorithms", 4),
        ("Introduction to Programming", 3),
        ("Statistics", 3),
        ("Web Development", 3),
        ("Data Visualization", 0),
    ]


def test_schema_declares_uniqueness_and_foreign_keys():
    seed = SEED.read_text(encoding="utf-8")
    assert "phone VARCHAR(16) NOT NULL UNIQUE" in seed
    assert "CONSTRAINT uq_student_class UNIQUE (STDid, CLASSid)" in seed
    assert seed.count("FOREIGN KEY") == 3
