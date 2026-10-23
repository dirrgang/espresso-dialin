"""Export a consistent, read-only v4/v5 inventory; keep runtime exports private."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

TABLE_ORDER = {
    "sessions": "started_at, id",
    "shots": "session_id, sequence",
    "recommendations": "session_id, target_sequence, created_at, id",
    "shot_resolutions": "recorded_at, shot_id",
    "experiments": "session_id, created_at, id",
    "experiment_steps": "experiment_id, sequence",
    "experiment_stops": "recorded_at, experiment_id",
    "extraction_recommendations": "session_id, target_sequence, created_at, id",
}


def read_inventory(path: Path) -> dict[str, object]:
    """Retain raw rows, NULLs and sequence boundaries without initializing the schema."""
    path = path.resolve(strict=True)
    # SQLite's file-header read/write versions (offsets 18/19) are 2 in WAL mode.
    # Even mode=ro can create WAL sidecars or write shared-memory read marks. Reject
    # these sources before connecting, including checkpointed WAL files with no sidecars.
    with path.open("rb") as source:
        source.seek(18)
        wal_mode = 2 in source.read(2)
    if wal_mode or any(Path(str(path) + suffix).exists() for suffix in ("-wal", "-shm")):
        raise ValueError(
            "WAL-mode sources or WAL sidecars are unsupported; supply a consistent "
            "snapshot in DELETE journal mode. The source was not opened by SQLite."
        )
    # mode=ro prevents accidental creation/migration; query_only also rejects writes
    # through this connection. Journal mode must stay unchanged during inventory.
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (4, 5):
            raise ValueError(f"unsupported inventory schema {version}; no migration performed")
        tables = {}
        for table, order in TABLE_ORDER.items():
            if table == "extraction_recommendations" and version == 4:
                continue  # Unavailable in v4, not evidence of zero recorded v5 feedback.
            tables[table] = [
                dict(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY {order}")
            ]
        quick_check = [row[0] for row in db.execute("PRAGMA quick_check")]
        foreign_key_errors = [tuple(row) for row in db.execute("PRAGMA foreign_key_check")]
        schema = [
            tuple(row)
            for row in db.execute(
                "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
            )
        ]
        # Fingerprint schema and the rows visible together in this read transaction.
        payload = {"schema_version": version, "schema": schema, "tables": tables}
        fingerprint = hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
    return {
        "source": str(path),
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "schema_version": version,
        "logical_snapshot_sha256": fingerprint,
        "quick_check": quick_check,
        "foreign_key_errors": foreign_key_errors,
        "counts": {table: len(rows) for table, rows in tables.items()},
        "tables": tables,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    print(json.dumps(read_inventory(args.database), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
