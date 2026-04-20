from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent


ROOT = Path(__file__).resolve().parents[1]
PRESENTATIONS_DIR = ROOT / "docs" / "presentations"
PAGE_WIDTH = 792
PAGE_HEIGHT = 612
MARGIN_X = 54
MARGIN_TOP = 52
MARGIN_BOTTOM = 40


@dataclass
class Theme:
    background: tuple[float, float, float]
    accent: tuple[float, float, float]
    title: tuple[float, float, float]
    subtitle: tuple[float, float, float]
    body: tuple[float, float, float]
    footer: tuple[float, float, float]
    name: str


@dataclass
class Slide:
    title: str
    subtitle: str | None
    bullets: list[str]
    paragraphs: list[str]


DEVELOPER_THEME = Theme(
    background=(0.96, 0.97, 0.99),
    accent=(0.07, 0.34, 0.77),
    title=(0.07, 0.14, 0.29),
    subtitle=(0.22, 0.34, 0.48),
    body=(0.10, 0.13, 0.17),
    footer=(0.40, 0.46, 0.54),
    name="Developer Deck",
)

EXECUTIVE_THEME = Theme(
    background=(0.99, 0.97, 0.94),
    accent=(0.80, 0.37, 0.08),
    title=(0.28, 0.16, 0.06),
    subtitle=(0.46, 0.30, 0.18),
    body=(0.16, 0.13, 0.11),
    footer=(0.52, 0.42, 0.32),
    name="Executive Deck",
)


def parse_slides(markdown_text: str) -> list[Slide]:
    slides: list[Slide] = []
    for raw_slide in markdown_text.split("\n---\n"):
        lines = [line.rstrip() for line in raw_slide.strip().splitlines() if line.strip()]
        if not lines:
            continue

        title = ""
        subtitle: str | None = None
        bullets: list[str] = []
        paragraphs: list[str] = []

        for line in lines:
            if line.startswith("# "):
                title = line[2:].strip()
            elif line.startswith("> "):
                subtitle = line[2:].strip()
            elif line.startswith("- "):
                bullets.append(line[2:].strip())
            else:
                paragraphs.append(line.strip())

        if not title:
            raise ValueError(f"Slide is missing a title:\n{raw_slide}")

        slides.append(Slide(title=title, subtitle=subtitle, bullets=bullets, paragraphs=paragraphs))
    return slides


def wrap_text(text: str, font_size: int, max_width: int) -> list[str]:
    if not text:
        return [""]

    max_chars = max(16, int(max_width / (font_size * 0.52)))
    words = text.split()
    lines: list[str] = []
    current: list[str] = []

    for word in words:
        candidate = " ".join([*current, word]).strip()
        if len(candidate) <= max_chars:
            current.append(word)
            continue
        if current:
            lines.append(" ".join(current))
        current = [word]

    if current:
        lines.append(" ".join(current))
    return lines or [text]


def pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def text_line(x: int, y: int, text: str, size: int, color: tuple[float, float, float]) -> str:
    r, g, b = color
    return dedent(
        f"""
        BT
        /F1 {size} Tf
        {r:.3f} {g:.3f} {b:.3f} rg
        1 0 0 1 {x} {y} Tm
        ({pdf_escape(text)}) Tj
        ET
        """
    ).strip()


def build_slide_stream(slide: Slide, theme: Theme, page_number: int, total_pages: int) -> bytes:
    body_width = PAGE_WIDTH - (MARGIN_X * 2)
    lines: list[str] = []
    bg_r, bg_g, bg_b = theme.background
    ac_r, ac_g, ac_b = theme.accent

    lines.append(f"{bg_r:.3f} {bg_g:.3f} {bg_b:.3f} rg")
    lines.append(f"0 0 {PAGE_WIDTH} {PAGE_HEIGHT} re f")
    lines.append(f"{ac_r:.3f} {ac_g:.3f} {ac_b:.3f} rg")
    lines.append(f"0 {PAGE_HEIGHT - 18} {PAGE_WIDTH} 18 re f")
    lines.append(f"{ac_r:.3f} {ac_g:.3f} {ac_b:.3f} rg")
    lines.append(f"{MARGIN_X} {PAGE_HEIGHT - 118} 6 56 re f")

    cursor_y = PAGE_HEIGHT - MARGIN_TOP - 16
    lines.append(text_line(MARGIN_X + 20, cursor_y, slide.title, 28, theme.title))
    cursor_y -= 34

    if slide.subtitle:
        for part in wrap_text(slide.subtitle, 15, body_width - 20):
            lines.append(text_line(MARGIN_X + 20, cursor_y, part, 15, theme.subtitle))
            cursor_y -= 20
        cursor_y -= 8

    for paragraph in slide.paragraphs:
        for part in wrap_text(paragraph, 14, body_width):
            lines.append(text_line(MARGIN_X + 20, cursor_y, part, 14, theme.body))
            cursor_y -= 18
        cursor_y -= 8

    bullet_x = MARGIN_X + 36
    followup_x = MARGIN_X + 54
    for bullet in slide.bullets:
        wrapped = wrap_text(bullet, 16, body_width - 54)
        if not wrapped:
            continue
        lines.append(text_line(bullet_x, cursor_y, "- " + wrapped[0], 16, theme.body))
        cursor_y -= 22
        for continuation in wrapped[1:]:
            lines.append(text_line(followup_x, cursor_y, continuation, 16, theme.body))
            cursor_y -= 20
        cursor_y -= 8

    footer = f"Agent Memory Runtime | {theme.name} | {page_number}/{total_pages}"
    lines.append(text_line(MARGIN_X, MARGIN_BOTTOM - 2, footer, 10, theme.footer))

    return ("\n".join(lines) + "\n").encode("latin-1", errors="replace")


