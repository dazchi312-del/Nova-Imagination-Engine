"""
Nova App Builder Error Hierarchy
Designed for self-correction and autonomous problem-solving
"""

class NovaError(Exception):
    """Base exception for all Nova system failures."""
    pass

class NovaEngineError(NovaError):
    """AI inference failures - critical for planning phase."""
    pass

class NovaMemoryError(NovaError):
    """Memory layer failures - critical for project continuity."""
    pass

class NovaToolError(NovaError):
    """File/Code/System tool failures - critical for execution phase."""
    pass

class NovaConfigError(NovaError):
    """Configuration failures - critical for startup."""
    pass

class NovaPlanningError(NovaError):
    """Planning phase failures - specific to App Builder workflow."""
    pass

class NovaVerificationError(NovaError):
    """Self-test failures - critical for autonomous quality control."""
    pass
