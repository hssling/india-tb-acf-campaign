# Adapted from hssling/india-state-tb-score (MIT), manuscript/word_count_word.ps1, commit 05bcaa7; modified: Public Health limits; the main text ends at the first heading after Discussion; a text box (a "Box N." heading) counts in the main text; JSON keys per section
# Count the abstract and the main text of the anonymised manuscript in Microsoft Word.
# Usage: powershell -NoProfile -File word_count_word.ps1 <docx> <out.json>
# Opens its own Word instance (read-only, hidden) and quits only that instance.
# Abstract: the paragraphs between the "Abstract" heading and the Keywords line (its run-in
# headings Objectives ... Conclusions included, Keywords excluded).
# Main text: Introduction to Discussion (and Conclusions, as in the IJTB set), headings excluded, run-in bold subheadings included,
# plus the text of a text box (a heading "Box N. ...", counted under "Box"); it ends at any
# other heading (Acknowledgements). Tables and the placement markers ("[Table 1 about here]")
# are not counted.
param([string]$Docx, [string]$Out)
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
  $d = $word.Documents.Open($Docx, $false, $true)
  $state = ""; $abs = 0; $main = 0; $sec = [ordered]@{}; $cur = ""
  foreach ($p in $d.Paragraphs) {
    $t = $p.Range.Text.Trim()
    $isHeading = $p.OutlineLevel -lt 10
    if ($isHeading) {
      if ($t -eq "Abstract") { $state = "abs" }
      elseif ($t -in @("Introduction", "Methods", "Results", "Discussion", "Conclusions")) { $state = "main"; $cur = $t; $sec[$t] = 0 }
      elseif ($t -match '^Box \d+\.') { $state = "main"; $cur = "Box"; $sec["Box"] = 0 }
      else { $state = "" }
      continue
    }
    if ($t -like "Keywords:*") { $state = "" ; continue }
    if ($t -match '^\[(Table|Figure) \d+ about here\]$') { continue }   # placement markers are not counted
    if ($p.Range.Information(12)) { continue }          # inside a table
    $n = $p.Range.ComputeStatistics(0)
    if ($state -eq "abs") { $abs += $n }
    if ($state -eq "main") { $main += $n; $sec[$cur] += $n }
  }
  $pages = $d.ComputeStatistics(2)
  $d.Close(0)
  $parts = @()
  foreach ($k in $sec.Keys) { $parts += ('"' + $k + '": ' + $sec[$k]) }
  $json = '{"abstract": ' + $abs + ', "main_text": ' + $main + ', "sections": {' + ($parts -join ', ') + '}, "pages": ' + $pages + '}'
  Set-Content -Path $Out -Value $json -Encoding ascii
} finally { $word.Quit() }
