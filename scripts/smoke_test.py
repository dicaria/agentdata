"""Offline checks for an installed wheel. Run with python -I scripts/smoke_test.py."""

import ast
import importlib
from importlib.metadata import distribution
import inspect
from pathlib import Path
import pkgutil
import re
import shlex
import subprocess
import sys
import sysconfig

import agentdata
from agentdata.cli import DOMAIN_ORDER, _CLI, build_parser
from agentdata.client import _Domain


def main():
    root = Path(__file__).resolve().parents[1]
    package = distribution("agentdata")
    assert not Path(agentdata.__file__).resolve().is_relative_to(root / "agentdata"), (
        "Imported the source tree instead of the installed wheel"
    )
    assert agentdata.__version__ == package.version, "Installed code and metadata versions differ"
    assert not package.requires, "The SDK must have zero runtime dependencies"

    expected_files = {
        path.relative_to(root).as_posix() for path in (root / "agentdata").rglob("*.py")
    }
    installed_files = {
        str(path).replace("\\", "/") for path in package.files if str(path).endswith(".py")
    }
    assert expected_files <= installed_files, f"Wheel is missing modules: {expected_files - installed_files}"
    for module in pkgutil.walk_packages(agentdata.__path__, prefix="agentdata."):
        importlib.import_module(module.name)

    entry_points = {
        entry.name: entry for entry in package.entry_points if entry.group == "console_scripts"
    }
    assert set(entry_points) == {"agentdata", *DOMAIN_ORDER}, "Missing or unexpected CLI entry points"
    scripts = Path(sysconfig.get_path("scripts"))
    suffix = ".exe" if sys.platform == "win32" else ""
    for name, entry in entry_points.items():
        assert callable(entry.load()), f"Entry point {name} does not resolve to a callable"
        subprocess.run(
            [str(scripts / (name + suffix)), "--help"],
            check=True, stdout=subprocess.DEVNULL, cwd=scripts,
        )
    for command in (
        [str(scripts / ("agentdata" + suffix))],
        [sys.executable, "-I", "-m", "agentdata"],
    ):
        result = subprocess.run(
            [*command, "--version"], check=True, capture_output=True, text=True, cwd=scripts,
        )
        assert result.stdout.strip() == f"agentdata {package.version}"

    # Parse examples without making upstream requests or creating a client/cache.
    readme = (root / "README.md").read_text(encoding="utf-8")
    python_examples = 0
    for snippet in re.findall(r"```python\n(.*?)```", readme, re.DOTALL):
        for node in ast.walk(ast.parse(snippet)):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            owner = node.func.value
            if (
                not isinstance(owner, ast.Attribute)
                or not isinstance(owner.value, ast.Name)
                or owner.value.id not in {"c", "c2"}
            ):
                continue
            domain, method = owner.attr, node.func.attr
            assert domain in DOMAIN_ORDER and method in {*_CLI[domain].FLAT, "search", "read"}, (
                f"Unknown README API: {domain}.{method}"
            )
            args = [ast.literal_eval(arg) for arg in node.args]
            kwargs = {arg.arg: ast.literal_eval(arg.value) for arg in node.keywords}
            inspect.signature(getattr(_Domain, method)).bind(None, *args, **kwargs)
            python_examples += 1

    parser = build_parser()
    cli_examples = 0
    for snippet in re.findall(r"```bash\n(.*?)```", readme, re.DOTALL):
        for line in snippet.splitlines():
            if line.startswith("agentdata "):
                parser.parse_args(shlex.split(line)[1:])
                cli_examples += 1
    assert python_examples and cli_examples, "README examples were not found"
    print(
        f"PASS: agentdata {package.version}, all modules, {len(entry_points)} CLI entry points, "
        f"{python_examples} Python examples, {cli_examples} CLI examples"
    )


if __name__ == "__main__":
    main()
