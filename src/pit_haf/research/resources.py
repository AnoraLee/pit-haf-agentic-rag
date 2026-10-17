"""Sample whole-machine RAM/GPU allocation; these are observed, not exact peaks."""

import csv
import io
import json
import math
import statistics
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from pit_haf.research.doctor import hardware_report


class ResourceSampler:
    """Sample before/after and between calls; never claims process-specific usage.

    The interval is a wait after each probe, not a guaranteed sampling frequency.
    nvidia-smi may take up to its hardware_report timeout (5 seconds). Spikes
    between observations, or during an unavailable probe, can be missed.
    """

    def __init__(self, destination: Path, interval_seconds: float = 1.0, probe=None):
        if not math.isfinite(interval_seconds) or not .25 <= interval_seconds <= 10:
            raise ValueError("Resource sampling interval must be between 0.25 and 10 seconds.")
        self.destination = destination
        self.interval = interval_seconds
        self.probe = probe or hardware_report
        self.samples = []
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.thread = None
        self.started = None

    def sample(self) -> None:
        started = time.monotonic()
        sample = {
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": started - self.started,
            "machine_ram_used_bytes": None, "gpus": [], "errors": [],
        }
        try:
            report = self.probe()
            ram = report.get("ram", {})
            total, available = ram.get("total_bytes"), ram.get("available_bytes")
            if ram.get("status") == "measured" and isinstance(total, int) and isinstance(
                available, int,
            ) and total > 0 and 0 <= available <= total:
                sample["machine_ram_used_bytes"] = total - available
                sample["machine_ram_available_bytes"] = available
                sample["machine_ram_total_bytes"] = total
            else:
                sample["errors"].append({"component": "ram", "detail": ram})
            gpu = report.get("gpu", {})
            if gpu.get("status") == "measured":
                rows = csv.reader(io.StringIO(gpu.get("query_output", "")))
                for index, row in enumerate(rows):
                    try:
                        name, raw_total, raw_free, driver = row
                        total_mib, free_mib = float(raw_total), float(raw_free)
                        if not math.isfinite(total_mib) or not math.isfinite(free_mib) or not (
                            0 <= free_mib <= total_mib
                        ):
                            raise ValueError("Invalid GPU memory observations")
                        sample["gpus"].append({
                            "index": index, "name": name.strip(), "driver": driver.strip(),
                            "machine_allocated_mib": total_mib - free_mib,
                            "total_mib": total_mib, "free_mib": free_mib,
                        })
                    except (TypeError, ValueError) as exc:
                        sample["errors"].append({"component": "gpu", "detail": str(exc),
                                                 "row": row})
                if not sample["gpus"]:
                    sample["errors"].append({"component": "gpu", "detail": "No valid GPU row"})
            else:
                sample["errors"].append({"component": "gpu", "detail": gpu})
        except Exception as exc:
            sample["errors"].append({"component": "probe", "detail": str(exc),
                                     "error_type": type(exc).__name__})
        sample["probe_duration_seconds"] = time.monotonic() - started
        with self.lock:
            with (self.destination / "resource_samples.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(sample, ensure_ascii=False) + "\n")
            self.samples.append(sample)

    def _loop(self) -> None:
        while not self.stop.wait(self.interval):
            self.sample()

    def __enter__(self):
        self.destination.mkdir(parents=True, exist_ok=True)
        self.started = time.monotonic()
        self.sample()
        self.thread = threading.Thread(target=self._loop, name="pit-haf-resources", daemon=True)
        self.thread.start()
        return self

    def summary(self, *, background_still_running: bool = False) -> dict:
        with self.lock:
            samples = list(self.samples)
        ram = [item["machine_ram_used_bytes"] for item in samples
               if item["machine_ram_used_bytes"] is not None]
        gpu_peaks = {}
        for item in samples:
            for gpu in item["gpus"]:
                key = f"{gpu['index']}:{gpu['name']}"
                gpu_peaks[key] = max(gpu_peaks.get(key, 0), gpu["machine_allocated_mib"])
        gaps = [right["elapsed_seconds"] - left["elapsed_seconds"]
                for left, right in zip(samples, samples[1:])]
        return {
            "scope": "whole_machine_all_processes; not Ollama/process-specific",
            "sample_count": len(samples), "interval_wait_seconds": self.interval,
            "machine_ram_used_peak_observed_bytes": max(ram) if ram else None,
            "machine_ram_valid_sample_count": len(ram),
            "gpu_allocated_peak_observed_mib": gpu_peaks or None,
            "gpu_valid_sample_count": sum(bool(item["gpus"]) for item in samples),
            "samples_with_errors": sum(bool(item["errors"]) for item in samples),
            "component_error_count": sum(len(item["errors"]) for item in samples),
            "median_observed_gap_seconds": statistics.median(gaps) if gaps else None,
            "maximum_observed_gap_seconds": max(gaps) if gaps else None,
            "maximum_probe_seconds": max((item["probe_duration_seconds"] for item in samples),
                                         default=None),
            "background_still_running": background_still_running,
            "peak_limitation": "Observed sampled peak, may miss spikes. Other applications are "
                               "included. Interval follows probe completion, not fixed frequency.",
        }

    def __exit__(self, exc_type, exc, tb):
        self.stop.set()
        self.thread.join(timeout=6)
        running = self.thread.is_alive()
        if not running:
            self.sample()
        summary = self.summary(background_still_running=running)
        (self.destination / "resource_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        return False
