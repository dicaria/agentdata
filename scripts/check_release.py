"""Check source versions and an optional release tag (Python 3.11+)."""

import argparse
import ast
from pathlib import Path
import tomllib


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="Release tag, exactly v<package version>")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    module = ast.parse((root / "agentdata/__init__.py").read_text(encoding="utf-8"))
    versions = [
        ast.literal_eval(node.value)
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets)
    ]
    if versions != [project["version"]]:
        parser.error(f"version mismatch: pyproject={project['version']!r}, __init__={versions!r}")
    if args.tag is not None and args.tag != f"v{project['version']}":
        parser.error(f"tag mismatch: expected v{project['version']}, got {args.tag!r}")
    print(f"Versions match: {project['version']}" + (f" ({args.tag})" if args.tag else ""))


if __name__ == "__main__":
    main()
