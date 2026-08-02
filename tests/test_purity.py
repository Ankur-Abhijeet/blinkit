"""
tests/test_purity.py — AST purity lint test for discovery/core/.
Principle 3 & architecture.md §1: Asserts discovery/core contains ZERO network, clock, or global RNG imports.
"""

import ast
import os
import glob
import pytest

FORBIDDEN_IMPORTS = {
    # Network / HTTP
    "socket", "requests", "httpx", "urllib", "aiohttp", "http",
    # Clock
    "time", "datetime",
    # Global RNG
    "random",
}


def get_imported_modules_from_file(filepath: str) -> set[str]:
    """Parses a Python file AST and extracts top-level module names imported."""
    with open(filepath, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=filepath)

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])
    return imports


def test_discovery_core_purity_ast():
    """Asserts that no file in discovery/core/ imports any forbidden I/O or non-deterministic module."""
    core_dir = os.path.join(os.path.dirname(__file__), "..", "discovery", "core")
    py_files = glob.glob(os.path.join(core_dir, "*.py"))

    assert len(py_files) > 0, "No python files found in discovery/core/"

    violations = {}
    for filepath in py_files:
        filename = os.path.basename(filepath)
        imported = get_imported_modules_from_file(filepath)
        forbidden = imported.intersection(FORBIDDEN_IMPORTS)
        if forbidden:
            violations[filename] = forbidden

    assert not violations, f"Purity violation! Forbidden I/O imports detected in discovery/core/: {violations}"
