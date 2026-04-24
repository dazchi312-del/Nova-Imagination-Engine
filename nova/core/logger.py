"""
Nova Logger — Layer 0
Unified logging for the entire Nova system
Supports both old and new import styles
"""

import datetime

# ── Log Levels ──────────────────────────────────────────────
LEVELS = ["VISION", "ARCH", "PRODUCT", "CODE", "STRUCT"]

_current_level = "CODE"


# ── Core Functions ───────────────────────────────────────────

def set_level(level: str):
    global _current_level
    if level in LEVELS:
        _current_level = level


def _should_log(level: str) -> bool:
    if level not in LEVELS:
        return True
    return LEVELS.index(level) <= LEVELS.index(_current_level)


def _write(level: str, message: str):
    """Internal write — avoids name collision with session_logger.log()"""
    if _should_log(level):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{message}] {level}")


# Module-level alias
def log(level: str, message: str):
    _write(level, message)


# ── Log Level Constants ──────────────────────────────────────

class LogLevel:
    VISION  = "VISION"
    ARCH    = "ARCH"
    PRODUCT = "PRODUCT"
    CODE    = "CODE"
    STRUCT  = "STRUCT"
    # Legacy aliases
    SYSTEM  = "ARCH"
    INFO    = "ARCH"
    DEBUG   = "CODE"
    ERROR   = "VISION"
    WARNING = "VISION"


# ── Legacy Compatibility ─────────────────────────────────────

class _SessionLogger:
    """Compatibility wrapper — old code uses session_logger.log()"""

    def log(self, message: str, level: str = "ARCH", extra=None):
        _write(level, message)

    def info(self, message: str):
        _write("ARCH", message)

    def debug(self, message: str):
        _write("CODE", message)

    def error(self, message: str):
        _write("VISION", f"ERROR: {message}")

    def set_level(self, level: str):
        set_level(level)


# Single shared instance
session_logger = _SessionLogger()
