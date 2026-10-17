"""Content-addressed raw blobs and an append-only, checksummed SQLite registry."""

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from pit_haf.data.evidence import EvidenceVersion


class SnapshotError(ValueError):
    """Immutable identity or content integrity check failed."""


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


class SnapshotStore:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.database = self.root / "registry.sqlite3"
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS versions (
                    version_id TEXT PRIMARY KEY, record_id TEXT NOT NULL, source_id TEXT NOT NULL,
                    content_hash TEXT NOT NULL, metadata_json TEXT NOT NULL,
                    metadata_hash TEXT NOT NULL, UNIQUE(record_id, content_hash)
                );
                CREATE TABLE IF NOT EXISTS acquisitions (
                    acquisition_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_json TEXT NOT NULL, event_hash TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS immutable_versions_update BEFORE UPDATE ON versions
                    BEGIN SELECT RAISE(ABORT, 'versions are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS immutable_versions_delete BEFORE DELETE ON versions
                    BEGIN SELECT RAISE(ABORT, 'versions are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS immutable_acquisitions_update
                    BEFORE UPDATE ON acquisitions
                    BEGIN SELECT RAISE(ABORT, 'acquisitions are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS immutable_acquisitions_delete
                    BEFORE DELETE ON acquisitions
                    BEGIN SELECT RAISE(ABORT, 'acquisitions are append-only'); END;
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def blob_path(self, content_hash: str) -> Path:
        if len(content_hash) != 64 or any(c not in "0123456789abcdef" for c in content_hash):
            raise SnapshotError("Invalid SHA-256 digest")
        return self.root / "blobs" / content_hash[:2] / content_hash

    def put_blob(self, payload: bytes) -> str:
        digest = hashlib.sha256(payload).hexdigest()
        target = self.blob_path(digest)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("xb") as stream:
                stream.write(payload)
        except FileExistsError:
            self.read_blob(digest)
        return digest

    def read_blob(self, digest: str) -> bytes:
        path = self.blob_path(digest)
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise SnapshotError(f"Snapshot unavailable: {digest}") from exc
        if hashlib.sha256(payload).hexdigest() != digest:
            raise SnapshotError(f"Snapshot checksum mismatch: {digest}")
        return payload

    def register(self, evidence: EvidenceVersion) -> None:
        """Register exactly once; revised metadata needs a new explicit record/protocol."""
        self.read_blob(evidence.content_hash)
        for reference in (
            evidence.listing_snapshot_hash,
            evidence.timestamp_evidence_hash,
            evidence.version_evidence_hash,
        ):
            if reference:
                self.read_blob(reference)
        raw = canonical(evidence.model_dump(mode="json"))
        digest = hashlib.sha256(raw).hexdigest()
        with self._connect() as db:
            existing = db.execute(
                "SELECT metadata_hash FROM versions WHERE version_id = ?", (evidence.version_id,)
            ).fetchone()
            if existing:
                if existing["metadata_hash"] == digest:
                    return
                raise SnapshotError("version_id already exists with different immutable metadata")
            source = db.execute(
                "SELECT DISTINCT source_id FROM versions WHERE record_id = ?", (evidence.record_id,)
            ).fetchall()
            if any(row["source_id"] != evidence.source_id for row in source):
                raise SnapshotError("A logical record cannot change source_id")
            if evidence.supersedes_version_id:
                previous = db.execute(
                    "SELECT record_id FROM versions WHERE version_id = ?",
                    (evidence.supersedes_version_id,),
                ).fetchone()
                if previous is None or previous["record_id"] != evidence.record_id:
                    raise SnapshotError("Superseded version must exist on the same logical record")
            try:
                db.execute("INSERT INTO versions VALUES (?, ?, ?, ?, ?, ?)", (
                    evidence.version_id, evidence.record_id, evidence.source_id,
                    evidence.content_hash, raw.decode(), digest,
                ))
            except sqlite3.IntegrityError as exc:
                raise SnapshotError("Record/content already has a different immutable version ID") from exc

    def versions(self) -> tuple[EvidenceVersion, ...]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM versions ORDER BY record_id, version_id").fetchall()
        result = []
        for row in rows:
            raw = row["metadata_json"].encode()
            if hashlib.sha256(raw).hexdigest() != row["metadata_hash"]:
                raise SnapshotError("Registry metadata checksum mismatch")
            entry = EvidenceVersion.model_validate_json(raw)
            identity = (entry.version_id, entry.record_id, entry.source_id, entry.content_hash)
            if identity != tuple(row[key] for key in (
                "version_id", "record_id", "source_id", "content_hash"
            )):
                raise SnapshotError("Registry metadata identity mismatch")
            result.append(entry)
        return tuple(result)

    def log_acquisition(self, event: dict) -> None:
        raw = canonical({"system_recorded_at": datetime.now(UTC).isoformat(), **event})
        with self._connect() as db:
            db.execute("INSERT INTO acquisitions(event_json, event_hash) VALUES (?, ?)", (
                raw.decode(), hashlib.sha256(raw).hexdigest(),
            ))
