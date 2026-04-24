"""
Tests for core.ast_shield v1.1.0.

Organized by threat category:
  1. Safe code (should pass cleanly)
  2. Import allowlist enforcement
  3. Forbidden call primitives
  4. Dunder / reflection escape attempts
  5. Aliasing attacks
  6. Syntax errors and edge cases
  7. Public API contract (ShieldResult shape, shield_gate)
"""

import pytest

from nova.core.ast_shield import (
    scan_code,
    shield_gate,
    Severity,
    Violation,
    ShieldResult,
    ALLOWED_IMPORT_ROOTS,
    FORBIDDEN_CALL_NAMES,
    FORBIDDEN_DUNDERS,
)


# ============================================================
# 1. Safe code — these MUST pass the shield
# ============================================================

class TestSafeCode:
    def test_empty_string_is_safe(self):
        result = scan_code("")
        assert result.safe is True
        assert result.violations == []

    def test_simple_arithmetic(self):
        result = scan_code("x = 1 + 2\nprint(x)")
        assert result.safe is True

    def test_allowed_import_math(self):
        result = scan_code("import math\nprint(math.pi)")
        assert result.safe is True
        assert "math" in result.imports_seen

    def test_allowed_import_from(self):
        result = scan_code("from math import sqrt\nprint(sqrt(4))")
        assert result.safe is True
        assert "math" in result.imports_seen

    def test_allowed_import_with_alias(self):
        result = scan_code("import numpy as np\nprint(np.array([1,2,3]))")
        assert result.safe is True
        assert "numpy" in result.imports_seen

    def test_matplotlib_submodule(self):
        result = scan_code("import matplotlib.pyplot as plt\nplt.plot([1,2])")
        assert result.safe is True

    def test_attribute_call_not_flagged(self):
        # re.compile() and list.remove() must not trip FORBIDDEN_CALL —
        # the module explicitly avoids flagging attribute calls by .attr name.
        result = scan_code("import re\np = re.compile('x')")
        assert result.safe is True

    def test_hashlib_allowed(self):
        # Comment in source confirms hashlib is allowlisted.
        result = scan_code("import hashlib\nhashlib.sha256(b'x').hexdigest()")
        assert result.safe is True


# ============================================================
# 2. Import allowlist
# ============================================================

class TestImportAllowlist:
    def test_os_import_blocked(self):
        result = scan_code("import os")
        assert result.safe is False
        codes = [v.code for v in result.violations]
        assert "IMPORT_NOT_ALLOWED" in codes

    def test_os_import_severity_high(self):
        result = scan_code("import os")
        v = result.violations[0]
        assert v.severity == Severity.HIGH

    def test_subprocess_blocked(self):
        result = scan_code("import subprocess")
        assert result.safe is False

    def test_socket_blocked(self):
        result = scan_code("import socket")
        assert result.safe is False

    def test_from_os_blocked(self):
        result = scan_code("from os import system")
        assert result.safe is False

    def test_relative_import_flagged(self):
        code = "from . import helper"
        result = scan_code(code)
        assert result.safe is False
        codes = [v.code for v in result.violations]
        assert "RELATIVE_IMPORT" in codes

    def test_relative_import_severity_medium(self):
        result = scan_code("from . import helper")
        rel = [v for v in result.violations if v.code == "RELATIVE_IMPORT"][0]
        assert rel.severity == Severity.MEDIUM

    def test_multiple_imports_one_line(self):
        # `import a, b.c` — both must be checked
        result = scan_code("import os, sys")
        codes = [v.code for v in result.violations]
        assert codes.count("IMPORT_NOT_ALLOWED") == 2

    def test_unknown_module_blocked(self):
        result = scan_code("import antigravity")
        assert result.safe is False


# ============================================================
# 3. Forbidden primitives (direct calls)
# ============================================================

class TestForbiddenCalls:
    @pytest.mark.parametrize("primitive", sorted(FORBIDDEN_CALL_NAMES))
    def test_direct_call_blocked(self, primitive):
        # Use a minimal call that is at least syntactically valid.
        code = f"{primitive}('x')"
        result = scan_code(code)
        assert result.safe is False, f"{primitive}() should be blocked"
        codes = [v.code for v in result.violations]
        assert "FORBIDDEN_CALL" in codes

    def test_eval_severity_critical(self):
        result = scan_code("eval('1+1')")
        v = [x for x in result.violations if x.code == "FORBIDDEN_CALL"][0]
        assert v.severity == Severity.CRITICAL

    def test_exec_blocked(self):
        result = scan_code("exec('x = 1')")
        assert result.safe is False


