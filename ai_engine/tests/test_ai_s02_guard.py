"""AI-S02 guard: nothing under src/ai_engine can reach a provider, network, process or import hook.

THIS IS NOT A SANDBOX. A static scan of the source cannot contain arbitrary Python. It can be
bypassed by code that the scan does not see, by a computed name, or by code loaded at runtime.
It is a regression check on first-party source. Running untrusted agent code needs process
isolation, which is a separate requirement (see docs/AI_ENGINE_AI_S02_REMEDIATION.md).

Imports are checked against an allowlist of the roots the engine needs (the census of src at
AI-S02 round 3). Anything not listed is refused, so a new module needs a deliberate change here.
The rules that do not depend on imports are a denylist of dynamic access: sys.modules and
__dict__ (also through an alias or getattr), dynamic getattr/setattr with a computed name,
vars/globals/locals, __import__, __builtins__, exec and eval.

The scan is static. It does not follow data passed between modules. Its self-tests check that each
form is flagged, so it cannot pass vacuously. The model_copy and model_construct rule applies
only to the AI-S02 files, because AI-1 code uses model_copy and re-validates its own output.
"""

from __future__ import annotations

import ast

import pytest
from conftest import AI_ENGINE_ROOT

PACKAGE_ROOT = AI_ENGINE_ROOT / "src" / "ai_engine"
AI_S02_FILES = (
    PACKAGE_ROOT / "contracts" / "semantic.py",
    *sorted((PACKAGE_ROOT / "llm").rglob("*.py")),
    *sorted((PACKAGE_ROOT / "llm_agents").rglob("*.py")),
)

# Top-level modules the engine may import. Everything else is refused. Census of src: __future__,
# typing, collections, pydantic, enum, dataclasses, json, datetime, pathlib, re, yaml, sys,
# hashlib, unicodedata, types, argparse, plus the package itself.
ALLOWED_ROOTS = frozenset(
    {
        "__future__",
        "ai_engine",
        "argparse",
        "collections",
        "dataclasses",
        "datetime",
        "enum",
        "hashlib",
        "json",
        "pathlib",
        "pydantic",
        "re",
        "sys",
        "types",
        "typing",
        "unicodedata",
        "yaml",
    }
)
# Attributes of sys that expose or replace the import and module state.
# yaml loaders that build arbitrary Python objects, or whose default loader does. Only
# yaml.safe_load, yaml.safe_load_all and yaml.SafeLoader are permitted. Checked through any alias of
# the yaml module, through from-imports and star-imports, and through getattr with a literal name.
YAML_FORBIDDEN_ATTRS = frozenset(
    {
        "load",
        "load_all",
        "full_load",
        "full_load_all",
        "unsafe_load",
        "unsafe_load_all",
        "Loader",
        "UnsafeLoader",
        "FullLoader",
    }
)
SYS_FORBIDDEN_ATTRS = frozenset({"modules", "__dict__", "__builtins__", "_getframe"})
# Names that give dynamic or unrestricted access to code, namespaces or the import machinery.
FORBIDDEN_NAMES = frozenset(
    {
        "ImportString",
        "__builtins__",
        "__import__",
        "exec",
        "eval",
        "compile",
        "vars",
        "globals",
        "locals",
        "import_module",
    }
)
# Attribute-style access that reaches module state or the import machinery.
FORBIDDEN_ATTRS = frozenset(
    {
        "__dict__",
        "__import__",
        "__builtins__",
        "import_module",
        # Object-graph escapes: reach loaders, globals, code objects or the class hierarchy.
        "__subclasses__",
        "__globals__",
        "__loader__",
        "__spec__",
        "__code__",
        "__class__",
        "__mro__",
        "__bases__",
        "__getattribute__",
        # Allowlisted yaml exposes unsafe loaders that build arbitrary Python objects.
        "unsafe_load",
        "unsafe_load_all",
        # yaml loaders that build Python objects. yaml.safe_load is the only permitted loader.
        "Loader",
        "UnsafeLoader",
        # pydantic ImportString imports any module named by a string at validation time.
        "ImportString",
        # Frame access: reach the caller's globals and builtins.
        "f_globals",
        "f_builtins",
        "f_locals",
        "f_back",
        "f_code",
        "tb_frame",
        "gi_frame",
        "cr_frame",
        "ag_frame",
    }
)
# Strings that, passed to a getattr-like call, name something forbidden.
SUSPECT_STRINGS = frozenset(
    {"modules", "__dict__", "__builtins__", "__import__"} | YAML_FORBIDDEN_ATTRS
)
DYNAMIC_ATTR_FUNCS = frozenset({"getattr", "setattr", "delattr", "hasattr"})
# Pydantic bypasses. Only checked in the AI-S02 files (see the module docstring).
BYPASS_ATTRS = frozenset({"model_copy", "model_construct"})


