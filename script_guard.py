"""Checks and runs the pandapower scripts uploaded to ``/import-pandapower``.

An uploaded script used to run with full Python builtins, so it could import ``os`` and
run commands on the server. Python cannot be sandboxed completely, so this module only
raises the bar:

1. The script is parsed and rejected when it imports a module outside ``ALLOWED_MODULES``,
   touches a private or dunder attribute, names a dangerous builtin, or calls one of the
   known file-reading/-writing and unpickling functions.
2. It then runs with a cut-down set of builtins and an ``__import__`` that only allows the
   same modules, so a check that misses something still meets a second wall.

Top-level ``if __name__ == "__main__":`` blocks are dropped before the checks: they never
ran on import (the script is not ``__main__``), and the samples keep local-only code there.

This is not a security boundary. A server that accepts scripts from untrusted users should
also run the import in an isolated worker without file or network access.
"""
from __future__ import annotations

import ast
import builtins
import importlib
import sys
import types
import uuid

ALLOWED_MODULES = frozenset({
    "__future__", "pandapower", "numpy", "pandas", "math", "cmath", "json", "collections",
    "itertools", "functools", "statistics", "datetime", "re", "typing", "dataclasses",
    "enum", "decimal", "fractions", "copy", "random", "string", "igraph",
})

# Builtins that can reach the interpreter, the file system or other modules.
FORBIDDEN_NAMES = frozenset({
    "exec", "eval", "compile", "open", "__import__", "globals", "locals", "vars",
    "setattr", "delattr", "input", "breakpoint", "help", "exit", "quit", "memoryview",
    "__builtins__", "__loader__", "__spec__",
})

# Attributes that lead to dangerous modules or read/write files or unpickle data.
FORBIDDEN_ATTRS = frozenset({
    # modules a library may have imported and expose as an attribute
    "os", "sys", "subprocess", "shutil", "socket", "builtins", "importlib", "ctypes",
    "ctypeslib", "pickle", "marshal", "io", "pathlib", "inspect", "code", "runpy",
    "multiprocessing", "threading", "signal", "tempfile", "glob", "distutils", "f2py",
    "io_utils", "file_io", "import_module", "system", "popen",
    # unpickling and loaders that can import arbitrary classes
    "from_pickle", "to_pickle", "from_json", "from_json_string", "from_json_dict",
    "from_excel", "from_sqlite", "from_sql", "from_postgresql", "from_file", "from_mpc",
    "loadtxt", "genfromtxt", "fromfile", "memmap", "load_workbook",
    # writers
    "to_json", "to_excel", "to_sqlite", "to_sql", "to_postgresql", "to_csv", "to_parquet",
    "to_hdf", "to_feather", "to_stata", "to_clipboard", "to_xml", "to_orc", "to_mpc",
    "tofile", "save", "savez", "savez_compressed", "savetxt", "savefig", "write",
    "write_html", "write_image", "to_html", "to_latex", "to_markdown",
})

# Keyword arguments that point a call at a file.
FORBIDDEN_KWARGS = frozenset({
    "filename", "file", "fname", "path", "filepath", "path_or_buf", "buf",
    "allow_pickle", "object_hook", "object_pairs_hook", "cls",
})

# Methods that write to a file when given a positional argument.
_WRITE_IF_ARGS = frozenset({"to_string"})

_SAFE_BUILTINS = (
    "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes", "callable", "chr",
    "classmethod", "complex", "dict", "divmod", "enumerate", "filter", "float", "format",
    "frozenset", "getattr", "hasattr", "hash", "hex", "id", "int", "isinstance",
    "issubclass", "iter", "len", "list", "map", "max", "min", "next", "object", "oct",
    "ord", "pow", "property", "range", "repr", "reversed", "round", "set", "slice",
    "sorted", "staticmethod", "str", "sum", "super", "tuple", "type", "zip",
    "__build_class__", "NotImplemented", "Ellipsis",
)


class ScriptRejected(ValueError):
    """The uploaded script uses something the import endpoint does not allow."""


def _root(module: str) -> str:
    return (module or "").split(".", 1)[0]


def _is_main_guard(node: ast.stmt) -> bool:
    if not isinstance(node, ast.If):
        return False
    test = node.test
    if not (isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq)):
        return False
    sides = [test.left, *test.comparators]
    has_name = any(isinstance(s, ast.Name) and s.id == "__name__" for s in sides)
    has_main = any(isinstance(s, ast.Constant) and s.value == "__main__" for s in sides)
    return has_name and has_main


