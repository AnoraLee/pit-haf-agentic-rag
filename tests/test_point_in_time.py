"""Temporal leakage and revision-selection checks using synthetic records."""

from datetime import date

import pandas as pd
import pytest

from pit_haf.data.point_in_time import PointInTimeError, select_as_of

CUTOFF = "2024-07-01T16:00:00+07:00"


@pytest.fixture
def records():
    return pd.DataFrame([
        {"record_id": "report", "source_id": "filings", "content": "original",
         "available_at": "2024-07-01T09:00:00+07:00"},
        {"record_id": "report", "source_id": "filings", "content": "future revision",
         "available_at": "2024-07-02T09:00:00+07:00"},
        {"record_id": "news", "source_id": "news", "content": "at cutoff",
         "available_at": "2024-07-01T09:00:00Z"},
    ])


def test_future_revision_is_not_returned_to_historical_analysis(records):
    records.attrs = {"snapshot": "example"}
    original = records.copy(deep=True)
    result = select_as_of(records, decision_at=CUTOFF)
    assert result.records["content"].tolist() == ["original", "at cutoff"]
    assert result.audit["status"].tolist() == ["allowed", "future", "allowed"]
    assert "content" not in result.audit
    assert result.records.attrs["snapshot"] == "example"
    pd.testing.assert_frame_equal(records, original)


def test_revision_becomes_eligible_only_after_its_availability(records):
    result = select_as_of(records, decision_at="2024-07-02T02:00:00Z")
    assert result.records.set_index("record_id").loc["report", "content"] == "future revision"
    assert result.audit["status"].tolist() == ["superseded", "allowed", "allowed"]


def test_timezone_equivalence_and_inclusive_cutoff(records):
    local = select_as_of(records, decision_at=CUTOFF)
    utc = select_as_of(records, decision_at="2024-07-01T09:00:00Z")
    pd.testing.assert_frame_equal(local.records, utc.records)
    assert "news" in utc.records["record_id"].tolist()


def test_no_available_records_returns_empty_selection(records):
    result = select_as_of(records, decision_at="2024-06-30T00:00:00Z")
    assert result.records.empty
    assert result.audit["status"].eq("future").all()


def test_empty_input_with_schema_is_valid():
    frame = pd.DataFrame(columns=["record_id", "source_id", "available_at", "content"])
    result = select_as_of(frame, decision_at=CUTOFF)
    assert result.records.empty and result.audit.empty
    assert str(result.records["available_at"].dtype) == "datetime64[ns, UTC]"


@pytest.mark.parametrize("value", [None, "bad", "2024-07-01", "2024-07-01T09:00:00", pd.NaT,
                                        date(2024, 7, 1), 1719824400, "3000-01-01T00:00:00Z"])
def test_unknown_or_naive_availability_rejects_entire_batch(records, value):
    records.loc[1, "available_at"] = value
    with pytest.raises(PointInTimeError, match="available_at"):
        select_as_of(records, decision_at=CUTOFF)


@pytest.mark.parametrize("value", [None, "bad", "2024-07-01", pd.NaT, 1719824400,
                                 "3000-01-01T00:00:00Z"])
def test_cutoff_needs_explicit_timezone(records, value):
    with pytest.raises(PointInTimeError, match="decision_at"):
        select_as_of(records, decision_at=value)


def test_session_and_retrieval_dates_are_not_invented_availability():
    frame = pd.DataFrame({"session_date": ["2024-01-01"]})
    frame.attrs["retrieved_at"] = "2026-10-06T00:00:00Z"
    with pytest.raises(PointInTimeError, match="available_at"):
        select_as_of(frame, decision_at=CUTOFF)


def test_old_reporting_period_does_not_override_late_publication(records):
    records["event_at"] = "2024-03-31"
    result = select_as_of(records.iloc[[1]], decision_at=CUTOFF)
    assert result.records.empty


def test_equivalent_timestamps_cannot_hide_conflicting_versions(records):
    records.loc[1, "available_at"] = "2024-07-01T02:00:00Z"
    with pytest.raises(PointInTimeError, match="Multiple versions"):
        select_as_of(records, decision_at=CUTOFF)


def test_availability_cannot_precede_publication(records):
    records["published_at"] = records["available_at"]
    records.loc[0, "published_at"] = "2024-07-01T10:00:00+07:00"
    with pytest.raises(PointInTimeError, match="precede published_at"):
        select_as_of(records, decision_at=CUTOFF)


def test_naive_publication_time_is_rejected(records):
    records["published_at"] = "2024-07-01"
    with pytest.raises(PointInTimeError, match="published_at"):
        select_as_of(records, decision_at=CUTOFF)


@pytest.mark.parametrize("column", ["record_id", "source_id"])
@pytest.mark.parametrize("value", [None, "", " ", " report ", 123])
def test_identifiers_need_unambiguous_strings(records, column, value):
    records.loc[0, column] = value
    with pytest.raises(PointInTimeError, match=column):
        select_as_of(records, decision_at=CUTOFF)


def test_record_revisions_cannot_change_source(records):
    records.loc[1, "source_id"] = "other-source"
    with pytest.raises(PointInTimeError, match="same source_id"):
        select_as_of(records, decision_at=CUTOFF)


def test_duplicate_dataframe_index_does_not_drop_other_records(records):
    records.index = [0, 0, 0]
    result = select_as_of(records, decision_at=CUTOFF)
    assert len(result.records) == 2
    assert len(result.audit) == 3


def test_input_order_does_not_choose_wrong_revision(records):
    result = select_as_of(records.iloc[::-1], decision_at="2024-07-02T09:00:00+07:00")
    assert result.records.set_index("record_id").loc["report", "content"] == "future revision"


def test_duplicate_columns_are_rejected(records):
    frame = pd.concat([records, records[["available_at"]]], axis=1)
    with pytest.raises(PointInTimeError, match="Duplicate column"):
        select_as_of(frame, decision_at=CUTOFF)


def test_non_dataframe_input_is_rejected():
    with pytest.raises(PointInTimeError, match="DataFrame"):
        select_as_of([], decision_at=CUTOFF)


def test_subsecond_future_record_is_not_rounded_into_the_cutoff(records):
    records.loc[2, "available_at"] = "2024-07-01T09:00:00.000000001Z"
    result = select_as_of(records, decision_at=CUTOFF)
    assert result.records["record_id"].tolist() == ["report"]
    assert result.audit.loc[2, "status"] == "future"
