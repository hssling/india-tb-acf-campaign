# Copied from hssling/india-state-tb-score (MIT), tests/test_fetch.py, commit 05bcaa7;
# modified: tests added for trust-on-first-use digests, --copy-from and author-supplied rows.
# No test touches the network: downloads are replaced by a stub.
import csv
import hashlib

import pytest

from tools import fetch_sources


def test_verify_accepts_matching_digest(tmp_path):
    data = b"acf campaign"
    p = tmp_path / "f.bin"
    p.write_bytes(data)
    fetch_sources.verify(p, hashlib.sha256(data).hexdigest())


def test_verify_rejects_tampered_file(tmp_path):
    data = bytearray(b"acf campaign")
    digest = hashlib.sha256(bytes(data)).hexdigest()
    data[0] ^= 0x01
    p = tmp_path / "f.bin"
    p.write_bytes(bytes(data))
    with pytest.raises(ValueError):
        fetch_sources.verify(p, digest)


def test_verify_rejects_empty_digest(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"x")
    with pytest.raises(ValueError):
        fetch_sources.verify(p, "")


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(fetch_sources, "ROOT", tmp_path)
    monkeypatch.setattr(fetch_sources, "MANIFEST", tmp_path / "data" / "source_manifest.csv")

    def write(rows):
        with open(fetch_sources.MANIFEST, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fetch_sources.FIELDS, lineterminator="\n")
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in fetch_sources.FIELDS})

    def read():
        return fetch_sources.read_manifest()

    def no_network(*a, **k):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(fetch_sources.urllib.request, "urlopen", no_network)
    return tmp_path, write, read


def _stub_download(monkeypatch, payload):
    def fake(url, part):
        part.parent.mkdir(parents=True, exist_ok=True)
        part.write_bytes(payload)
    monkeypatch.setattr(fetch_sources, "_http_get", fake)


def test_first_download_pins_digest_then_refuses_mismatch(project, monkeypatch):
    root, write, read = project
    payload = b"first copy"
    write([{"file": "data_raw/a.csv", "url": "https://example.org/a.csv"}])
    _stub_download(monkeypatch, payload)
    assert fetch_sources.main([]) == 0
    row = read()[0]
    assert row["sha256"] == hashlib.sha256(payload).hexdigest()
    assert row["bytes"] == str(len(payload)) and row["retrieved_utc"]
    # tamper after pinning: verification must now fail
    (root / "data_raw" / "a.csv").write_bytes(b"changed")
    assert fetch_sources.main([]) == 1
    # a re-download that returns different bytes is refused and leaves no file
    (root / "data_raw" / "a.csv").unlink()
    _stub_download(monkeypatch, b"different")
    assert fetch_sources.main([]) == 1
    assert not (root / "data_raw" / "a.csv").exists()
    assert not (root / "data_raw" / "a.csv.part").exists()
    assert read()[0]["sha256"] == hashlib.sha256(payload).hexdigest()


def test_copy_from_checks_digest(project, monkeypatch):
    root, write, read = project
    src = root / "verified"
    src.mkdir()
    good = b"verified copy"
    (src / "ITR.pdf").write_bytes(good)
    write([{"file": "data_raw/itr/ITR.pdf", "url": "https://example.org/ITR.pdf",
            "sha256": hashlib.sha256(good).hexdigest()}])
    assert fetch_sources.main(["--copy-from", str(src)]) == 0
    assert (root / "data_raw" / "itr" / "ITR.pdf").read_bytes() == good
    # a wrong copy is refused and not installed
    (root / "data_raw" / "itr" / "ITR.pdf").unlink()
    (src / "ITR.pdf").write_bytes(b"tampered")
    assert fetch_sources.main(["--copy-from", str(src)]) == 1
    assert not (root / "data_raw" / "itr" / "ITR.pdf").exists()


def test_author_supplied_rows_are_verified_never_fetched(project):
    root, write, read = project
    data = b"pq answer"
    (root / "data_raw" / "pq").mkdir(parents=True)
    (root / "data_raw" / "pq" / "AU1.pdf").write_bytes(data)
    row = {"file": "data_raw/pq/AU1.pdf", "url": "author-supplied: sansad.in question archive",
           "sha256": hashlib.sha256(data).hexdigest()}
    write([row])
    assert fetch_sources.main([]) == 0
    (root / "data_raw" / "pq" / "AU1.pdf").write_bytes(b"altered")
    assert fetch_sources.main([]) == 1
    (root / "data_raw" / "pq" / "AU1.pdf").unlink()
    assert fetch_sources.main([]) == 1  # missing author-supplied file is an error, not a download


def test_manual_rows_are_not_fetched_when_missing(project):
    root, write, read = project
    write([{"file": "data_raw/ogd/q.csv", "url": "https://www.data.gov.in/resource/x",
            "note": "fetch=manual"}])
    assert fetch_sources.main([]) == 0
    assert not (root / "data_raw" / "ogd").exists()


def test_committed_manifest_is_wellformed():
    rows = fetch_sources.read_manifest(fetch_sources.ROOT / "data" / "source_manifest.csv")
    assert rows and len({r["file"] for r in rows}) == len(rows)
    assert not any(r["file"].startswith("data_raw/ogd/") for r in rows)
    for r in rows:
        assert r["file"].startswith("data_raw/") and r["url"]
        assert r["sha256"] == "" or len(r["sha256"]) == 64
        if r["url"].startswith("author-supplied:") and not r["sha256"]:
            assert "--pin" in r["note"]
    assert any(r["file"].endswith("doc20241228477601.pdf") and not r["sha256"] for r in rows)


