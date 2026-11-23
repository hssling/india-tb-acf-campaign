"""--manuscript-dir for the manuscript tools: the default is manuscript/ext (the extension paper);
the audit-framed v1 manuscript stays usable with --manuscript-dir manuscript/v1_audit. Fixture
folders only; the private manuscript is never read."""
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from verification import check_all  # noqa: E402
from verification import check_docx_tie as tie  # noqa: E402
from verification import check_manuscript_numbers as cmn  # noqa: E402
from verification import mutate_manuscript as mm  # noqa: E402


def run(fn, *args, **kw) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = fn(*args, **kw)
    return code, buf.getvalue()


# ------------------------------------------------------------------ resolving the folder

def test_default_is_the_extension_manuscript():
    assert cmn.DEFAULT_MS_DIR == "manuscript/ext"
    assert cmn.manuscript_dir(ROOT, []) == (ROOT / "manuscript" / "ext", [])


def test_named_folder_relative_to_the_root_and_other_arguments_kept(tmp_path):
    d, rest = cmn.manuscript_dir(tmp_path, ["--regenerate", "--manuscript-dir", "manuscript/v1_audit"])
    assert d == tmp_path / "manuscript" / "v1_audit" and rest == ["--regenerate"]
    d, rest = cmn.manuscript_dir(tmp_path, [f"--manuscript-dir={tmp_path / 'x'}"])
    assert d == tmp_path / "x" and rest == []


def test_relative_name_for_messages(tmp_path):
    assert cmn.rel(tmp_path / "manuscript" / "ext", tmp_path) == "manuscript/ext"
    assert cmn.rel(Path("/elsewhere/m"), tmp_path).endswith("m")


# ------------------------------------------------------------------ check_manuscript_numbers

def test_numbers_check_skips_without_the_ext_folder_even_when_v1_is_present(tmp_path):
    v1 = tmp_path / "manuscript" / "v1_audit"
    v1.mkdir(parents=True)
    (v1 / cmn.MS_NAME).write_text("# T\n", encoding="utf-8")
    code, out = run(cmn.main, tmp_path, [])
    assert code == 0 and out.startswith("SKIPPED") and "manuscript/ext" in out


def test_numbers_check_reads_the_named_folder(tmp_path):
    v1 = tmp_path / "manuscript" / "v1_audit"
    v1.mkdir(parents=True)
    (v1 / cmn.MS_NAME).write_text("# T\n", encoding="utf-8")
    code, out = run(cmn.main, tmp_path, ["--manuscript-dir", "manuscript/v1_audit"])
    assert code == 1 and out.startswith("FAIL") and f"manuscript/v1_audit/{cmn.PHRASES}" in out


def test_numbers_check_regenerates_into_the_named_folder(tmp_path, monkeypatch):
    ms = tmp_path / "manuscript" / "v1_audit"
    ms.mkdir(parents=True)
    (ms / cmn.MS_NAME).write_text("# T\n", encoding="utf-8")
    (ms / cmn.PHRASES).write_text(json.dumps({"sections": {"Abstract": ["x"]}}), encoding="utf-8")
    monkeypatch.setattr(cmn, "golden", lambda text, root, required, profile="ext": {"about": "", "sections": {}})
    code, out = run(cmn.main, tmp_path, ["--manuscript-dir", "manuscript/v1_audit", "--regenerate"])
    assert code == 0 and (ms / cmn.SKELETON).exists() and not (tmp_path / "manuscript" / cmn.SKELETON).exists()
    assert "manuscript/v1_audit/" + cmn.SKELETON in out


def test_gold_and_other_files_are_read_from_the_folder(tmp_path):
    ms = tmp_path / "m"
    (ms / "exhibits").mkdir(parents=True)
    (ms / cmn.SKELETON).write_text(json.dumps({"sections": {"A": []}}), encoding="utf-8")
    (ms / "exhibits" / "tables.md").write_text("# Tables (generated)\n", encoding="utf-8")
    assert cmn.load_gold(ms) == {"A": []}
    assert cmn.load_others(ms) == {"exhibits/tables.md": "# Tables (generated)\n"}


# ------------------------------------------------------------------ check_docx_tie

def test_docx_tie_skips_without_the_ext_folder(tmp_path):
    (tmp_path / "manuscript" / "v1_audit" / "submission").mkdir(parents=True)
    code, out = run(tie.main, root=tmp_path, argv=[])
    assert code == 0 and out.startswith("SKIPPED") and "manuscript/ext" in out


def test_docx_tie_reads_the_named_folder(tmp_path, monkeypatch):
    v1 = tmp_path / "manuscript" / "v1_audit"
    (v1 / "submission").mkdir(parents=True)
    seen = []
    monkeypatch.setattr(tie, "problems", lambda ms_dir, root: seen.append(ms_dir) or ["MISSING: x"])
    code, out = run(tie.main, root=tmp_path, argv=["--manuscript-dir", "manuscript/v1_audit"])
    assert code == 1 and "MISSING: x" in out and seen == [v1]
    code, out = run(tie.main, root=tmp_path, argv=["--manuscript-dir", "manuscript/v1_audit", "--other"])
    assert code == 1 and out.startswith("FAIL")


