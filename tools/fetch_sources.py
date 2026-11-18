# Copied from hssling/india-state-tb-score (MIT), tools/fetch_sources.py, commit 05bcaa7; modified: rewritten for this project's manifest (author-supplied rows, trust-on-first-use digests, --copy-from, manual rows).
"""Download (only if missing) and SHA-256-verify the sources in data/source_manifest.csv.

Run as: python -I tools/fetch_sources.py [--copy-from DIR] [--pin]   (stdlib only; standalone)

Manifest columns: file, url, bytes, sha256, retrieved_utc, note.
- url "author-supplied: ...": never fetched; a missing file is an error. An empty digest
  is an error unless --pin is given, which content-checks and pins it (a '*' in the
  file name must resolve to exactly one file, whose name is then written).
- note containing "fetch=manual": never fetched; verified (or pinned) if the author has placed it.
- empty sha256 (fetch rows): trust on first use after a content check (no HTML pages). The digest, size and date are written to the
  manifest when the file is first obtained; afterwards any mismatch is refused.
- --copy-from DIR: take a file named like the manifest entry from DIR instead of
  downloading it. The copy must pass the same digest check.
"""
import argparse
import csv
import datetime
import hashlib
import os
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
    """Write the manifest through a temporary file and an atomic replace, so a
    failure while writing leaves the old manifest intact."""
    target = Path(manifest or MANIFEST)
    tmp = target.with_name(target.name + ".tmp")
    try:
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


_OLE2 = bytes.fromhex("D0CF11E0A1B11AE1")


def check_content(path: Path, name: str | None = None) -> None:
    """Refuse a file whose leading bytes do not fit its extension (typically an
    HTML interstitial saved in place of the file). Called before any digest is
    pinned. Extensions with no rule are not checked."""
    path = Path(path)
    with open(path, "rb") as f:
        head = f.read(64)
    ext = Path(name or path.name).suffix.lower()
    stripped = head.removeprefix(b"\xef\xbb\xbf").lstrip()
    if ext == ".pdf":
        ok = head.startswith(b"%PDF-")
    elif ext in (".docx", ".xlsx"):
        ok = head.startswith(b"PK\x03\x04")
    elif ext == ".xls":
        ok = head.startswith(_OLE2) or stripped.startswith(b"<?xml")
    elif ext in (".pgm", ".csv"):
        ok = bool(stripped) and not stripped.startswith(b"<")
    else:
        ok = True
    if not ok:
        raise ValueError(f"unexpected content (HTML?) in {path.name}")


def _http_get(url: str, part: Path) -> None:
    part.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "acf-campaign-audit-fetch/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(part, "wb") as out:
        while block := resp.read(CHUNK):
            out.write(block)


def _stamp(path: Path, row: dict) -> None:
    row["sha256"] = sha256_of(path)
    row["bytes"] = str(path.stat().st_size)
    row["retrieved_utc"] = datetime.datetime.fromtimestamp(
        path.stat().st_mtime, datetime.timezone.utc).strftime("%Y-%m-%d")


def _install(part: Path, dest: Path, row: dict) -> None:
    """Check `part` against the row's digest (or content-check and pin it, if the
    row has none) and move it to `dest`. A refused file is deleted."""
    try:
        if row["sha256"]:
            verify(part, row["sha256"])
        else:
            check_content(part, dest.name)
            _stamp(part, row)
    except ValueError:
        part.unlink(missing_ok=True)
        raise
    part.replace(dest)


def _resolve(row: dict) -> Path:
    """Path of an author-supplied row; a name with '*' must match exactly one file."""
    if "*" not in row["file"]:
        return ROOT / row["file"]
    matches = sorted(ROOT.glob(row["file"]))
    if not matches:
        raise FileNotFoundError(f"author-supplied file missing: {row['file']}")
    if len(matches) > 1:
        raise ValueError(f"{row['file']} matches {len(matches)} files; keep exactly one")
    return matches[0]


def _author(row: dict, pin: bool) -> str:
    dest = _resolve(row)
    if not dest.exists():
        raise FileNotFoundError(f"author-supplied file missing: {row['file']}")
    if row["sha256"]:
        verify(dest, row["sha256"])
        return f"verified: {row['file']}"
    if not pin:
        raise ValueError(f"author-supplied file has no pinned digest (use --pin): {row['file']}")
    check_content(dest)
    row["file"] = dest.relative_to(ROOT).as_posix()
    _stamp(dest, row)
    return f"pinned: {row['file']}"


def process(row: dict, copy_from: Path | None, pin: bool = False) -> str:
    """Bring one manifest row to the verified state; return a status line.
    Raises ValueError (digest, content) or FileNotFoundError on failure."""
    if row["url"].startswith(AUTHOR):
        return _author(row, pin)
    dest = ROOT / row["file"]
    manual = "fetch=manual" in row["note"]
    if not dest.exists():
        part = dest.with_name(dest.name + ".part")
        local = copy_from / dest.name if copy_from else None
        try:
            if local is not None and local.is_file():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(local, part)
                how = f"copied from {copy_from}"
            elif manual:
                return f"manual, not yet present: {row['file']}"
            else:
                _http_get(row["url"], part)
                how = "downloaded"
            _install(part, dest, row)
        finally:
            part.unlink(missing_ok=True)
        return f"{how}: {row['file']}"
    if not row["sha256"]:
        check_content(dest)
        _stamp(dest, row)
        return f"pinned existing file: {row['file']}"
    verify(dest, row["sha256"])
    return f"verified: {row['file']}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--copy-from", type=Path, default=None,
                    help="directory holding verified local copies to use instead of downloading")
    ap.add_argument("--pin", action="store_true",
                    help="pin author-supplied rows that have an empty digest")
    args = ap.parse_args(argv)
    rows = read_manifest()
    failed = 0
    for row in rows:
        try:
            print(process(row, args.copy_from, args.pin))
        except (ValueError, FileNotFoundError, OSError) as e:
            failed += 1
            print(f"FAILED {row['file']}: {e}", file=sys.stderr)
        write_manifest(rows)  # keep digests pinned so far even if a later row fails
    print(f"{len(rows) - failed} of {len(rows)} files verified")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