def _alias_names(tree: ast.AST, module: str) -> set[str]:
    """Names that refer to ``module``: its imports (with any alias) and simple reassignments."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == module:
                    names.add(alias.asname or module)
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name):
                if node.value.id in names:
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id not in names:
                            names.add(target.id)
                            changed = True
    return names


def violations(source: str, label: str, *, check_bypass: bool = False) -> list[str]:
    tree = ast.parse(source, filename=label)
    sys_names = _alias_names(tree, "sys")
    yaml_names = _alias_names(tree, "yaml")
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in ALLOWED_ROOTS:
                    found.append(f"{label}: imports {alias.name}, which is not on the allowlist")
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                if node.module.split(".")[0] not in ALLOWED_ROOTS:
                    found.append(f"{label}: imports from {node.module}, not on the allowlist")
                if node.module == "sys":
                    for alias in node.names:
                        if alias.name in SYS_FORBIDDEN_ATTRS or alias.name == "*":
                            found.append(f"{label}: imports sys.{alias.name}")
                if node.module == "yaml":
                    for alias in node.names:
                        if alias.name in YAML_FORBIDDEN_ATTRS or alias.name == "*":
                            found.append(f"{label}: imports yaml.{alias.name} (use safe_load)")
        elif isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES:
                found.append(f"{label}: uses {node.id}")
        elif isinstance(node, ast.Attribute):
            if node.attr in FORBIDDEN_ATTRS:
                found.append(f"{label}: uses .{node.attr}")
            if node.attr in YAML_FORBIDDEN_ATTRS and isinstance(node.value, ast.Name):
                if node.value.id in yaml_names:
                    found.append(f"{label}: uses yaml.{node.attr} through {node.value.id}")
            if node.attr in SYS_FORBIDDEN_ATTRS and isinstance(node.value, ast.Name):
                if node.value.id in sys_names:
                    found.append(f"{label}: uses sys.{node.attr} through {node.value.id}")
            if check_bypass and node.attr in BYPASS_ATTRS:
                found.append(f"{label}: uses .{node.attr}, which skips validation")
        elif isinstance(node, ast.keyword):
            # yaml.load(text, Loader=...) with any loader other than yaml.safe_load's is refused,
            # and the keyword names of the unsafe loaders are refused in any call.
            if node.arg in {"Loader", "UnsafeLoader"}:
                found.append(f"{label}: passes {node.arg}= (use yaml.safe_load)")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in DYNAMIC_ATTR_FUNCS and len(node.args) >= 2:
                name = node.args[1]
                if not isinstance(name, ast.Constant):
                    found.append(f"{label}: {func.id} with a computed attribute name")
                elif isinstance(name.value, str) and name.value in SUSPECT_STRINGS:
                    found.append(f"{label}: {func.id} names {name.value!r}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in FORBIDDEN_NAMES:
                found.append(f"{label}: string {node.value!r} reaches the import machinery")
    return found


def test_no_provider_or_unlisted_module_is_reachable_under_src() -> None:
    files = sorted(PACKAGE_ROOT.rglob("*.py"))
    assert files, "the scan found no source files; the guard would pass vacuously"
    assert any(path.name == "runner.py" for path in files)

    offenders: list[str] = []
    for path in files:
        source = path.read_text(encoding="utf-8")
        check_bypass = path in AI_S02_FILES
        offenders.extend(
            violations(source, str(path.relative_to(PACKAGE_ROOT)), check_bypass=check_bypass)
        )
    assert offenders == []


def test_ai_s02_files_are_all_in_the_scan() -> None:
    assert PACKAGE_ROOT / "llm" / "runner.py" in AI_S02_FILES
    assert PACKAGE_ROOT / "llm_agents" / "common.py" in AI_S02_FILES
    assert all(path.exists() for path in AI_S02_FILES)


# Each snippet is a source fixture. Each must be flagged.
FLAGGED = [
    # Original denylist: provider SDKs, HTTP, dynamic import machinery.
    pytest.param("import anthropic", id="sdk-anthropic"),
    pytest.param("from openai import OpenAI", id="sdk-openai"),
    pytest.param("import importlib", id="importlib"),
    pytest.param("from importlib import import_module", id="importlib-from"),
    pytest.param("x = __import__('anthropic')", id="dunder-import"),
    pytest.param("import builtins\nbuiltins.__dict__['__import__']('httpx')", id="builtins"),
    pytest.param("exec('import anthropic')", id="exec"),
    pytest.param("eval('1')", id="eval"),
    # Network clients the denylist missed in round 2.
    pytest.param("import urllib.request", id="urllib"),
    pytest.param("from urllib import request", id="urllib-from"),
    pytest.param("import http.client", id="http-client"),
    pytest.param("import socket", id="socket"),
    pytest.param("import ssl", id="ssl"),
    pytest.param("from ssl import create_default_context", id="ssl-from"),
    pytest.param("import xmlrpc.client", id="xmlrpc-client"),
    pytest.param("from xmlrpc import client", id="xmlrpc-from"),
    pytest.param("import ftplib", id="ftplib"),
    pytest.param("import smtplib", id="smtplib"),
    # Process, OS and native-code access.
    pytest.param("import asyncio", id="asyncio"),
    pytest.param("import subprocess", id="subprocess"),
    pytest.param("import os", id="os"),
    pytest.param("import os.path", id="os-path"),
    pytest.param("import ctypes", id="ctypes"),
    pytest.param("from ctypes import CDLL", id="ctypes-from"),
    pytest.param("import runpy", id="runpy"),
    pytest.param("from runpy import run_path", id="runpy-from"),
    pytest.param("import pkgutil", id="pkgutil"),
    # sys.modules through every route: direct, from-import, alias, reassignment, getattr, __dict__.
    pytest.param("import sys\nx = sys.modules['anthropic']", id="sys-modules"),
    pytest.param("from sys import modules", id="sys-modules-from"),
    pytest.param("from sys import modules as m", id="sys-modules-from-alias"),
    pytest.param("import sys as s\nx = s.modules['anthropic']", id="sys-modules-alias"),
    pytest.param("import sys\nm = sys\nx = m.modules", id="sys-modules-reassigned"),
    pytest.param("import sys\nx = getattr(sys, 'modules')", id="sys-modules-getattr"),
    pytest.param("import sys\nx = sys.__dict__", id="sys-dict"),
    pytest.param("import sys as s\nx = s.__dict__", id="sys-dict-alias"),
    # Dynamic attribute access and namespace access.
    pytest.param("x = getattr(obj, name)", id="getattr-computed"),
    pytest.param("setattr(obj, key, value)", id="setattr-computed"),
    pytest.param("x = vars()", id="vars"),
    pytest.param("x = globals()", id="globals"),
    pytest.param("f = getattr(obj, '__import__')", id="getattr-dunder-import"),
    pytest.param("d = globals()['__builtins__']", id="globals-builtins"),
    pytest.param("x = __builtins__", id="builtins-name"),
    pytest.param("d = {}\nd['__import__']('httpx')", id="string-dunder-import"),
    # Anything not on the allowlist, even if harmless.
    pytest.param("import yaml\nx = yaml.unsafe_load(text)", id="yaml-unsafe-load"),
    pytest.param("import yaml\nx = yaml.unsafe_load_all(text)", id="yaml-unsafe-load-all"),
    pytest.param("import yaml\nx = yaml.Loader", id="yaml-Loader"),
    pytest.param("import yaml\nx = yaml.UnsafeLoader", id="yaml-UnsafeLoader"),
    pytest.param("import yaml\nyaml.load(text, Loader=yaml.SafeLoader)", id="yaml-load-Loader-kw"),
    pytest.param("import yaml\nyaml.load(text, Loader=yaml.Loader)", id="yaml-load-Loader-unsafe"),
    pytest.param("import yaml\nyaml.load(text, UnsafeLoader=1)", id="yaml-UnsafeLoader-kw"),
    pytest.param(
        "from pydantic import ImportString\nclass M:\n    x: ImportString",
        id="pydantic-ImportString-annotation",
    ),
    pytest.param("import pydantic\nx: pydantic.ImportString", id="pydantic-ImportString-attr"),
    pytest.param("import csv", id="allowlist-csv"),
    pytest.param("import shutil", id="allowlist-shutil"),
    pytest.param("import tempfile", id="allowlist-tempfile"),
]


@pytest.mark.parametrize("snippet", FLAGGED)
def test_detector_flags_each_forbidden_form(snippet: str) -> None:
    assert violations(snippet, "snippet.py"), f"not flagged: {snippet!r}"


@pytest.mark.parametrize(
    "snippet",
    [
        "result = obj.model_copy(update={'x': 1})",
        "result = obj.model_construct(x=1)",
    ],
)
def test_bypass_methods_are_flagged_in_ai_s02_files(snippet: str) -> None:
    assert violations(snippet, "semantic.py", check_bypass=True)


@pytest.mark.parametrize(
    "snippet",
    [
        "result = obj.model_copy(update={'x': 1})",
        "result = obj.model_construct(x=1)",
    ],
)
def test_bypass_methods_are_allowed_outside_ai_s02_files(snippet: str) -> None:
    # AI-1 code uses model_copy and re-validates its own output, so the rule is scoped.
    assert violations(snippet, "demo/workflow.py", check_bypass=False) == []


def test_allowed_code_is_not_flagged() -> None:
    clean = (
        "from __future__ import annotations\nimport json\nimport sys\n"
        "from ai_engine.llm.port import LLMPort\nimport re\nfrom pydantic import Field\n"
        "name = sys.version_info\nx = getattr(obj, 'field_name')\n"
    )
    assert violations(clean, "clean.py", check_bypass=True) == []


def test_relative_import_is_not_judged_by_the_allowlist() -> None:
    # A relative import stays inside the package, so it is not an external module.
    assert violations("from . import socket_helpers\n", "relative.py") == []


def test_an_absolute_import_with_a_similar_name_is_refused_by_the_allowlist() -> None:
    # The allowlist is exact: a look-alike name is not a listed root, so it is refused.
    assert violations("import socket_helpers\n", "local.py")


def test_scan_reads_the_real_package_files() -> None:
    # The scan must see the real modules. A wrong root would pass every check vacuously.
    scanned = {path.relative_to(PACKAGE_ROOT).as_posix() for path in PACKAGE_ROOT.rglob("*.py")}
    assert {"contracts/source.py", "specialists/base.py", "llm/runner.py"} <= scanned
