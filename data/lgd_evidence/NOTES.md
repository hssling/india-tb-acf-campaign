# Notes on the LGD evidence

## 19 November 2026: cached copies, and the Delhi notice re-read

**Cached copies.** The §13 rule for the district denominator says the official notices are
"read online". Some notices are image-only or were not machine-readable through the web reader.
They were read from cached copies of the online documents, as `search_log.md` records: the
Delhi gazette, the Delhi Food, Supplies and Consumer Affairs order, the CEO Delhi map, the Ladakh
release, the Arunachal Act and the Assam notifications. The copies are the files the web reader
fetched from the URLs in `changes.csv` and `rows.csv`. They are kept outside the repository, under
`data_raw/lgd_evidence_cache/`, with their SHA-256 digests in
`data_raw/lgd_evidence_cache_sha256.txt`. They are not redistributed. The local path in
`search_log.md` was replaced by "the tool's local cache" on 19 November 2026, and the file was
re-pinned in `MANIFEST.txt`. No other change was made to it.

**Delhi notice (change DL-04, Shahdara abolished).** The notice is the Revenue Department
notification F. 223/SDM-II(HQ)/Land/2025/285 of 25 December 2025. It is printed in the Delhi
Gazette Extraordinary, Part IV, pages 20 to 33, and the online copy is
https://revenue.delhi.gov.in/sites/default/files/revenue/generic_multiple_files/268793_list.pdf.
The cached copy has SHA-256
`a4952090be78fca89a2c79d52908877a33de3b62bc06c4ca7e9e91c7210a0ca9` (file
`webfetch-1795028859226-4j9pvo.pdf`). Its 14 pages were rendered to images with PyMuPDF and read
by eye. This copy also has a text layer, and the text layer agrees with the images.

- **Supersession.** The notice opens: "In supersession of all previous notifications on the
  subject". Its second paragraph repeats the phrase for the Sub-Divisions.
- **Thirteen units.** It creates "thirty-nine (39) Sub-Divisions/ Tehsils and thirteen (13)
  Areas", co-terminous with the twelve MCD zones and one NDMC and Delhi Cantonment area.
- **Table I** (pages 20 to 21) lists 13 Areas: South East, Old Delhi, North, New Delhi, Central,
  Central North, South West, Outer North, North West, North East, East, South and West.
- **Shahdara is not an Area.** It appears only as Sub-Division 4 of North East (Table I) and as
  that Sub-Division in Table II. It also appears in revenue-village names.
- **What the notice does not say.** It uses "Areas", not "districts". It names no district as
  abolished. The notice refers to a Table III (MCD wards), which is not in these 14 pages. The
  Food, Supplies and Consumer Affairs order of 2 January 2026 cites this notification and calls
  the same 13 units "13 Revenue Districts".

**Result.** The notice agrees with the coding in `changes.csv`. Old Delhi, Central North and Outer
North were created (DL-01 to DL-03). Shahdara is absent from the complete list that the notice
fixes in supersession of all earlier notifications (DL-04). Shahdara's abolition remains an
inference, as DL-04 states. No count changes: Delhi had 11 districts on 7 December 2024 (13 now,
less 3 created, plus 1 abolished). The re-reading is recorded as row ADD-02 of
`data/source_choices.csv`.
