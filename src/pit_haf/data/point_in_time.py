"""Filter versioned records by their verified availability timestamps."""

import argparse
import json
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

REQUIRED_COLUMNS = {"record_id", "source_id", "available_at"}


class PointInTimeError(ValueError):
    """The input cannot be safely interpreted for a historical decision."""


def _utc_timestamp(value: str | datetime | pd.Timestamp, field: str) -> pd.Timestamp:
    if not isinstance(value, (str, datetime, pd.Timestamp)):
        raise PointInTimeError(f"{field} must be a timestamp with an explicit timezone.")
    try:
        stamp = pd.Timestamp(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise PointInTimeError(f"Invalid {field} timestamp.") from exc
    if pd.isna(stamp) or stamp.tzinfo is None:
        raise PointInTimeError(f"{field} must be a timestamp with an explicit timezone.")
    try:
        return stamp.tz_convert("UTC").as_unit("ns")
    except (ValueError, OverflowError) as exc:
        raise PointInTimeError(f"{field} is outside the supported timestamp range.") from exc


@dataclass(frozen=True)
class PointInTimeResult:
    """Selected records and a metadata-only audit of the filtering decision."""

    records: pd.DataFrame
    audit: pd.DataFrame
    decision_at: pd.Timestamp


def select_as_of(
    records: pd.DataFrame, *, decision_at: str | datetime | pd.Timestamp
) -> PointInTimeResult:
    """Select the latest available version of each record at decision_at.

    record_id identifies a logical record across revisions; source_id identifies
    its source. Each revision needs its own verified available_at. This function
    never derives availability from session_date, event_at or retrieved_at.
    Future records are excluded before selecting revisions. Invalid timestamps
    reject the whole input rather than silently treating bad records as safe.
    """
    cutoff = _utc_timestamp(decision_at, "decision_at")
    if not isinstance(records, pd.DataFrame):
        raise PointInTimeError("records must be a DataFrame.")
    if not records.columns.is_unique:
        raise PointInTimeError("Duplicate column names are not allowed.")
    missing = REQUIRED_COLUMNS - set(records.columns)
    if missing:
        raise PointInTimeError(f"Missing required columns: {', '.join(sorted(missing))}.")

    frame = records.copy(deep=True).reset_index(drop=True)
    for column in ("record_id", "source_id"):
        if not frame[column].map(lambda value: isinstance(value, str) and bool(value.strip())).all():
            raise PointInTimeError(f"{column} must contain non-empty strings.")
        if frame[column].map(lambda value: value != value.strip()).any():
            raise PointInTimeError(f"{column} must not have leading or trailing whitespace.")

    for column in ("available_at", "published_at"):
        if column in frame:
            frame[column] = pd.Series(
                [_utc_timestamp(value, column) for value in frame[column]],
                index=frame.index,
                dtype="datetime64[ns, UTC]",
            )
    if "published_at" in frame and (frame["published_at"] > frame["available_at"]).any():
        raise PointInTimeError("available_at must not precede published_at.")
    if frame.duplicated(["record_id", "available_at"]).any():
        raise PointInTimeError("Multiple versions share a record_id and available_at.")
    if (frame.groupby("record_id")["source_id"].nunique() > 1).any():
        raise PointInTimeError("Versions of a record_id must use the same source_id.")

    eligible = frame["available_at"] <= cutoff
    selected = (
        frame.loc[eligible]
        .sort_values("available_at", kind="stable")
        .drop_duplicates("record_id", keep="last")
    )
    audit = frame[["record_id", "source_id", "available_at"]].copy()
    audit["status"] = "future"
    audit.loc[eligible, "status"] = "superseded"
    audit.loc[selected.index, "status"] = "allowed"
    audit["decision_at"] = cutoff

    selected = selected.reset_index(drop=True)
    selected.attrs = dict(records.attrs)
    selected.attrs["decision_at"] = cutoff.isoformat()
    selected.attrs["availability_check"] = "available_at <= decision_at"
    return PointInTimeResult(records=selected, audit=audit, decision_at=cutoff)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a synthetic Point-in-Time filtering example")
    parser.add_argument("--demo", action="store_true", required=True)
    parser.parse_args()
    examples = pd.DataFrame([
        {
            "record_id": "example-report",
            "source_id": "synthetic-example",
            "available_at": "2024-07-01T09:00:00+07:00",
            "content": "Original report: sample value 100.",
        },
        {
            "record_id": "example-report",
            "source_id": "synthetic-example",
            "available_at": "2024-07-03T09:00:00+07:00",
            "content": "Revised report: sample value 120.",
        },
        {
            "record_id": "example-news",
            "source_id": "synthetic-example",
            "available_at": "2024-07-02T08:00:00+07:00",
            "content": "News available the next day.",
        },
    ])
    result = select_as_of(examples, decision_at="2024-07-01T16:00:00+07:00")
    print(json.dumps({
        "data_kind": "synthetic demonstration; not market data or research results",
        "decision_at": result.decision_at.isoformat(),
        "selected_records": json.loads(result.records.to_json(
            orient="records", date_format="iso", date_unit="ns"
        )),
        "audit": json.loads(result.audit.to_json(
            orient="records", date_format="iso", date_unit="ns"
        )),
    }, indent=2))


if __name__ == "__main__":
    main()
