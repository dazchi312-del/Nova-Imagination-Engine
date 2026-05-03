#!/usr/bin/env python3
"""Validate every iter*_record.json under experiments/ against IterationRecord."""
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from nova.core.schemas import IterationRecord


def main() -> int:
    root = Path("experiments")
    if not root.exists():
        print("no experiments/ dir; nothing to check")
        return 0

    files = sorted(root.rglob("iter*_record.json"))
    if not files:
        print("no iter*_record.json files found")
        return 0

    failures = 0
    legacy = 0
    ok = 0
    for f in files:
        try:
            data = json.loads(f.read_text())
        except json.JSONDecodeError as e:
            failures += 1
            print(f"FAIL    {f}  (invalid JSON: {e})")
            continue

        version = data.get("schema_version")
        if version != 1:
            legacy += 1
            tag = f"v={version!r}" if version is not None else "no schema_version"
            print(f"LEGACY  {f}  ({tag})")
            continue

        try:
            IterationRecord.model_validate(data)
            ok += 1
            print(f"OK      {f}")
        except ValidationError as e:
            failures += 1
            print(f"FAIL    {f}")
            print(f"        {e.error_count()} error(s):")
            for err in e.errors():
                loc = ".".join(str(p) for p in err["loc"])
                print(f"          - {loc}: {err['msg']}")

    print(f"\n{len(files)} file(s): {ok} ok, {legacy} legacy, {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
