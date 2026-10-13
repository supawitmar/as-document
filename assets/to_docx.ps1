# Convert Word-HTML letters to .docx (and optional .pdf) with Microsoft Word.
# -Jobs: JSON file  [{ "in": "...htm", "docx": "...docx", "pdf": "...pdf" (optional) }]
# Prints one line per job:  OK<TAB>in   or   ERR<TAB>in<TAB>message
param([Parameter(Mandatory = $true)][string]$Jobs)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$list = Get-Content -LiteralPath $Jobs -Raw -Encoding UTF8 | ConvertFrom-Json

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    foreach ($job in $list) {
        $doc = $null
        try {
            $doc = $word.Documents.Open($job.in, $false, $false, $false)
            # embed linked pictures (logo) into the document
            foreach ($shape in @($doc.InlineShapes)) {
                if ($shape.LinkFormat -ne $null) {
                    $shape.LinkFormat.SavePictureWithDocument = $true
                    $shape.LinkFormat.BreakLink()
                }
            }
            try { $doc.ActiveWindow.View.Type = 3 } catch {}   # Print Layout
            $doc.SaveAs2($job.docx, 16)                         # wdFormatXMLDocument
            if ($job.pdf) { $doc.SaveAs2($job.pdf, 17) }        # wdFormatPDF
            Write-Output ("OK`t" + $job.in)
        }
        catch {
            Write-Output ("ERR`t" + $job.in + "`t" + ($_.Exception.Message -replace '\s+', ' '))
        }
        finally {
            if ($doc -ne $null) { $doc.Close($false) }
        }
    }
}
finally {
    $word.Quit()
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)
}
