# Convert Word-HTML letters to .docx (and optional .pdf) with Microsoft Word.
# -Jobs: JSON file  [{ "in": "...htm", "docx": "...docx" (optional), "pdf": "...pdf" (optional),
#                      "tighten": true (optional: pull a lone last-line word back up, see Tighten) }]
# Prints one line per job:  OK<TAB>in   or   ERR<TAB>in<TAB>message   (plus WARN<TAB>in<TAB>message if Tighten failed)
param([Parameter(Mandatory = $true)][string]$Jobs)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$list = Get-Content -LiteralPath $Jobs -Raw -Encoding UTF8 | ConvertFrom-Json

# Range.Information, retried while Word is busy laying out the page (RPC_E_CALL_REJECTED)
function Info($r, $what) {
    for ($k = 0; ; $k++) {
        try { return $r.Information($what) }
        catch {
            $e = $_.Exception; if ($e.InnerException) { $e = $e.InnerException }
            if ($k -ge 40 -or $e.HResult -ne -2147418111) { throw }
            Start-Sleep -Milliseconds 50
        }
    }
}

# (page, line) of the character at $pos - line numbers grow along a paragraph
function LineKey($doc, $pos) {
    $r = $doc.Range($pos, $pos + 1)
    return [int](Info $r 3) * 1000 + [int](Info $r 10)   # wdActiveEndPageNumber, wdFirstCharacterLineNumber
}

# first position in [lo, hi] that is on the same line as hi: Home key of the selection when there is one
# (3 calls, cheaper than one Information call), else a binary search on LineKey
function LineStart($doc, $sel, $lo, $hi) {
    if ($sel) {
        $sel.SetRange($hi, $hi)
        [void]$sel.HomeKey(5)                                       # wdLine
        return [math]::Max($lo, $sel.Start)
    }
    $key = LineKey $doc $hi
    while ($lo -lt $hi) {
        $mid = [int][math]::Floor(($lo + $hi) / 2)
        if ((LineKey $doc $mid) -eq $key) { $hi = $mid } else { $lo = $mid + 1 }
    }
    return $lo
}

# A paragraph whose last line holds a single word (no space - a Thai compound counts as one word, although
# Word splits it): condense the line above it by 0.1 pt steps, up to 0.6 pt below its current
# spacing, until the word fits there; undo if it still does not fit. Text between manual line breaks counts
# as its own paragraph (the Thai closing block is one Word paragraph). Skips tables and centred paragraphs.
# Word's own line layout is used, so Thai word breaks are exact. Each Information call costs ~15 ms, so text
# shorter than $MinLen characters (cannot fill a 16 pt line) is skipped without asking Word, and so is a word
# wider than condensing can free.
$MinLen = 40
function Tighten($doc) {
    $doc.Repaginate()
    $sel = $null
    try { $sel = $doc.ActiveWindow.Selection } catch {}
    $tables = @(foreach ($t in @($doc.Tables)) { , @($t.Range.Start, $t.Range.End) })
    foreach ($p in @($doc.Paragraphs)) {
        $r = $p.Range
        $r0 = $r.Start; $r1 = $r.End                                      # COM calls are slow: read once
        if ($r1 - $r0 -lt $MinLen) { continue }
        $inTable = $false
        foreach ($t in $tables) { if ($r0 -ge $t[0] -and $r0 -lt $t[1]) { $inTable = $true } }
        if ($inTable -or $p.Alignment -eq 1) { continue }                 # centred
        $text = $r.Text
        $segStart = 0                                                     # (string methods: PowerShell loops are slow)
        while ($segStart -lt $text.Length) {
            $i = $text.IndexOf([char]11, $segStart)
            if ($i -lt 0) { $i = $text.Length - 1 }                       # paragraph mark
            $seg = $text.Substring($segStart, $i - $segStart).TrimEnd()
            $first = $r0 + $segStart; $last = $first + $seg.Length - 1   # one visual paragraph: [first, last]
            $segStart = $i + 1
            if ($seg.Length -lt $MinLen) { continue }
            if ($doc.Range($r0 + $i, $r0 + $i + 1).Text -ne [string]$text[$i]) { break }   # positions do not match text
            $m = [regex]::Match($seg, '\s\S*$')                           # last space before the final word
            $w = if ($m.Success) { $first + $m.Index } else { $first }
            $ls = LineStart $doc $sel $first $last
            if ($ls -le $first -or ($m.Success -and $w -ge $ls)) { continue }   # one line / last line holds more than one word
            $ps = LineStart $doc $sel $first ($ls - 1)
            if ($ps -ge $ls) { continue }
            # the word must fit in what 0.6 pt per character can free (skips hopeless cases: ~6 relayouts each)
            $need = [double](Info ($doc.Range($last, $last + 1)) 5) - [double](Info ($doc.Range($ls, $ls + 1)) 5)   # wdHorizontalPositionRelativeToPage
            if ($need -gt 0.6 * ($last + 1 - $ps)) { continue }
            $pkey = LineKey $doc $ps
            $span = $doc.Range($ps, $last + 1)
            $base = $span.Font.Spacing
            if ($base -gt 1000) { $base = 0 }                             # mixed spacing (wdUndefined)
            $tries = 0
            foreach ($s in 0.1, 0.2, 0.3, 0.4, 0.5, 0.6) {
                $span.Font.Spacing = $base - $s
                $tries++
                if ((LineKey $doc $last) -eq $pkey) { $tries = 0; break }
            }
            if ($tries) { [void]$doc.Undo($tries) }
        }
    }
}

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
            if ($job.tighten) {
                try { Tighten $doc } catch { Write-Output ("WARN`t" + $job.in + "`ttighten: " + ($_.Exception.Message -replace '\s+', ' ')) }
            }
            if ($job.docx) { $doc.SaveAs2($job.docx, 16) }      # wdFormatXMLDocument
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
