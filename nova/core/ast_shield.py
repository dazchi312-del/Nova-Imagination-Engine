# ast_shield.py v1.1.0
# Location: nova/core/ast_shield.py
# Purpose: Static analysis gate for LLM-generated code, before sandbox execution.
#
# THREAT MODEL:
#   Defends against:
#     - Obvious direct attacks (import os; os.system(...))
#     - Common dunder-based sandbox escapes (__class__.__mro__...)
#     - Use of reflection primitives (getattr, __import__) as bypasses
#   Does NOT defend against:
#     - String-encoded attacks (chr(111)+chr(115) = "os")
#     - Runtime dynamic attacks (the container handles those)
#     - Resource exhaustion (the container handles those)
#     - Supply-chain attacks on allowed libraries (out of scope)
#
#   The AST Shield is a CODE-QUALITY FILTER, not the final security boundary.
#   The container (gVisor + read-only FS + network=none) is the real boundary.
#   The shield's job is to reject sloppy/obvious attacks fast and cheap.
#
# DESIGN CHOICE: ALLOWLIST, NOT BLOCKLIST.
#   Blocklists fail open — anything you didn't think of is permitted.
#   Allowlists fail closed — anything new requires explicit approval.
#   We choose allowlist because "fail closed" is the safe default for security.

import ast
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# === SEVERITY LEVELS ===
# Using an Enum instead of arbitrary floats. Each level has a clear meaning
# and downstream code (Reflector) can map severity → action explicitly.

class Severity(str, Enum):
    INFO = "info"         # noteworthy but not a violation
    LOW = "low"           # suspicious pattern, probably benign
    MEDIUM = "medium"     # clear policy violation, probably not exploitable
    HIGH = "high"         # known attack pattern or clear unsafe call
    CRITICAL = "critical" # reflection / sandbox-escape primitives


@dataclass
class Violation:
    """One finding. Structured so downstream tools can filter/group."""
    code: str             # short machine-readable code, e.g. "IMPORT_NOT_ALLOWED"
    message: str          # human-readable description
    severity: Severity
    line: int
    col: int = 0


