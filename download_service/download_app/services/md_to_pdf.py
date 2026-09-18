import asyncio
import re
import textwrap
from pathlib import Path
from typing import Optional

import markdown
from jinja2 import Template
from playwright.async_api import async_playwright

_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "template.html"

MERMAID_BLOCK_PATTERN = re.compile(
    r"```mermaid\s+([\s\S]*?)```",
    re.IGNORECASE,
)


def _prepare_markdown(md_content: str) -> str:
    """Normalize indentation and convert mermaid fences to raw HTML blocks."""
    normalized = textwrap.dedent(md_content).strip()

    def _replace(match: re.Match) -> str:
        graph_definition = match.group(1).strip()
        return f'\n<div class="mermaid">\n{graph_definition}\n</div>\n'

    return MERMAID_BLOCK_PATTERN.sub(_replace, normalized)


async def md_to_pdf(
    md_content: str,
    output_path: Optional[str] = None,
    return_bytes: bool = False
) -> bytes:
    """
    Convert markdown with mermaid charts to PDF.
    
    Args:
        md_content: Markdown content string (may include mermaid code blocks)
        output_path: Optional path to save PDF file
        return_bytes: If True, return PDF as bytes instead of saving to file
    
    Returns:
        PDF bytes
    """
    html_content = markdown.markdown(
        _prepare_markdown(md_content),
        extensions=['fenced_code', 'tables', 'codehilite']
    )
    
    with open(_TEMPLATE_PATH, "r") as file:
        template = Template(file.read())
        html_document = template.render(content=html_content)
    if output_path:
        Path(output_path).with_suffix(".html").write_text(html_document)
        
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        await page.set_content(html_document)
        await page.wait_for_timeout(2000)
        
        pdf_bytes = await page.pdf(
            format='A4',
            print_background=True,
            margin={
                'top': '2mm',
                'right': '2mm',
                'bottom': '2mm',
                'left': '2mm'
            }
        )
        
        await browser.close()
        
        if output_path:
            Path(output_path).write_bytes(pdf_bytes)
        
        return pdf_bytes


def md_to_pdf_sync(md_content: str, output_path: Optional[str] = None) -> bytes:
    """
    Synchronous wrapper for md_to_pdf.
    
    Args:
        md_content: Markdown content string (may include mermaid code blocks)
        output_path: Optional path to save PDF file
    
    Returns:
        PDF bytes
    """
    return asyncio.run(md_to_pdf(md_content, output_path, return_bytes=True))
