#!/usr/bin/env python3
"""Check portable release content without opening user configuration or using network."""
from pathlib import Path
import ast
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]

# Permit only the reviewed README illustration; other binary files remain blocked.
PUBLIC_IMAGE_HASHES = {
    "assets/octopus-researcher.png":
        "e17a177c19dfc89801151ed602df6a84a219a31d5b7d534e67b9a6467deb252a",
}


def release_files():
    # In a Git checkout, inspect exactly the tracked publication set.
    if (ROOT / ".git").exists():
        result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                                check=True, capture_output=True)
        return [ROOT / p.decode() for p in result.stdout.split(b"\0") if p]
    return [p for p in ROOT.rglob("*") if p.is_file()
            and not {".git", "__pycache__"} & set(p.relative_to(ROOT).parts)]


def check(files):
    errors = []
    forbidden = {"runtime", "services", ".venv", "node_modules", "__pycache__"}
    secret_patterns = [
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
        re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
        re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{35,}\b"),
    ]
    for path in files:
        relative = path.relative_to(ROOT)
        if path.is_symlink():
            errors.append(f"{relative}: symbolic link is not a portable release file")
            continue
        if forbidden & set(relative.parts) or (
            "local-sources" in relative.parts and "bin" in relative.parts
        ):
            errors.append(f"{relative}: private or installed runtime content")
        if (path.name.startswith(".env") and path.name != ".env.example") or path.suffix in {
            ".db", ".sqlite", ".log", ".pyc", ".pem", ".key"
        } or path.name in {"cookies.json", "auth.json", "preferences.local.md"}:
            errors.append(f"{relative}: private file type")
        if relative.as_posix() in PUBLIC_IMAGE_HASHES:
            data = path.read_bytes()
            if not data.startswith(b"\x89PNG\r\n\x1a\n") or (
                hashlib.sha256(data).hexdigest()
                != PUBLIC_IMAGE_HASHES[relative.as_posix()]
            ):
                errors.append(f"{relative}: image differs from reviewed asset")
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            errors.append(f"{relative}: unexpected binary")
            continue
        if re.search(r'(?<![A-Za-z0-9_])/Users/[A-Za-z0-9_.-]+/', text):
            errors.append(f"{relative}: machine-specific home directory")
        if any(pattern.search(text) for pattern in secret_patterns):
            errors.append(f"{relative}: possible credential (value not printed)")
        if path.suffix == ".py":
            try:
                ast.parse(text, filename=str(relative))
            except SyntaxError:
                errors.append(f"{relative}: Python syntax error")
        if path.suffix == ".md":
            for target in re.findall(r"\]\(([^)]+)\)", text):
                if "://" in target or target.startswith("#"):
                    continue
                target = target.split("#", 1)[0]
                if target and not (path.parent / target).exists():
                    errors.append(f"{relative}: broken local link {target}")
    for relative in [
        "LICENSE", "NOTICE.md", "skills/octopus/LICENSE", "skills/octopus/NOTICE.md",
        "skills/octopus/scripts/lib/vendor/bird-search/LICENSE",
    ]:
        if ROOT / relative not in files:
            errors.append(f"{relative}: missing attribution file")
    for name in ("octopus", "octopus-query-alias"):
        path = ROOT / "skills" / name / "SKILL.md"
        if path not in files or f"name: {name}\n" not in path.read_text():
            errors.append(f"{name}: missing or inconsistent skill identity")
    return errors


def main():
    files = release_files()
    errors = check(files)
    print(json.dumps({"checked_files": len(files), "errors": errors}, ensure_ascii=False, indent=2))
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
