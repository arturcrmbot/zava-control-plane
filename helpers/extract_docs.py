import win32com.client
import os, sys

sys.stdout.reconfigure(encoding='utf-8')

base = r'c:\dev\ghcp sdk stuff\RFP\MSFT_Response'
files = [
    'Microsoft_WPP_Agent_Framework_Response.docx',
    'WPP_RFP_Clarification_Questions_copilot generated.docx'
]

word = win32com.client.Dispatch('Word.Application')
word.Visible = False

for f in files:
    src = os.path.join(base, f)
    dst = os.path.join(base, f.replace('.docx', '.txt'))
    print(f"Opening {f}...")
    doc = word.Documents.Open(src)
    # SaveAs with format 2 = wdFormatText
    doc.SaveAs(dst, 2)
    doc.Close()
    print(f"Saved {dst} ({os.path.getsize(dst)} bytes)")

word.Quit()
print("Done")