class SimplePDF:
    def __init__(self) -> None:
        self.objects: list[bytes] = []

    def add_object(self, content: bytes | str) -> int:
        data = content.encode("latin-1") if isinstance(content, str) else content
        self.objects.append(data)
        return len(self.objects)

    def add_stream(self, stream_data: bytes, extra_dict: str = "") -> int:
        header = f"<< /Length {len(stream_data)}"
        if extra_dict:
            header += f" {extra_dict}"
        header += " >>\nstream\n"
        footer = "\nendstream"
        return self.add_object(header.encode("latin-1") + stream_data + footer.encode("latin-1"))

    def write(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]

        for index, obj in enumerate(self.objects, start=1):
            offsets.append(len(result))
            result.extend(f"{index} 0 obj\n".encode("latin-1"))
            result.extend(obj)
            result.extend(b"\nendobj\n")

        xref_start = len(result)
        result.extend(f"xref\n0 {len(self.objects) + 1}\n".encode("latin-1"))
        result.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            result.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))

        catalog_id = len(self.objects)
        result.extend(
            f"trailer\n<< /Size {len(self.objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode(
                "latin-1"
            )
        )
        output_path.write_bytes(result)


def render_pdf(slides: list[Slide], theme: Theme, output_path: Path) -> None:
    pdf = SimplePDF()
    font_id = pdf.add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    content_ids: list[int] = []

    total_pages = len(slides)
    for index, slide in enumerate(slides, start=1):
        stream_id = pdf.add_stream(build_slide_stream(slide, theme, index, total_pages))
        content_ids.append(stream_id)

    pages_kids_refs = []
    page_object_ids: list[int] = []
    pages_id = len(pdf.objects) + len(slides) + 1

    # Create page objects after knowing the future pages object id.
    for content_id in content_ids:
        page_obj = (
            f"<< /Type /Page /Parent {pages_id} 0 R "
            f"/MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> "
            f"/Contents {content_id} 0 R >>"
        )
        page_object_ids.append(pdf.add_object(page_obj))
        pages_kids_refs.append(f"{page_object_ids[-1]} 0 R")

    pdf.add_object(f"<< /Type /Pages /Kids [{' '.join(pages_kids_refs)}] /Count {len(page_object_ids)} >>")
    pdf.add_object(f"<< /Type /Catalog /Pages {pages_id} 0 R >>")
    pdf.write(output_path)


def build_deck(source_path: Path, output_path: Path, theme: Theme) -> None:
    slides = parse_slides(source_path.read_text(encoding="utf-8"))
    render_pdf(slides, theme, output_path)


def build_all() -> list[Path]:
    outputs = [
        (
            PRESENTATIONS_DIR / "agent-memory-runtime-for-builders.md",
            PRESENTATIONS_DIR / "agent-memory-runtime-for-builders.pdf",
            DEVELOPER_THEME,
        ),
        (
            PRESENTATIONS_DIR / "agent-memory-runtime-for-executives.md",
            PRESENTATIONS_DIR / "agent-memory-runtime-for-executives.pdf",
            EXECUTIVE_THEME,
        ),
    ]
    generated: list[Path] = []
    for source_path, output_path, theme in outputs:
        build_deck(source_path, output_path, theme)
        generated.append(output_path)
    return generated


def main() -> None:
    parser = argparse.ArgumentParser(description="Build project presentation PDFs.")
    parser.add_argument("--source", type=Path, help="Optional source markdown file.")
    parser.add_argument("--output", type=Path, help="Optional output PDF file.")
    parser.add_argument(
        "--theme",
        choices=("developer", "executive"),
        help="Theme to use when building a single deck.",
    )
    args = parser.parse_args()

    if args.source or args.output or args.theme:
        if not (args.source and args.output and args.theme):
            raise SystemExit("--source, --output, and --theme must be provided together.")
        theme = DEVELOPER_THEME if args.theme == "developer" else EXECUTIVE_THEME
        build_deck(args.source, args.output, theme)
        print(args.output)
        return

    for output in build_all():
        print(output)


if __name__ == "__main__":
    main()
