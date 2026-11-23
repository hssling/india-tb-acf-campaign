# New for the IJTB set (tools/build_submission.py): export one .docx to PDF through Microsoft Word.
# Usage: powershell -NoProfile -File docx_to_pdf.ps1 <docx> <pdf>
# Opens its own Word instance (read-only, hidden) and quits only that instance.
param([string]$Docx, [string]$Pdf)
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
  $d = $word.Documents.Open($Docx, $false, $true)
  $d.ExportAsFixedFormat($Pdf, 17)
  $d.Close(0)
} finally { $word.Quit() }