# ------------------------------------------------------------------ the mutation harness

def test_mutation_harness_takes_the_folder(tmp_path):
    code, out = run(mm.main, ["--manuscript-dir", "manuscript/v1_audit"], root=tmp_path)
    assert code == 0 and out.startswith("SKIPPED") and "manuscript/v1_audit" in out
    code, out = run(mm.main, [], root=tmp_path)
    assert code == 0 and "manuscript/ext" in out


# ------------------------------------------------------------------ build_submission

def test_build_submission_paths_follow_the_folder(tmp_path):
    bs = pytest.importorskip("tools.build_submission")
    try:
        bs.configure(tmp_path / "m")
        assert (bs.MS, bs.EX, bs.OUT) == (tmp_path / "m", tmp_path / "m" / "exhibits", tmp_path / "m" / "submission")
        with pytest.raises(SystemExit, match="absent"):
            bs.main(["--manuscript-dir", str(tmp_path / "absent"), "--no-word"])
        assert not (tmp_path / "absent").exists()
    finally:
        bs.configure(ROOT / bs.DEFAULT_MS_DIR)
    assert bs.DEFAULT_MS_DIR == "manuscript/ext" and bs.MS == ROOT / "manuscript" / "ext"


def test_build_submission_set_follows_the_profile(tmp_path):
    bs = pytest.importorskip("tools.build_submission")
    try:
        bs.configure(tmp_path / "v1_audit")
        assert bs.LAY is bs.LAYOUTS["v1"] and bs.LAY.figures == ("03", "04") and bs.LAY.data
        bs.configure(tmp_path / "ext")
        assert bs.LAY is bs.LAYOUTS["ext"] and bs.LAY.figures == ("03", "04", "05", "06")
        assert bs.LAY.supplement == "07_supplementary_material.docx" and not bs.LAY.data
    finally:
        bs.configure(ROOT / bs.DEFAULT_MS_DIR)


def test_build_submission_out_option_and_frozen_folder(tmp_path):
    bs = pytest.importorskip("tools.build_submission")
    try:
        bs.configure(tmp_path / "m", tmp_path / "elsewhere")
        assert bs.OUT == tmp_path / "elsewhere" and bs.MS == tmp_path / "m"
        ms = tmp_path / "ms"
        (ms / "submission").mkdir(parents=True)
        (ms / "submission" / "SUBMITTED_2026-11-20.txt").write_text("manifest", encoding="utf-8")
        assert bs.frozen(ms / "submission") == ["SUBMITTED_2026-11-20.txt"]
        with pytest.raises(SystemExit, match="frozen"):
            bs.main(["--manuscript-dir", str(ms), "--no-word"])
        assert sorted(p.name for p in (ms / "submission").iterdir()) == ["SUBMITTED_2026-11-20.txt"]
        assert bs.frozen(tmp_path / "missing") == []
    finally:
        bs.configure(ROOT / bs.DEFAULT_MS_DIR)


def test_build_submission_ijtb_profile(tmp_path):
    bs = pytest.importorskip("tools.build_submission")
    d = tmp_path / "ext_v2"
    d.mkdir()
    (d / cmn.PHRASES).write_text(json.dumps({"profile": "ijtb", "sections": {"A": ["x"]}}), encoding="utf-8")
    try:
        bs.configure(d)
        assert bs.LAY is bs.LAYOUTS["ijtb"] and bs.LAY.figures == ("11", "12", "13", "14")
        assert bs.TIFF_DPI_IJTB == 600
    finally:
        bs.configure(ROOT / bs.DEFAULT_MS_DIR)


# ------------------------------------------------------------------ check_all and the v1 builders

def test_check_all_runs_the_manuscript_steps_on_ext():
    steps = dict(check_all.STEPS)
    for name in ("check_manuscript_numbers", "check_docx_tie"):
        assert steps[name][-2:] == ["--manuscript-dir", "manuscript/ext"]
    for name in ("check_manuscript_numbers [ijtb]", "check_docx_tie [ijtb]"):
        assert steps[name][-2:] == ["--manuscript-dir", "manuscript/ext_v2"]


def test_v1_builders_write_into_the_v1_folder():
    sys.path.insert(0, str(ROOT / "exhibits"))
    import make_tables as mt
    assert mt.OUT == ROOT / "manuscript" / "v1_audit" / "exhibits"
    pytest.importorskip("matplotlib")
    import make_figures as mf
    assert mf.OUT == ROOT / "manuscript" / "v1_audit" / "exhibits"