def _bad_attr(name: str) -> bool:
    return name.startswith("_") or name in FORBIDDEN_ATTRS or name.startswith("read_")


class _Checker(ast.NodeVisitor):
    def __init__(self) -> None:
        self.problems: list[str] = []

    def _flag(self, node: ast.AST, message: str) -> None:
        self.problems.append(f"line {getattr(node, 'lineno', '?')}: {message}")

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if _root(alias.name) not in ALLOWED_MODULES:
                self._flag(node, f"import of '{alias.name}' is not allowed")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level:
            self._flag(node, "relative imports are not allowed")
        elif _root(node.module) not in ALLOWED_MODULES:
            self._flag(node, f"import from '{node.module}' is not allowed")
        for alias in node.names:
            if _bad_attr(alias.name) and alias.name != "annotations":
                self._flag(node, f"importing '{alias.name}' is not allowed")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in FORBIDDEN_NAMES:
            self._flag(node, f"'{node.id}' is not allowed")
        elif node.id.startswith("__") and node.id not in ("__name__", "__build_class__"):
            self._flag(node, f"'{node.id}' is not allowed")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if _bad_attr(node.attr):
            self._flag(node, f"attribute '.{node.attr}' is not allowed")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Name) and func.id in ("getattr", "hasattr"):
            name_arg = node.args[1] if len(node.args) > 1 else None
            if not (isinstance(name_arg, ast.Constant) and isinstance(name_arg.value, str)):
                self._flag(node, f"{func.id}() needs a literal attribute name")
            elif _bad_attr(name_arg.value):
                self._flag(node, f"{func.id}() of '{name_arg.value}' is not allowed")
        if isinstance(func, ast.Attribute):
            if func.attr in _WRITE_IF_ARGS and node.args:
                self._flag(node, f"'.{func.attr}()' with a file argument is not allowed")
            if func.attr in ("format", "format_map") and isinstance(func.value, ast.Constant) \
                    and isinstance(func.value.value, str) and ("._" in func.value.value or "[_" in func.value.value):
                self._flag(node, "format strings may not read private attributes")
        for kw in node.keywords:
            if kw.arg in FORBIDDEN_KWARGS:
                self._flag(node, f"keyword argument '{kw.arg}=' is not allowed")
        self.generic_visit(node)


def check_script(code: str) -> ast.Module:
    """Parse and check an uploaded script; return the tree to run.

    Raises ``ScriptRejected`` listing every problem found, or ``SyntaxError``.
    """
    tree = ast.parse(code, filename="<uploaded script>")
    tree.body = [stmt for stmt in tree.body if not _is_main_guard(stmt)]
    checker = _Checker()
    checker.visit(tree)
    if checker.problems:
        shown = checker.problems[:10]
        more = len(checker.problems) - len(shown)
        detail = "; ".join(shown) + (f"; and {more} more" if more > 0 else "")
        raise ScriptRejected(f"The script uses something the import does not allow: {detail}")
    return tree


def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level or _root(name) not in ALLOWED_MODULES:
        raise ImportError(f"import of '{name}' is not allowed")
    return importlib.__import__(name, globals, locals, fromlist, level)


def _restricted_builtins() -> dict:
    safe = {name: getattr(builtins, name) for name in _SAFE_BUILTINS if hasattr(builtins, name)}
    for name in dir(builtins):
        value = getattr(builtins, name)
        if isinstance(value, type) and issubclass(value, BaseException):
            safe[name] = value
    safe["__import__"] = _guarded_import
    safe["print"] = lambda *args, **kwargs: None  # uploaded scripts print progress; drop it
    return safe


def run_script(code: str) -> dict:
    """Check and run an uploaded script; return its namespace.

    When the script fails after it built ``net`` (for example its own power flow does not
    converge), the namespace is returned anyway so the topology can still be imported.
    """
    tree = check_script(code)
    compiled = compile(tree, "<uploaded script>", "exec")
    # Run as a throwaway module registered in sys.modules: dataclasses and typing look the
    # defining module up there while a class is created.
    module = types.ModuleType(f"electrisim_import_{uuid.uuid4().hex}")
    namespace = module.__dict__
    namespace["__builtins__"] = _restricted_builtins()
    sys.modules[module.__name__] = module
    try:
        exec(compiled, namespace)  # noqa: S102 - checked above; see the module docstring
    except Exception:
        if namespace.get("net") is None:
            raise
    finally:
        sys.modules.pop(module.__name__, None)
    return namespace
