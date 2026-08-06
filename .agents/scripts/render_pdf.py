import fitz
import os

pdf_path = "attached_assets/Project_1-_Industrial_PPE_and_Work-at-Height_Safety_Monitoring_1786011403305.pdf"
doc = fitz.open(pdf_path)
print(f"Pages: {doc.page_count}")
print(f"Metadata: {doc.metadata}")

os.makedirs(".agents/outputs/pdf_pages", exist_ok=True)

for i, page in enumerate(doc):
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    out = f".agents/outputs/pdf_pages/page_{i+1:02d}.png"
    pix.save(out)
    print(f"Saved page {i+1}: {page.rect}")

# Also extract full text
for i, page in enumerate(doc):
    text = page.get_text()
    print(f"\n--- PAGE {i+1} ---\n{text}")
