# Adapted from hssling/india-state-tb-score (MIT), manuscript/render_check.ps1, commit 05bcaa7; modified: the Public Health submission file names; the folder is an argument
# Export the submission .docx files to PDF through Word (own instance) and report page and table counts.
# Usage: powershell -NoProfile -File render_check.ps1 [<submission dir>]   (default: manuscript\submission)
# PDFs go to <submission dir>\_render, one line per file, then the pages each table spans.
param([string]$Sub = (Join-Path (Split-Path $PSScriptRoot -Parent) "manuscript\submission"))
$rd = Join-Path $Sub "_render"
New-Item -ItemType Directory -Force $rd | Out-Null
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
  foreach ($n in "01_title_page", "02_manuscript_anonymised", "05_supplementary_material",
                 "06_cover_letter", "07_RECORD_checklist", "08_declaration_of_interests") {
    $d = $word.Documents.Open("$Sub\$n.docx", $false, $true)
    $d.Repaginate()
    $d.ExportAsFixedFormat("$rd\$n.pdf", 17)
    "$n pages=$($d.ComputeStatistics(2)) tables=$($d.Tables.Count)"
    $i = 0
    foreach ($t in $d.Tables) {
      $i++
      $first = $t.Range.Characters.First.Information(3)
      $last = $t.Range.Characters.Last.Information(3)
      "  table $i : rows $($t.Rows.Count), pages $first-$last"
    }
    $d.Close(0)
  }
} finally { $word.Quit() }
