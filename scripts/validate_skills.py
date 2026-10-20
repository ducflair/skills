#!/usr/bin/env python3
"""
Validates individual agent skill folders in the repository.

Checks each skill against the Agent Skills specification:
- Folder contains a SKILL.md file.
- Frontmatter is valid YAML delimited by '---'.
- 'name' field is required, kebab-case, <= 64 chars, and matches the parent folder name.
- 'description' field is required, non-empty, and <= 1024 chars.
- Whole folder contains self-contained files within size limits.
"""

import os
import re
import sys
from pathlib import Path

MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MiB per file safety limit
NAME_REGEX = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def parse_frontmatter(content: str) -> tuple[str, str]:
    """Extract frontmatter and remaining body from markdown content."""
    match = re.match(r"^---\r?\n(.*?)\r?\n---(?:\r?\n|$)(.*)", content, re.DOTALL)
    if not match:
        raise ValueError("File does not start with valid '---' YAML frontmatter delimiters.")
    return match.group(1), match.group(2)


def extract_field(frontmatter: str, field: str) -> str | None:
    """Extract a scalar field value from YAML frontmatter."""
    match = re.search(rf"^{re.escape(field)}:\s*(.+)$", frontmatter, re.MULTILINE)
    if not match:
        return None
    val = match.group(1).strip()
    # Strip quotes if present
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        val = val[1:-1]
    return val


def extract_metadata_version(frontmatter: str) -> str | None:
    """Extract version from metadata block or top-level."""
    meta_m = re.search(r"metadata:.*?\n\s+version:\s*['\"]?([^'\"\r\n]+)['\"]?", frontmatter, re.DOTALL)
    if meta_m:
        return meta_m.group(1).strip()
    return extract_field(frontmatter, "version")


def validate_skill_folder(skill_dir: Path) -> list[str]:
    """Validate an individual skill folder and return a list of error messages."""
    errors = []
    folder_name = skill_dir.name

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        errors.append(f"Missing required 'SKILL.md' file in {skill_dir}")
        return errors

    try:
        content = skill_md.read_text(encoding="utf-8")
    except Exception as e:
        errors.append(f"Unable to read SKILL.md: {e}")
        return errors

    try:
        fm, body = parse_frontmatter(content)
    except ValueError as e:
        errors.append(str(e))
        return errors

    # Validate name
    name = extract_field(fm, "name")
    if not name:
        errors.append("Frontmatter missing required 'name' field.")
    else:
        if name != folder_name:
            errors.append(f"'name' ('{name}') does not match parent folder name ('{folder_name}').")
        if len(name) > MAX_NAME_LENGTH:
            errors.append(f"'name' exceeds {MAX_NAME_LENGTH} characters ({len(name)} chars).")
        if not NAME_REGEX.match(name):
            errors.append(f"'name' ('{name}') must be lowercase alphanumeric and hyphens only.")

    # Validate description
    desc = extract_field(fm, "description")
    if not desc:
        errors.append("Frontmatter missing required 'description' field.")
    else:
        if len(desc) > MAX_DESCRIPTION_LENGTH:
            errors.append(
                f"'description' exceeds {MAX_DESCRIPTION_LENGTH} characters ({len(desc)} chars)."
            )

    # Validate whole folder files (no broken symlinks, size limits)
    for root, _, files in os.walk(skill_dir):
        for f in files:
            file_path = Path(root) / f
            try:
                stat = file_path.stat()
                if stat.st_size > MAX_FILE_BYTES:
                    errors.append(
                        f"File {file_path.relative_to(skill_dir)} exceeds maximum file size limit "
                        f"({stat.st_size} > {MAX_FILE_BYTES} bytes)."
                    )
            except Exception as e:
                errors.append(f"Cannot access file {file_path.relative_to(skill_dir)}: {e}")

    return errors


def main() -> int:
    skills_root = Path(__file__).resolve().parent.parent / "skills"
    if not skills_root.is_dir():
        print(f"Error: skills directory not found at {skills_root}", file=sys.stderr)
        return 1

    skill_folders = [d for d in skills_root.iterdir() if d.is_dir() and not d.name.startswith(".")]
    if not skill_folders:
        print("Error: No skill folders found under 'skills/'", file=sys.stderr)
        return 1

    print(f"Discovered {len(skill_folders)} skill folder(s) in {skills_root}:\n")

    total_errors = 0
    for folder in sorted(skill_folders, key=lambda p: p.name):
        errors = validate_skill_folder(folder)
        if errors:
            total_errors += len(errors)
            print(f"  ✗ {folder.name}: FAILED")
            for err in errors:
                print(f"      - {err}")
        else:
            skill_md = folder / "SKILL.md"
            fm, _ = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
            version = extract_metadata_version(fm)
            version_info = f"version: {version}, " if version else ""
            file_count = sum(len(files) for _, _, files in os.walk(folder))
            print(f"  ✓ {folder.name} ({version_info}{file_count} file(s)): PASSED")

    print()
    if total_errors > 0:
        print(f"Validation FAILED with {total_errors} error(s).", file=sys.stderr)
        return 1

    print(f"All {len(skill_folders)} skill folders validated successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