def test_html_body_refused_before_pinning(project, monkeypatch):
    root, write, read = project
    write([{"file": "data_raw/s/x.docx", "url": "https://example.org/x.docx"}])
    _stub_download(monkeypatch, b"<!DOCTYPE html><html>challenge</html>")
    assert fetch_sources.main([]) == 1
    assert not (root / "data_raw" / "s" / "x.docx").exists()
    assert not (root / "data_raw" / "s" / "x.docx.part").exists()
    assert read()[0]["sha256"] == ""


def test_valid_zip_body_is_pinned(project, monkeypatch):
    root, write, read = project
    payload = b"PK\x03\x04rest of archive"
    write([{"file": "data_raw/s/x.docx", "url": "https://example.org/x.docx"}])
    _stub_download(monkeypatch, payload)
    assert fetch_sources.main([]) == 0
    assert read()[0]["sha256"] == hashlib.sha256(payload).hexdigest()


@pytest.mark.parametrize("name,body,ok", [
    ("a.pdf", b"%PDF-1.7", True), ("a.pdf", b"<html>", False),
    ("a.xlsx", b"PK\x03\x04", True), ("a.xlsx", b"<html>", False),
    ("a.xls", bytes.fromhex("D0CF11E0A1B11AE1") + b"x", True),
    ("a.xls", b"\xef\xbb\xbf <?xml version='1.0'?>", True),
    ("a.xls", b"<!DOCTYPE html>", False),
    ("a.csv", b"\xef\xbb\xbfa,b\n1,2", True), ("a.csv", b"  <html>", False),
    ("a.pgm", b"* program", True), ("a.pgm", b"<html>", False),
])
def test_check_content(tmp_path, name, body, ok):
    p = tmp_path / name
    p.write_bytes(body)
    if ok:
        fetch_sources.check_content(p)
    else:
        with pytest.raises(ValueError, match="unexpected content"):
            fetch_sources.check_content(p)


def test_write_manifest_failure_keeps_old_manifest(project):
    root, write, read = project
    write([{"file": "data_raw/a.csv", "url": "u"}])
    before = fetch_sources.MANIFEST.read_bytes()
    with pytest.raises(Exception):
        fetch_sources.write_manifest([object()])
    assert fetch_sources.MANIFEST.read_bytes() == before
    assert not list(fetch_sources.MANIFEST.parent.glob("*.tmp"))


def test_failed_download_leaves_no_part_file(project, monkeypatch):
    root, write, read = project
    write([{"file": "data_raw/a.csv", "url": "https://example.org/a.csv"}])

    def boom(url, part):
        part.parent.mkdir(parents=True, exist_ok=True)
        part.write_bytes(b"partial")
        raise OSError("connection reset")

    monkeypatch.setattr(fetch_sources, "_http_get", boom)
    assert fetch_sources.main([]) == 1
    assert not list((root / "data_raw").glob("*"))


def _pq_row(name="data_raw/pq/AU1900_*.pdf", sha=""):
    return {"file": name, "url": "author-supplied: sansad.in Rajya Sabha question archive",
            "sha256": sha}


def test_pin_required_for_empty_author_digest(project):
    root, write, read = project
    (root / "data_raw" / "pq").mkdir(parents=True)
    f = root / "data_raw" / "pq" / "AU1900_abc.pdf"
    f.write_bytes(b"%PDF-1.4 answer")
    write([_pq_row()])
    assert fetch_sources.main([]) == 1
    assert read()[0]["sha256"] == ""
    assert fetch_sources.main(["--pin"]) == 0
    row = read()[0]
    assert row["file"] == "data_raw/pq/AU1900_abc.pdf"
    assert row["sha256"] == hashlib.sha256(b"%PDF-1.4 answer").hexdigest()
    assert row["bytes"] == str(len(b"%PDF-1.4 answer")) and row["retrieved_utc"]
    # pinned rows verify; a mismatch is an error even with --pin and is never re-pinned
    assert fetch_sources.main([]) == 0
    f.write_bytes(b"%PDF-1.4 altered")
    assert fetch_sources.main(["--pin"]) == 1
    assert read()[0]["sha256"] == hashlib.sha256(b"%PDF-1.4 answer").hexdigest()


def test_pin_glob_needs_exactly_one_file_and_valid_content(project):
    root, write, read = project
    d = root / "data_raw" / "pq"
    d.mkdir(parents=True)
    write([_pq_row()])
    assert fetch_sources.main(["--pin"]) == 1  # zero matches
    (d / "AU1900_a.pdf").write_bytes(b"%PDF-1")
    (d / "AU1900_b.pdf").write_bytes(b"%PDF-2")
    assert fetch_sources.main(["--pin"]) == 1  # two matches
    (d / "AU1900_b.pdf").unlink()
    (d / "AU1900_a.pdf").write_bytes(b"<html>blocked</html>")
    assert fetch_sources.main(["--pin"]) == 1  # HTML, not a PDF
    assert read()[0]["sha256"] == ""