# ============================================================
# 4. Dunder / reflection escapes
# ============================================================

class TestDunderEscapes:
    def test_classic_subclasses_escape(self):
        code = "().__class__.__bases__[0].__subclasses__()"
        result = scan_code(code)
        assert result.safe is False
        codes = [v.code for v in result.violations]
        assert "DUNDER_ACCESS" in codes

    def test_mro_access(self):
        result = scan_code("x = [].__class__.__mro__")
        assert result.safe is False

    def test_globals_attr_access(self):
        result = scan_code("f.__globals__")
        assert result.safe is False

    def test_dunder_severity_critical(self):
        result = scan_code("().__class__")
        v = [x for x in result.violations if x.code == "DUNDER_ACCESS"][0]
        assert v.severity == Severity.CRITICAL

    @pytest.mark.parametrize("dunder", sorted(FORBIDDEN_DUNDERS))
    def test_each_forbidden_dunder(self, dunder):
        code = f"x.{dunder}"
        result = scan_code(code)
        codes = [v.code for v in result.violations]
        assert "DUNDER_ACCESS" in codes, f".{dunder} should be flagged"


# ============================================================
# 5. Aliasing attacks
# ============================================================

class TestAliasing:
    def test_getattr_alias_blocked(self):
        code = "g = getattr\ng(x, 'y')"
        result = scan_code(code)
        assert result.safe is False
        codes = [v.code for v in result.violations]
        assert "FORBIDDEN_ALIAS" in codes

    def test_eval_alias_blocked(self):
        code = "e = eval\ne('1+1')"
        result = scan_code(code)
        codes = [v.code for v in result.violations]
        assert "FORBIDDEN_ALIAS" in codes

    def test_alias_severity_critical(self):
        result = scan_code("e = eval")
        v = [x for x in result.violations if x.code == "FORBIDDEN_ALIAS"][0]
        assert v.severity == Severity.CRITICAL


# ============================================================
# 6. Syntax errors and edge cases
# ============================================================

class TestSyntaxAndEdges:
    def test_syntax_error_flagged(self):
        result = scan_code("def broken(:\n    pass")
        assert result.safe is False
        codes = [v.code for v in result.violations]
        assert "SYNTAX_ERROR" in codes

    def test_syntax_error_severity_medium(self):
        result = scan_code("def broken(:\n    pass")
        assert result.violations[0].severity == Severity.MEDIUM

    def test_syntax_error_returns_single_violation(self):
        # On syntax error we bail early; only the syntax violation is reported.
        result = scan_code("if\n")
        assert len(result.violations) == 1

    def test_multiple_violations_accumulate(self):
        code = "import os\nimport socket\neval('x')"
        result = scan_code(code)
        assert len(result.violations) >= 3

    def test_comment_only_is_safe(self):
        result = scan_code("# just a comment\n")
        assert result.safe is True


# ============================================================
# 7. Public API contract
# ============================================================

class TestPublicAPI:
    def test_scan_code_returns_shield_result(self):
        assert isinstance(scan_code(""), ShieldResult)

    def test_shield_result_has_expected_fields(self):
        r = scan_code("import math")
        assert hasattr(r, "safe")
        assert hasattr(r, "violations")
        assert hasattr(r, "imports_seen")
        assert hasattr(r, "highest_severity")

    def test_highest_severity_none_when_safe(self):
        r = scan_code("x = 1")
        assert r.highest_severity is None

    def test_highest_severity_escalates_to_critical(self):
        r = scan_code("import math\neval('1+1')")
        assert r.highest_severity == Severity.CRITICAL

    def test_shield_gate_passes_safe_code(self):
        ok, reason = shield_gate("import math")
        assert ok is True
        assert reason == "clear"

    def test_shield_gate_blocks_unsafe_code(self):
        ok, reason = shield_gate("import os")
        assert ok is False
        assert reason.startswith("blocked:")

    def test_shield_gate_truncates_long_violation_lists(self):
        # Generate 10 bad imports; gate should summarize first 5 and note "+N more"
        code = "\n".join(f"import bad{i}" for i in range(10))
        ok, reason = shield_gate(code)
        assert ok is False
        assert "more" in reason
