"""System metrics collector — runs in a background thread during experiment runs."""

import threading
import time
from typing import List

import psutil

from config import METRICS_SAMPLE_INTERVAL
from src.models import SystemSample


class MetricsCollector:
    """Collects system metrics at regular intervals in a background thread."""

    def __init__(self, interval: float = METRICS_SAMPLE_INTERVAL):
        self.interval = interval
        self.samples: List[SystemSample] = []
        self._stop_event = threading.Event()
        self._thread = None
        self._process = psutil.Process()

    def start(self):
        self.samples = []
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._collect_loop, daemon=True)
        self._thread.start()

    def stop(self) -> List[SystemSample]:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        return self.samples

    def _collect_loop(self):
        net_before = psutil.net_io_counters()

        while not self._stop_event.is_set():
            try:
                cpu = self._process.cpu_percent()
                mem = self._process.memory_info().rss / (1024 * 1024)  # MB
                net = psutil.net_io_counters()

                # Open file descriptors — use num_handles on Windows
                try:
                    fds = self._process.num_handles()
                except AttributeError:
                    try:
                        fds = self._process.num_fds()
                    except Exception:
                        fds = 0

                sample = SystemSample(
                    timestamp=time.time(),
                    cpu_percent=cpu,
                    memory_rss_mb=round(mem, 2),
                    open_fds=fds,
                    net_bytes_sent=net.bytes_sent - net_before.bytes_sent,
                    net_bytes_recv=net.bytes_recv - net_before.bytes_recv,
                )
                self.samples.append(sample)
            except Exception:
                pass

            self._stop_event.wait(self.interval)

    def save_csv(self, filepath: str):
        with open(filepath, "w") as f:
            f.write(SystemSample.csv_header() + "\n")
            for s in self.samples:
                f.write(s.to_csv_row() + "\n")
