# Copied from hssling/india-state-tb-score (MIT), tools/fetch_sources.py, commit 05bcaa7; modified: rewritten for this project's manifest (author-supplied rows, trust-on-first-use digests, --copy-from, manual rows).
"""Download (only if missing) and SHA-256-verify the sources in data/source_manifest.csv.

Run as: python -I tools/fetch_sources.py [--copy-from DIR]   (stdlib only; standalone)

Manifest columns: file, url, bytes, sha256, retrieved_utc, note.
- url "author-supplied: ...": verify only, never fetched; a missing file is an error.
- note containing "fetch=manual": never fetched; verified (or pinned) if the author has placed it.
- empty sha256: trust on first use. The digest, size and date are written to the
  manifest when the file is first obtained; afterwards any mismatch is refused.
- --copy-from DIR: take a file named like the manifest entry from DIR instead of
  downloading it. The copy must pass the same digest check.
"""
import argparse
import csv
import datetime
import hashlib
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "source_manifest.csv"
FIELDS = ["file", "url", "bytes", "sha256", "retrieved_utc", "note"]
CHUNK = 1 << 20
AUTHOR = "author-supplied:"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def verify(path: Path, sha256: str) -> None:
    """Raise ValueError if the file's SHA-256 differs from the manifest digest
    (or if the manifest has no digest to compare with)."""
    if not sha256:
        raise ValueError(f"no pinned SHA-256 for {path}")
    actual = sha256_of(Path(path))
    if actual != sha256.lower():
        raise ValueError(f"SHA-256 mismatch for {path}: expected {sha256}, got {actual}")


def read_manifest(manifest: Path | None = None) -> list[dict]:
    with open(manifest or MANIFEST, newline="", encoding="utf-8") as f:
        return [{k: r.get(k, "") or "" for k in FIELDS} for r in csv.DictReader(f)]


def write_manifest(rows: list[dict], manifest: Path | None = None) -> None:
    with open(manifest or MANIFEST, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def _http_get(url: str, part: Path) -> None:
    part.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "acf-campaign-audit-fetch/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(part, "wb") as out:
        while block := resp.read(CHUNK):
            out.write(block)


def _install(part: Path, dest: Path, row: dict) -> None:
    """Check `part` against the row's digest (or pin it, if the row has none) and
    move it to `dest`. A refused file is deleted."""
    if row["sha256"]:
        try:
            verify(part, row["sha256"])
        except ValueError:
            part.unlink(missing_ok=True)
            raise
    else:
        row["sha256"] = sha256_of(part)
        row["bytes"] = str(part.stat().st_size)
        row["retrieved_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    part.replace(dest)


def _pin_existing(dest: Path, row: dict) -> None:
    row["sha256"] = sha256_of(dest)
    row["bytes"] = str(dest.stat().st_size)
    row["retrieved_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def process(row: dict, copy_from: Path | None) -> str:
    """Bring one manifest row to the verified state; return a status line.
    Raises ValueError (digest) or FileNotFoundError on failure."""
    dest = ROOT / row["file"]
    author = row["url"].startswith(AUTHOR)
    manual = "fetch=manual" in row["note"]
    if not dest.exists():
        if author:
            raise FileNotFoundError(f"author-supplied file missing: {row['file']}")
        part = dest.with_name(dest.name + ".part")
        local = copy_from / dest.name if copy_from else None
        if local is not None and local.is_file():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(local, part)
            how = f"copied from {copy_from}"
        elif manual:
            return f"manual, not yet present: {row['file']}"
        else:
            _http_get(row["url"], part)
            how = "downloaded"
        try:
            _install(part, dest, row)
        finally:
            part.unlink(missing_ok=True)
        return f"{how}: {row['file']}"
    if not row["sha256"]:
        if author:
            raise ValueError(f"author-supplied file has no pinned digest: {row['file']}")
        _pin_existing(dest, row)
        return f"pinned existing file: {row['file']}"
    verify(dest, row["sha256"])
    return f"verified: {row['file']}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--copy-from", type=Path, default=None,
                    help="directory holding verified local copies to use instead of downloading")
    args = ap.parse_args(argv)
    rows = read_manifest()
    failed = 0
    for row in rows:
        try:
            print(process(row, args.copy_from))
        except (ValueError, FileNotFoundError, OSError) as e:
            failed += 1
            print(f"FAILED {row['file']}: {e}", file=sys.stderr)
        write_manifest(rows)  # keep digests pinned so far even if a later row fails
    print(f"{len(rows) - failed} of {len(rows)} files verified")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
