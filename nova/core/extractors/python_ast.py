"""
Python AST-based structural extractor.

Captures domain-agnostic structural metrics from Python source:
  - function_count (top-level), method_count (in classes, via raw)
  - class_count, import_count
  - ast_depth (statement-level nesting depth)
  - cyclomatic_complexity (decision-point estimate)

Produces a primary ShapeDescriptor classifying the artifact's dominant structure.
"""
from __future__ import annotations

import ast

from nova.core.extractors.base import ExtractionResult
from nova.core.schemas import ShapeDescriptor, StructuralMetadata


# AST node types that contribute a decision point to cyclomatic complexity.
_DECISION_NODES = (
    ast.If, ast.For, ast.While, ast.AsyncFor,
    ast.ExceptHandler, ast.With, ast.AsyncWith,
    ast.BoolOp,
    ast.IfExp,
    ast.comprehension,
)

# Statement-level nodes that represent meaningful nesting.
# Excludes expression/annotation subtrees that inflate depth without semantic weight.
_NESTING_NODES = (
    ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
    ast.If, ast.For, ast.AsyncFor, ast.While,
    ast.With, ast.AsyncWith, ast.Try, ast.ExceptHandler,
)


class _Visitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.function_count = 0   # top-level functions only
        self.method_count = 0     # functions defined inside a class
        self.class_count = 0
        self.import_count = 0
        self.complexity = 1       # base path
        self.max_depth = 0
        self._depth = 0
        self._class_stack = 0

    def generic_visit(self, node: ast.AST) -> None:
        nests = isinstance(node, _NESTING_NODES)
        if nests:
            self._depth += 1
            if self._depth > self.max_depth:
                self.max_depth = self._depth

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if self._class_stack > 0:
                self.method_count += 1
            else:
                self.function_count += 1
        elif isinstance(node, ast.ClassDef):
            self.class_count += 1
            self._class_stack += 1
            super().generic_visit(node)
            self._class_stack -= 1
            if nests:
                self._depth -= 1
            return
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            self.import_count += 1

        if isinstance(node, _DECISION_NODES):
            self.complexity += 1

        super().generic_visit(node)
        if nests:
            self._depth -= 1


def _classify_shape(v: _Visitor) -> ShapeDescriptor:
    """
    Heuristic primary-shape classification from raw counts.
    Confidence is a coarse signal, not a calibrated probability.
    """
    secondary: list[str] = []

    if v.class_count > 0:
        primary = "class-oriented"
        if v.method_count > 0:
            secondary.append("with-methods")
        if v.function_count >= 2:
            secondary.append("with-helpers")
    elif v.function_count >= 3:
        primary = "function-cluster"
    elif v.function_count > 0:
        primary = "small-functional"
    elif v.import_count > 0:
        primary = "import-only"
    else:
        primary = "script-flat"

    if v.complexity >= 10:
        secondary.append("high-complexity")
    elif v.complexity >= 5:
        secondary.append("moderate-complexity")

    if v.max_depth >= 5:
        secondary.append("deeply-nested")

    signal = v.function_count + v.method_count + v.class_count + v.import_count
    confidence = min(1.0, 0.3 + 0.1 * signal)

    return ShapeDescriptor(
        primary=primary,
        secondary=secondary,
        confidence=round(confidence, 3),
    )


class PythonASTExtractor:
    """Extractor for Python source artifacts."""

    name = "python_ast"

    def supports(self, filename: str, content: bytes) -> bool:
        if filename.endswith(".py"):
            return True
        # Sniff: many of our artifacts are unnamed code blobs.
        head = content[:256].lstrip()
        return head.startswith((b"import ", b"from ", b"def ", b"class ", b"#!"))

    def extract(self, filename: str, content: bytes) -> ExtractionResult:
        try:
            text = content.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return ExtractionResult(shape=None, structure=None)

        tree = ast.parse(text)  # may raise SyntaxError; caller wraps
        v = _Visitor()
        v.visit(tree)

        structure = StructuralMetadata(
            ast_depth=v.max_depth,
            cyclomatic_complexity=v.complexity,
            function_count=v.function_count,
            class_count=v.class_count,
            import_count=v.import_count,
            raw={"method_count": v.method_count},
        )
        shape = _classify_shape(v)
        return ExtractionResult(shape=shape, structure=structure)
