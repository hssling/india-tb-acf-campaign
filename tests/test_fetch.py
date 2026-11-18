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
    for r in rows:
        assert r["file"].startswith("data_raw/") and r["url"]
        assert r["sha256"] == "" or len(r["sha256"]) == 64
        if r["url"].startswith("author-supplied:") or r["file"].startswith("data_raw/official/"):
            assert r["sha256"]
