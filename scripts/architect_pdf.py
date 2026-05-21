import os
import sys
import markdown
from weasyprint import HTML

def generate_pdf():
    # 1. Path Resolution
    script_dir = os.path.dirname(os.path.abspath(__file__))
    mdx_path = os.path.normpath(os.path.join(script_dir, "..", "output", "changelog.mdx"))
    pdf_path = os.path.normpath(os.path.join(script_dir, "..", "output", "changelog.pdf"))

    print("[architect_pdf] Starting PDF generation...")

    # 2. Error Handling (Non-blocking)
    if not os.path.exists(mdx_path):
        print(f"[architect_pdf] WARNING: Input file not found at {mdx_path}")
        print("[architect_pdf] Skipping PDF generation. Exiting cleanly.")
        sys.exit(0)

    # 3. Read MDX
    with open(mdx_path, "r", encoding="utf-8") as f:
        mdx_content = f.read()

    print("[architect_pdf] Converting Markdown to HTML...")
    html_content = markdown.markdown(mdx_content, extensions=['fenced_code', 'tables'])

    # 4. Inject Corporate CSS & Map Mintlify Tags to HTML styling
    styled_html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Helvetica Neue', Arial, sans-serif; color: #1f2937; line-height: 1.6; margin: 40px; }}
            h1 {{ color: #111827; border-bottom: 2px solid #e5e7eb; padding-bottom: 10px; }}
            h2 {{ color: #374151; margin-top: 30px; }}
            code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 0.9em; }}
            .danger {{ background: #fef2f2; border-left: 5px solid #ef4444; padding: 15px; margin: 20px 0; border-radius: 0 8px 8px 0; }}
            .warning {{ background: #fffbeb; border-left: 5px solid #f59e0b; padding: 15px; margin: 20px 0; border-radius: 0 8px 8px 0; }}
            .info {{ background: #eff6ff; border-left: 5px solid #3b82f6; padding: 15px; margin: 20px 0; border-radius: 0 8px 8px 0; }}
            .check {{ background: #f0fdf4; border-left: 5px solid #22c55e; padding: 15px; margin: 20px 0; border-radius: 0 8px 8px 0; }}
        </style>
    </head>
    <body>
        {html_content.replace('<Danger>', '<div class="danger">').replace('</Danger>', '</div>')
                     .replace('<Warning>', '<div class="warning">').replace('</Warning>', '</div>')
                     .replace('<Info>', '<div class="info">').replace('</Info>', '</div>')
                     .replace('<Check>', '<div class="check">').replace('</Check>', '</div>')}
    </body>
    </html>
    """

    # 5. Render PDF
    print("[architect_pdf] Rendering PDF via WeasyPrint...")
    try:
        HTML(string=styled_html).write_pdf(pdf_path)
        print(f"[architect_pdf] SUCCESS: Corporate PDF saved to {pdf_path}")
    except Exception as e:
        print(f"[architect_pdf] ERROR generating PDF: {e}")
        sys.exit(1)

if __name__ == "__main__":
    generate_pdf()