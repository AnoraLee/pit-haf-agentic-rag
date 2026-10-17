"""Gate evidence metadata first, then deliver only selected and verified raw bytes."""

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from pit_haf.data.evidence import EvidenceVersion
from pit_haf.data.point_in_time import _utc_timestamp, select_as_of
from pit_haf.data.snapshots import SnapshotError, SnapshotStore


@dataclass(frozen=True)
class EvidenceDelivery:
    evidence: EvidenceVersion
    raw_bytes: bytes


@dataclass(frozen=True)
class GatewayResult:
    deliveries: tuple[EvidenceDelivery, ...]
    audit: tuple[dict, ...]
    decision_at: str
    cohort: str


def deliver_as_of(
    store: SnapshotStore, *, decision_at: str, cohort: Literal["strict", "conservative"] = "strict",
    expected_data_kind: Literal["real_document", "test_fixture"] = "real_document",
) -> GatewayResult:
    """Audit is evaluator-only; never attach it to model context or retrieval corpus."""
    if cohort not in {"strict", "conservative"}:
        raise ValueError("Unknown eligibility cohort")
    if expected_data_kind not in {"real_document", "test_fixture"}:
        raise ValueError("Unknown data kind")
    cutoff = _utc_timestamp(decision_at, "decision_at")
    versions = store.versions()
    candidates = []
    audit = []
    by_id = {}
    for item in versions:
        if item.data_kind != expected_data_kind:
            audit.append({"version_id": item.version_id, "status": "quarantined",
                          "reasons": ["unexpected_data_kind"]})
            continue
        if item.available_at is None:
            audit.append({"version_id": item.version_id, "status": "quarantined",
                          "reasons": item.quarantine_reasons(cohort)})
            continue
        # Future content/proof blobs are not opened while constructing a historical corpus.
        if item.available_at > cutoff:
            audit.append({"version_id": item.version_id, "status": "future"})
            continue
        candidates.append({
            "record_id": item.record_id, "source_id": item.source_id,
            "available_at": item.available_at, "version_id": item.version_id,
        })
        by_id[item.version_id] = item
    selected = select_as_of(pd.DataFrame(candidates, columns=[
        "record_id", "source_id", "available_at", "version_id"
    ]), decision_at=cutoff)
    selected_ids = set(selected.records["version_id"])
    deliveries = []
    for row in candidates:
        version_id = row["version_id"]
        status = "allowed" if version_id in selected_ids else "superseded"
        if status == "allowed":
            item = by_id[version_id]
            reasons = item.quarantine_reasons(cohort)
            if reasons:
                # A known newer version blocks stale older delivery even when its proof is missing.
                audit.append({"version_id": version_id, "status": "quarantined", "reasons": reasons})
                continue
            try:
                for proof in (item.timestamp_evidence_hash, item.version_evidence_hash):
                    store.read_blob(proof)
                deliveries.append(EvidenceDelivery(item, store.read_blob(item.content_hash)))
            except SnapshotError as exc:
                status = "quarantined"
                audit.append({"version_id": version_id, "status": status, "reasons": [str(exc)]})
                continue
        audit.append({"version_id": version_id, "status": status})
    return GatewayResult(tuple(deliveries), tuple(audit), cutoff.isoformat(), cohort)
