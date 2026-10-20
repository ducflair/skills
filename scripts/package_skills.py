#!/usr/bin/env python3
"""
Packages individual skill folders into standalone archives for release.

For each skill folder:
1. Appends or updates the version inside the metadata block in SKILL.md:
   - metadata:
       version: "<version>"
2. Packages the whole folder into:
   - <skill_name>-<version>.tar.gz
   - <skill_name>-<version>.zip
3. Generates SHA-256 checksums in checksums.txt
"""

import argparse
import hashlib
import os
import re
import shutil
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path


def update_frontmatter_version(content: str, version: str) -> str:
    """Inject or update version strictly inside metadata block in YAML frontmatter."""
    match = re.match(r"^---\r?\n(.*?)\r?\n---(?:\r?\n|$)(.*)", content, re.DOTALL)
    if not match:
        raise ValueError("File does not start with valid '---' YAML frontmatter delimiters.")

    fm = match.group(1)
    body = match.group(2)

    # 1. Remove top-level 'version' if present
    fm = re.sub(r"^version:\s*.*$\r?\n?", "", fm, flags=re.MULTILINE)

    # 2. Update or append 'metadata.version'
    if re.search(r"^metadata:", fm, re.MULTILINE):
        if re.search(r"(^metadata:.*?\n\s+version:\s*).*$", fm, re.DOTALL | re.MULTILINE):
            fm = re.sub(
                r"(^metadata:.*?\n\s+version:\s*).*$",
                rf'\g<1>"{version}"',
                fm,
                flags=re.MULTILINE,
            )
        else:
            fm = re.sub(r"(^metadata:\s*)$", rf'\1\n  version: "{version}"', fm, flags=re.MULTILINE)
    else:
        fm = fm.rstrip() + f'\nmetadata:\n  version: "{version}"\n'

    # Reconstruct document
    return f"---\n{fm.strip()}\n---\n{body.lstrip()}"


def sha256_file(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def package_directory_tar(src_dir: Path, target_tar: Path, arcname: str) -> None:
    """Create a gzip tarball containing the whole folder."""
    with tarfile.open(target_tar, "w:gz") as tar:
        tar.add(src_dir, arcname=arcname)


def package_directory_zip(src_dir: Path, target_zip: Path, arcname: str) -> None:
    """Create a zip archive containing the whole folder."""
    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(src_dir):
            for file in files:
                full_path = Path(root) / file
                rel_path = full_path.relative_to(src_dir)
                zf.write(full_path, arcname=f"{arcname}/{rel_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Package skill folders for release.")
    parser.add_argument(
        "--version",
        required=True,
        help="Release version string (e.g. 0.1.0, without leading 'v')",
    )
    parser.add_argument(
        "--skills-dir",
        default="skills",
        help="Directory containing skill subfolders (default: skills)",
    )
    parser.add_argument(
        "--out-dir",
        default="dist",
        help="Directory to write release archives into (default: dist)",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Also write version metadata back to source SKILL.md files in the repository",
    )

    args = parser.parse_args()
    version = args.version.lstrip("v")
    skills_root = Path(args.skills_dir).resolve()
    out_dir = Path(args.out_dir).resolve()

    if not skills_root.is_dir():
        print(f"Error: skills directory not found: {skills_root}", file=sys.stderr)
        return 1

    skill_folders = [d for d in skills_root.iterdir() if d.is_dir() and not d.name.startswith(".")]
    if not skill_folders:
        print(f"Error: No skill folders found in {skills_root}", file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    created_files = []

    print(f"Packaging {len(skill_folders)} skill(s) for release version {version}...")

    with tempfile.TemporaryDirectory() as staging_tmp:
        staging_root = Path(staging_tmp)

        for folder in sorted(skill_folders, key=lambda p: p.name):
            skill_name = folder.name
            skill_md = folder / "SKILL.md"
            if not skill_md.is_file():
                print(f"Warning: Skipping {skill_name}, no SKILL.md found", file=sys.stderr)
                continue

            # Stage the whole folder
            staged_folder = staging_root / skill_name
            shutil.copytree(folder, staged_folder)

            # Update SKILL.md with version metadata
            content = skill_md.read_text(encoding="utf-8")
            updated_content = update_frontmatter_version(content, version)
            (staged_folder / "SKILL.md").write_text(updated_content, encoding="utf-8")

            if args.in_place:
                skill_md.write_text(updated_content, encoding="utf-8")

            # Archives to generate
            tar_versioned = out_dir / f"{skill_name}-{version}.tar.gz"
            zip_versioned = out_dir / f"{skill_name}-{version}.zip"

            package_directory_tar(staged_folder, tar_versioned, arcname=skill_name)
            package_directory_zip(staged_folder, zip_versioned, arcname=skill_name)

            created_files.extend([tar_versioned, zip_versioned])
            print(f"  ✓ {skill_name}: generated {tar_versioned.name}, {zip_versioned.name}")

    # Write checksums
    checksums_file = out_dir / "checksums.txt"
    checksum_lines = []
    for f in created_files:
        digest = sha256_file(f)
        checksum_lines.append(f"{digest}  {f.name}\n")

    checksums_file.write_text("".join(checksum_lines), encoding="utf-8")
    created_files.append(checksums_file)

    print(f"\nAll packages created in {out_dir}:")
    for f in created_files:
        print(f"  - {f.name} ({f.stat().st_size:,} bytes)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
