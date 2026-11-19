# Environment

The outputs of this study are to be produced with:

- Python 3.14.0
- pdfplumber 0.11.8
- pytest 9.0.0

The v1.0.0 analysis uses the Python standard library only. pdfplumber is used
for PDF table extraction only, and pytest for the tests. Every script is run as
`python -I <script>` from the repository root. The analysis pipeline
(`tools/fetch_sources.py`, `src/`, `verification/`) is cross-platform.

## Extension only

- numpy 2.3.5
- scipy 1.16.3

These are needed only for `src/ext/` and `verification/check_ext_outputs.py`
(the extension of v1.1.0). The v1.0.0 pipeline and its checks stay
standard-library only. The full extension build (`src/ext/` scripts, seeded
bootstraps) takes several minutes.

## Test-suite runtime

The full test suite (`python -I -m pytest -q`, run by
`python -I verification/check_all.py`) takes about 6 minutes, most of it in the
extension's bootstrap tests.

## Exhibits and the submission build only

These packages are needed only to draw the exhibits and to build the
submission files. No analysis output depends on them.

- matplotlib 3.10.7: the figures (`exhibits/make_figures.py`)
- openpyxl 3.1.5: the XLSX supplementary data workbook, and the mutation that
  edits it
- python-docx 1.2.0: the submission `.docx` files and the tests of the docx
  checks
- PyMuPDF 1.27.2.3 and Pillow 11.3.0: the TIFF copies of the figures in the
  submission build (the figure PDFs are rendered and saved as TIFF)
- pandoc 3.8.2.1 (on PATH, not a Python package): the submission build

`tools/build_submission.py`, `tools/render_check.ps1` and
`tools/word_count_word.ps1` drive Microsoft Word through PowerShell. They need
Windows with Microsoft Word installed (`tools/build_submission.py --no-word`
skips the Word counts). The tests and checks that need these
packages or the private manuscript skip when either is absent.
