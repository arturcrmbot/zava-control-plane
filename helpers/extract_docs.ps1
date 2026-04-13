$word = New-Object -ComObject Word.Application
$word.Visible = $false
$files = @(
    'Microsoft_WPP_Agent_Framework_Response.docx',
    'WPP_RFP_Clarification_Questions_copilot generated.docx'
)
$base = 'c:\dev\ghcp sdk stuff\RFP\MSFT_Response'
foreach ($f in $files) {
    $src = Join-Path $base $f
    $dst = Join-Path $base ($f.Replace('.docx','.txt'))
    $doc = $word.Documents.Open($src)
    $doc.SaveAs([ref]$dst, [ref]2)
    $doc.Close()
    Write-Host "Converted $f"
}
$word.Quit()
Write-Host "All done"
