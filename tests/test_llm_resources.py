"""Resource observations remain whole-machine sampled peaks, including errors."""

import json
import threading

import pytest

from pit_haf.research.resources import ResourceSampler


def observation(available=300, gpu_free=3072):
    return {"ram": {"status": "measured", "total_bytes": 1000, "available_bytes": available},
            "gpu": {"status": "measured", "query_output": f"GPU, 4096, {gpu_free}, driver"}}


@pytest.mark.parametrize("interval", [0, .1, 11, float("nan"), float("inf")])
def test_sampling_interval_is_finite_and_bounded(tmp_path, interval):
    with pytest.raises(ValueError):
        ResourceSampler(tmp_path, interval_seconds=interval)


def test_sampled_peak_scope_and_actual_intervals_are_preserved(tmp_path):
    calls = []
    def probe():
        calls.append(1)
        return observation() if len(calls) == 1 else observation(available=200, gpu_free=2048)
    with ResourceSampler(tmp_path, interval_seconds=10, probe=probe):
        pass
    summary = json.loads((tmp_path / "resource_summary.json").read_text())
    assert summary["sample_count"] == 2 and summary["machine_ram_used_peak_observed_bytes"] == 800
    assert summary["gpu_allocated_peak_observed_mib"] == {"0:GPU": 2048}
    assert "whole_machine_all_processes" in summary["scope"]
    assert "may miss spikes" in summary["peak_limitation"]
    assert summary["maximum_observed_gap_seconds"] is not None
    assert len((tmp_path / "resource_samples.jsonl").read_text().splitlines()) == 2


def test_probe_failures_are_counted_without_fabricated_zero_usage(tmp_path):
    def failed():
        raise OSError("GPU query unavailable")
    with ResourceSampler(tmp_path, interval_seconds=10, probe=failed):
        pass
    summary = json.loads((tmp_path / "resource_summary.json").read_text())
    assert summary["samples_with_errors"] == 2
    assert summary["machine_ram_used_peak_observed_bytes"] is None
    assert summary["gpu_allocated_peak_observed_mib"] is None


def test_periodic_probe_finishes_and_thread_stops(tmp_path):
    calls = []
    periodic = threading.Event()
    def probe():
        calls.append(1)
        if len(calls) >= 2:
            periodic.set()
        return observation()
    with ResourceSampler(tmp_path, interval_seconds=.25, probe=probe) as sampler:
        assert periodic.wait(2), "periodic sampler did not run"
    assert not sampler.thread.is_alive()
    assert sampler.summary()["sample_count"] >= 3


def test_interruption_still_writes_resources_and_propagates_error(tmp_path):
    with pytest.raises(RuntimeError, match="stop pilot"):
        with ResourceSampler(tmp_path, interval_seconds=10, probe=observation):
            raise RuntimeError("stop pilot")
    assert (tmp_path / "resource_summary.json").is_file()
