"""
Test the App Builder foundational nervous system
"""

import sys
sys.path.insert(0, r"C:\Users\dazch\nova")

from nova.core.logger import session_logger, LogLevel
from nova.core.errors import NovaToolError, NovaPlanningError
from nova.core.config import config


def test_app_builder_thinking():
    session_logger.log("Starting App Builder foundation test", LogLevel.VISION)
    session_logger.log("Testing Layer 0 stability for autonomous building", LogLevel.PRODUCT)
    session_logger.log("Testing error hierarchy and logging system", LogLevel.ARCH)
    session_logger.log("Creating test structure", LogLevel.STRUCT)
    session_logger.log("Executing test code", LogLevel.CODE)

    try:
        raise NovaToolError("Simulated file permission error during scaffold_project()")
    except NovaToolError as e:
        session_logger.log(
            "Caught tool error - will self-correct",
            LogLevel.CODE,
            {"error": str(e), "action": "retry_with_elevated_permissions"}
        )

    try:
        raise NovaPlanningError("Architecture plan conflicts with existing project structure")
    except NovaPlanningError as e:
        session_logger.log(
            "Planning conflict detected",
            LogLevel.ARCH,
            {"error": str(e), "action": "revise_plan"}
        )

    session_logger.log(
        f"Engine: {config['engine']} | Model: {config['model']}",
        LogLevel.SYSTEM
    )

    session_logger.log(
        "App Builder foundation test complete",
        LogLevel.VISION,
        {"result": "Layer 0 ready for autonomous building"}
    )

    print("\n✅ App Builder foundation test complete")


if __name__ == "__main__":
    test_app_builder_thinking()
