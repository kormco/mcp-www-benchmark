"""Cache control utilities for ensuring clean experiment state."""

import subprocess
import sys


def flush_dns_cache() -> bool:
    """Flush the OS DNS cache. Returns True on success."""
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["ipconfig", "/flushdns"],
                capture_output=True, text=True, timeout=10,
            )
            return result.returncode == 0
        elif sys.platform == "darwin":
            result = subprocess.run(
                ["dscacheutil", "-flushcache"],
                capture_output=True, text=True, timeout=10,
            )
            return result.returncode == 0
        else:
            # Linux — systemd-resolved
            result = subprocess.run(
                ["resolvectl", "flush-caches"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                # Fallback for non-systemd
                result = subprocess.run(
                    ["nscd", "-i", "hosts"],
                    capture_output=True, text=True, timeout=10,
                )
            return result.returncode == 0
    except Exception:
        return False