@dataclass
class ShieldResult:
    safe: bool
    violations: list[Violation] = field(default_factory=list)
    imports_seen: list[str] = field(default_factory=list)

    @property
    def highest_severity(self) -> Optional[Severity]:
        if not self.violations:
            return None
        order = [Severity.INFO, Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
        return max(self.violations, key=lambda v: order.index(v.severity)).severity


# === ALLOWLIST ===
# Every module here was consciously added. Adding one is a policy decision,
# not a reflex. When the LLM needs a new module, review and add it deliberately.
#
# Note: submodules are matched by prefix. Adding "matplotlib" permits
# "matplotlib.pyplot", "matplotlib.patches", etc. If that's too broad for
# a given module, list exact submodules instead of the root.

ALLOWED_IMPORT_ROOTS: frozenset[str] = frozenset({
    # --- Numeric / scientific ---
    "math", "cmath", "decimal", "fractions", "statistics", "random",
    "numpy", "scipy", "pandas",
    # --- Visualization ---
    "matplotlib", "seaborn", "plotly",
    # --- Standard library: pure computation ---
    "collections", "itertools", "functools", "operator",
    "typing", "dataclasses", "enum",
    "re", "string", "textwrap", "unicodedata",
    "datetime", "calendar", "time",     # time.sleep is container-bounded anyway
    "json", "csv",                       # parsing only — no network implied
    "hashlib", "hmac", "secrets",        # crypto primitives, safe
    "base64", "binascii",
    # --- Imaging (if needed) ---
    "PIL",
})


# === FORBIDDEN PRIMITIVES ===
# These are not "modules" but specific Python reflection / code-execution
# primitives. Even without any import, these can be used to escape.

FORBIDDEN_CALL_NAMES: frozenset[str] = frozenset({
    "eval", "exec", "compile",
    "__import__",
    "getattr", "setattr", "delattr",     # reflection — the real escape vector
    "globals", "locals", "vars",
    "open",                               # file I/O (container also restricts)
    "input",                              # interactive; meaningless in sandbox
    "breakpoint",                         # would hang the container
})

# Dunder attributes that are characteristic of sandbox escapes.
# The classic escape: "".__class__.__mro__[1].__subclasses__()
FORBIDDEN_DUNDERS: frozenset[str] = frozenset({
    "__class__", "__bases__", "__mro__", "__subclasses__",
    "__globals__", "__builtins__",
    "__import__",
    "__getattribute__", "__getattr__",
    "__dict__",
    "__code__", "__func__",
    "__reduce__", "__reduce_ex__",       # pickle-based attacks
})


# === VISITOR ===

class SafetyVisitor(ast.NodeVisitor):
    """
    Walks an AST and records violations.

    EDUCATIONAL: ast.NodeVisitor dispatches to visit_<NodeType> for each
    node type. If we don't define a handler, generic_visit() recurses.
    The golden rule: ALWAYS call generic_visit() (or super().generic_visit())
    at the end of a visit_X method, or the subtree below won't be checked.
    """

    def __init__(self) -> None:
        self.violations: list[Violation] = []
        self.imports_seen: list[str] = []

    # ---- Imports ----

    def _check_import(self, full_name: str, line: int) -> None:
        """Shared logic for Import and ImportFrom."""
        self.imports_seen.append(full_name)
        root = full_name.split(".")[0]
        if root not in ALLOWED_IMPORT_ROOTS:
            self.violations.append(Violation(
                code="IMPORT_NOT_ALLOWED",
                message=f"import '{full_name}' is not on the allowlist",
                severity=Severity.HIGH,
                line=line,
            ))

    def visit_Import(self, node: ast.Import) -> None:
        # `import a, b.c as d` -> node.names = [alias("a"), alias("b.c", asname="d")]
        for alias in node.names:
            self._check_import(alias.name, node.lineno)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        # `from x.y import z` -> node.module = "x.y", node.names = [alias("z")]
        # `from . import x`   -> node.module = None, node.level = 1
        if node.level and node.level > 0:
            # Relative imports shouldn't occur in sandbox code; it has no package.
            self.violations.append(Violation(
                code="RELATIVE_IMPORT",
                message="relative imports are not allowed in sandbox code",
                severity=Severity.MEDIUM,
                line=node.lineno,
            ))
        elif node.module:
            self._check_import(node.module, node.lineno)
        self.generic_visit(node)

    # ---- Calls ----

    def visit_Call(self, node: ast.Call) -> None:
        # Direct name call: eval(...), exec(...), getattr(...)
        if isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_CALL_NAMES:
                self.violations.append(Violation(
                    code="FORBIDDEN_CALL",
                    message=f"call to forbidden primitive '{node.func.id}()'",
                    severity=Severity.CRITICAL,
                    line=node.lineno,
                    col=node.col_offset,
                ))
        # NOTE: we deliberately do NOT flag attribute calls by .attr name alone.
        # That produced false positives like re.compile() or list.remove().
        # Attribute-based risk is handled by visit_Attribute below, which can
        # inspect the full access chain.
        self.generic_visit(node)

    # ---- Attribute access (the real sandbox-escape surface) ----

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """
        Catches dunder-based escapes regardless of what they're attached to.
        Example: "".__class__.__mro__[1].__subclasses__()
                  ^^^ attr chain: __class__, __mro__, __subclasses__
        """
        if node.attr in FORBIDDEN_DUNDERS:
            self.violations.append(Violation(
                code="DUNDER_ACCESS",
                message=f"access to reflection dunder '.{node.attr}'",
                severity=Severity.CRITICAL,
                line=node.lineno,
                col=node.col_offset,
            ))
        self.generic_visit(node)

    # ---- Reassignment of dangerous names ----

    def visit_Assign(self, node: ast.Assign) -> None:
        """
        Catches `g = getattr` style aliasing of forbidden primitives.
        Without this check, the Call visitor only sees `g(...)` and passes.
        """
        if isinstance(node.value, ast.Name) and node.value.id in FORBIDDEN_CALL_NAMES:
            self.violations.append(Violation(
                code="FORBIDDEN_ALIAS",
                message=f"aliasing forbidden primitive '{node.value.id}'",
                severity=Severity.CRITICAL,
                line=node.lineno,
            ))
        self.generic_visit(node)


# === PUBLIC API ===

def scan_code(code: str) -> ShieldResult:
    """
    Parse and scan. Returns a ShieldResult.

    On syntax error: safe=False with a single SYNTAX_ERROR violation.
    Rationale: if it won't parse, we can't reason about it — don't let it past.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return ShieldResult(
            safe=False,
            violations=[Violation(
                code="SYNTAX_ERROR",
                message=f"{e.msg}",
                severity=Severity.MEDIUM,
                line=e.lineno or 0,
                col=e.offset or 0,
            )],
        )

    visitor = SafetyVisitor()
    visitor.visit(tree)

    return ShieldResult(
        safe=len(visitor.violations) == 0,
        violations=visitor.violations,
        imports_seen=visitor.imports_seen,
    )


def shield_gate(code: str) -> tuple[bool, str]:
    """
    Convenience wrapper for the sandbox. Returns (passed, reason_string).
    """
    result = scan_code(code)
    if result.safe:
        return True, "clear"
    summary = "; ".join(f"[{v.severity.value}] {v.code}: {v.message} (L{v.line})"
                        for v in result.violations[:5])
    more = "" if len(result.violations) <= 5 else f" (+{len(result.violations)-5} more)"
    return False, f"blocked: {summary}{more}"


# === SMOKE TEST ===
# Again: these print, they don't assert. Real tests belong in tests/.

if __name__ == "__main__":
    cases = {
        "safe_numeric": "import math\nprint(math.pi)",
        "safe_plot":    "import numpy as np\nimport matplotlib.pyplot as plt\nplt.plot([1,2,3])",
        "direct_os":    "import os\nos.system('id')",
        "getattr_bypass": "g = getattr\ng(__builtins__, 'eval')('1+1')",
        "dunder_escape": "().__class__.__bases__[0].__subclasses__()",
        "alias_eval":   "e = eval\ne('1+1')",
        "syntax_error": "def broken(:\n    pass",
        "unknown_mod":  "import hashlib\nprint(hashlib.sha256(b'x').hexdigest())",  # allowed now
        "wild_mod":     "import antigravity",
    }
    for name, code in cases.items():
        r = scan_code(code)
        print(f"{name:20s} safe={r.safe}  top={r.highest_severity}  "
              f"violations={len(r.violations)}")
        for v in r.violations:
            print(f"    [{v.severity.value}] {v.code} L{v.line}: {v.message}")
        print()

