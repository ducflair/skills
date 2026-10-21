#!/usr/bin/env python3
"""
Fetches and exports documentation for DUC and Scopture:
- High-level Fumadocs documentation (duc.ducflair.com, site.scopture.com) -> docs/
- ducpy API reference (ducflair.github.io/duc/reference/python/) -> docs-ducpy/
- DUC SQL schema reference (ducflair.github.io/duc/reference/sql/) -> docs-sql/

Preserves complete file hierarchy, generates llms.txt indexes, and ensures
100% offline availability inside skill bundles.
"""

import argparse
import concurrent.futures
import re
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

# Mapping of primary Fumadocs sites
SKILL_DOC_SOURCES = {
    "duc": "https://duc.ducflair.com",
    "scopture": "https://site.scopture.com",
}

DUCPY_BASE_URL = "https://ducflair.github.io/duc/reference/python/"
SQL_REF_URL = "https://ducflair.github.io/duc/reference/sql/"


def fetch_url(url: str, timeout: int = 25) -> str:
    """Fetch text content from a URL with English headers and strict error checking."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Ducflair Doc Exporter)",
            "Accept-Language": "en,en-US;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                raise RuntimeError(f"HTTP {resp.status} fetching {url}")
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} ({e.reason}) fetching {url}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error fetching {url}: {e.reason}") from e
    except TimeoutError as e:
        raise RuntimeError(f"Timeout ({timeout}s) fetching {url}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error fetching {url}: {e}") from e


def parse_fumadocs_sections(content: str) -> list[tuple[str, str, str]]:
    """Parse Fumadocs llms-full markdown into (title, rel_path, markdown_body)."""
    raw_sections = re.split(r"\n(?=# [^\n]+ \(/docs[^\)]*\))", content)
    pages = []

    for sec in raw_sections:
        sec = sec.strip()
        if not sec:
            continue
        m = re.match(r"^# ([^\n]+) \((/docs[^\)]*)\)", sec)
        if not m:
            continue
        title = m.group(1).strip()
        raw_path = m.group(2).strip()

        clean_path = re.sub(r"^/?docs/?", "", raw_path).strip()
        rel_path = "index.md" if not clean_path else f"{clean_path}.md"
        pages.append((title, rel_path, sec))

    return pages


def fetch_and_populate_skill_docs(skill_name: str, base_url: str, docs_dir: Path) -> int:
    """Fetch /llms.txt and all English documentation pages from base_url into docs_dir."""
    print(f"  Fetching main documentation for '{skill_name}' from {base_url}...")

    # 1. Fetch /llms.txt
    llms_url = f"{base_url.rstrip('/')}/llms.txt"
    llms_txt = fetch_url(llms_url)
    if not llms_txt or len(llms_txt.strip()) < 20:
        raise RuntimeError(f"Fetched /llms.txt for '{skill_name}' was empty or invalid.")

    # 2. Fetch /llms-full.txt
    full_url = f"{base_url.rstrip('/')}/llms-full.txt"
    full_content = fetch_url(full_url)
    if not full_content or len(full_content.strip()) < 50:
        raise RuntimeError(f"Fetched /llms-full.txt for '{skill_name}' was empty.")

    pages = parse_fumadocs_sections(full_content)
    if len(pages) < 3:
        raise RuntimeError(
            f"Expected >= 3 pages for '{skill_name}' from {full_url}, but found {len(pages)}."
        )

    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "llms.txt").write_text(llms_txt, encoding="utf-8")

    for _, rel_path, markdown in pages:
        target_path = docs_dir / rel_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(markdown, encoding="utf-8")

    print(f"    ✓ Added docs/llms.txt and {len(pages)} markdown page(s) into {docs_dir}")
    return len(pages)


def fetch_ducpy_reference(dest_dir: Path) -> int:
    """
    Fetch the complete ducpy Python reference documentation from
    https://ducflair.github.io/duc/reference/python/ into dest_dir (docs-ducpy/).
    """
    print(f"  Fetching ducpy Python reference from {DUCPY_BASE_URL}...")
    dest_dir.mkdir(parents=True, exist_ok=True)

    # 1. Fetch llms.txt index
    llms_url = f"{DUCPY_BASE_URL}llms.txt"
    llms_txt = fetch_url(llms_url)
    (dest_dir / "llms.txt").write_text(llms_txt, encoding="utf-8")

    # 2. Fetch llms-full.txt
    full_url = f"{DUCPY_BASE_URL}llms-full.txt"
    llms_full = fetch_url(full_url)
    (dest_dir / "llms-full.txt").write_text(llms_full, encoding="utf-8")

    # 3. Extract individual page links from llms.txt
    page_links = re.findall(r"\[([^\]]+)\]\(([^)]+\.html\.md)\)", llms_txt)
    if len(page_links) < 10:
        raise RuntimeError(f"Found only {len(page_links)} page links in ducpy llms.txt.")

    def fetch_single_page(link_tuple: tuple[str, str]) -> tuple[str, str]:
        title, rel = link_tuple
        page_url = f"{DUCPY_BASE_URL}{rel}"
        data = fetch_url(page_url)
        # Convert path from e.g. foo/bar.html.md -> foo/bar.md
        clean_rel = re.sub(r"\.html\.md$", ".md", rel)
        return clean_rel, data

    # Concurrently fetch all individual markdown pages
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(fetch_single_page, page_links))

    for clean_rel, content in results:
        file_path = dest_dir / clean_rel
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

    print(f"    ✓ Added docs-ducpy/llms.txt, llms-full.txt, and {len(results)} module page(s)")
    return len(results)


def _html_table_to_markdown(tbl_html: str) -> str:
    """Convert an HTML table string into a GitHub Flavored Markdown table."""
    rows = re.findall(r"<tr>(.*?)</tr>", tbl_html, re.DOTALL)
    md_rows = []
    for r in rows:
        cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", r, re.DOTALL)
        clean_cells = [re.sub(r"<[^>]+>", "", c).strip().replace("\n", " ") for c in cells]
        md_rows.append("| " + " | ".join(clean_cells) + " |")

    if len(md_rows) > 1:
        cols = md_rows[0].count("|") - 1
        sep = "| " + " | ".join(["---"] * cols) + " |"
        return md_rows[0] + "\n" + sep + "\n" + "\n".join(md_rows[1:])
    return "\n".join(md_rows)


def fetch_sql_reference(dest_dir: Path) -> int:
    """
    Fetch the DUC SQL schema reference from https://ducflair.github.io/duc/reference/sql/
    and convert it into clean Markdown (schema.md) and llms.txt inside dest_dir (docs-sql/).
    """
    print(f"  Fetching DUC SQL schema reference from {SQL_REF_URL}...")
    dest_dir.mkdir(parents=True, exist_ok=True)

    html = fetch_url(SQL_REF_URL)
    (dest_dir / "index.html").write_text(html, encoding="utf-8")

    table_blocks = re.split(r'<h3 id=\"([^\"]+)\" class=\"sq-table\">', html)
    tables_found = []

    md_parts = [
        "# DUC SQLite Schema Reference\n\n",
        "Authoritative relational schema documentation for `.duc` (gzip-compressed SQLite) files.\n",
        "Contains full table definitions, column types, default values, foreign keys, and ER diagrams.\n\n",
        "---\n\n",
    ]

    llms_lines = [
        "# DUC SQL Schema Reference\n",
        "> Complete SQLite schema reference for .duc containers, tables, views, and relationships.\n\n",
        "## Tables and Views\n\n",
    ]

    for i in range(1, len(table_blocks), 2):
        tbl_name = table_blocks[i]
        content = table_blocks[i + 1]
        tables_found.append(tbl_name)

        summary_m = re.search(r'<p class=\"summary\">(.*?)</p>', content)
        summary_text = summary_m.group(1).strip() if summary_m else "table"
        llms_lines.append(f"- [{tbl_name}](schema.md#{tbl_name}): {summary_text}")

        md_parts.append(f"## {tbl_name}\n\n")
        if summary_m:
            md_parts.append(f"*{summary_text}*\n\n")

        erd_m = re.search(r'<pre class=\"mermaid\">(.*?)</pre>', content, re.DOTALL)
        if erd_m:
            md_parts.append("```mermaid\n" + erd_m.group(1).strip() + "\n```\n\n")

        for tbl_match in re.finditer(
            r"<table>\s*(?:<caption[^>]*>(.*?)</caption>)?(.*?)</table>", content, re.DOTALL
        ):
            caption = tbl_match.group(1) or "Columns"
            caption_clean = re.sub(r"<[^>]+>", "", caption).strip()
            tbl_body = tbl_match.group(2)
            md_parts.append(f"### {caption_clean}\n\n")
            md_parts.append(_html_table_to_markdown(tbl_body) + "\n\n")

    if len(tables_found) < 30:
        raise RuntimeError(
            f"Expected >= 30 tables in SQL schema reference, but found {len(tables_found)}."
        )

    (dest_dir / "schema.md").write_text("".join(md_parts), encoding="utf-8")
    (dest_dir / "llms.txt").write_text("\n".join(llms_lines), encoding="utf-8")

    print(f"    ✓ Added docs-sql/llms.txt, schema.md, and index.html ({len(tables_found)} tables/views)")
    return len(tables_found)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch and export DUC, ducpy, and Scopture documentation."
    )
    parser.add_argument(
        "--target",
        choices=["duc", "scopture", "ducpy", "sql", "all"],
        default="all",
        help="Documentation target to export (default: all)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Directory to save the exported documentation folders",
    )
    parser.add_argument(
        "--to-skills",
        action="store_true",
        help="Directly populate skills/duc and skills/scopture doc directories",
    )

    args = parser.parse_args()

    out_base = Path("skills") if args.to_skills else args.out_dir
    if not out_base:
        parser.error("Please specify --out-dir <path> or --to-skills")

    try:
        if args.target in ("scopture", "all"):
            scopture_dir = out_base / "scopture" / "docs" if args.to_skills else out_base / "scopture" / "docs"
            fetch_and_populate_skill_docs("scopture", SKILL_DOC_SOURCES["scopture"], scopture_dir)

        if args.target in ("duc", "all"):
            duc_dir = out_base / "duc" if args.to_skills else out_base / "duc"
            fetch_and_populate_skill_docs("duc", SKILL_DOC_SOURCES["duc"], duc_dir / "docs")
            fetch_ducpy_reference(duc_dir / "docs-ducpy")
            fetch_sql_reference(duc_dir / "docs-sql")

        if args.target == "ducpy":
            target_dir = out_base / "duc" / "docs-ducpy" if args.to_skills else out_base / "docs-ducpy"
            fetch_ducpy_reference(target_dir)

        if args.target == "sql":
            target_dir = out_base / "duc" / "docs-sql" if args.to_skills else out_base / "docs-sql"
            fetch_sql_reference(target_dir)

    except Exception as e:
        print(f"\n[CRITICAL ERROR] Documentation export failed: {e}", file=sys.stderr)
        return 1

    print("\nDocumentation export successfully completed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
