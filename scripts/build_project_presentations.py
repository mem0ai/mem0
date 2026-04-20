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
CONTENT_WIDTH = PAGE_WIDTH - (MARGIN_X * 2)


@dataclass
class Theme:
    background: tuple[float, float, float]
    surface: tuple[float, float, float]
    accent: tuple[float, float, float]
    accent_soft: tuple[float, float, float]
    accent_dark: tuple[float, float, float]
    title: tuple[float, float, float]
    subtitle: tuple[float, float, float]
    body: tuple[float, float, float]
    muted: tuple[float, float, float]
    footer: tuple[float, float, float]
    name: str


@dataclass
class Slide:
    title: str
    subtitle: str | None
    bullets: list[str]
    paragraphs: list[str]


DEVELOPER_THEME = Theme(
    background=(0.95, 0.97, 0.99),
    surface=(1.0, 1.0, 1.0),
    accent=(0.06, 0.33, 0.78),
    accent_soft=(0.84, 0.90, 0.99),
    accent_dark=(0.05, 0.16, 0.35),
    title=(0.06, 0.12, 0.25),
    subtitle=(0.21, 0.35, 0.51),
    body=(0.10, 0.13, 0.17),
    muted=(0.50, 0.57, 0.65),
    footer=(0.38, 0.44, 0.53),
    name="Developer Deck",
)

EXECUTIVE_THEME = Theme(
    background=(0.99, 0.96, 0.93),
    surface=(1.0, 0.99, 0.98),
    accent=(0.82, 0.38, 0.09),
    accent_soft=(0.98, 0.89, 0.78),
    accent_dark=(0.36, 0.19, 0.07),
    title=(0.29, 0.15, 0.06),
    subtitle=(0.49, 0.30, 0.16),
    body=(0.16, 0.13, 0.11),
    muted=(0.56, 0.45, 0.35),
    footer=(0.53, 0.41, 0.30),
    name="Executive Deck",
)

SHORT_THEME = Theme(
    background=(0.94, 0.97, 0.95),
    surface=(1.0, 1.0, 1.0),
    accent=(0.08, 0.49, 0.33),
    accent_soft=(0.85, 0.95, 0.90),
    accent_dark=(0.08, 0.22, 0.16),
    title=(0.08, 0.18, 0.14),
    subtitle=(0.22, 0.39, 0.31),
    body=(0.11, 0.15, 0.13),
    muted=(0.43, 0.52, 0.47),
    footer=(0.37, 0.47, 0.42),
    name="Short Deck",
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


def fill_rect(x: int, y: int, width: int, height: int, color: tuple[float, float, float]) -> str:
    r, g, b = color
    return f"{r:.3f} {g:.3f} {b:.3f} rg\n{x} {y} {width} {height} re f"


def stroke_rect(x: int, y: int, width: int, height: int, color: tuple[float, float, float], line_width: float = 1.0) -> str:
    r, g, b = color
    return f"{line_width:.2f} w\n{r:.3f} {g:.3f} {b:.3f} RG\n{x} {y} {width} {height} re S"


def draw_pill(x: int, y: int, width: int, height: int, fill: tuple[float, float, float]) -> list[str]:
    return [fill_rect(x, y, width, height, fill)]


def build_title_slide_stream(slide: Slide, theme: Theme, page_number: int, total_pages: int) -> bytes:
    lines: list[str] = []
    lines.append(fill_rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, theme.background))
    lines.append(fill_rect(0, PAGE_HEIGHT - 22, PAGE_WIDTH, 22, theme.accent))
    lines.append(fill_rect(PAGE_WIDTH - 244, 0, 244, PAGE_HEIGHT, theme.accent_dark))
    lines.append(fill_rect(PAGE_WIDTH - 214, 84, 150, 110, theme.accent_soft))
    lines.append(fill_rect(PAGE_WIDTH - 176, 228, 112, 84, theme.surface))
    lines.append(fill_rect(PAGE_WIDTH - 220, 358, 164, 118, theme.accent))

    tag_width = 220
    tag_y = PAGE_HEIGHT - 104
    lines.extend(draw_pill(MARGIN_X, tag_y, tag_width, 26, theme.accent_soft))
    lines.append(text_line(MARGIN_X + 12, tag_y + 8, "Autonomous memory infrastructure for agents", 11, theme.accent_dark))

    title_y = PAGE_HEIGHT - 166
    for part in wrap_text(slide.title, 34, 380):
        lines.append(text_line(MARGIN_X, title_y, part, 34, theme.title))
        title_y -= 40

    subtitle_y = title_y - 6
    if slide.subtitle:
        for part in wrap_text(slide.subtitle, 17, 400):
            lines.append(text_line(MARGIN_X, subtitle_y, part, 17, theme.subtitle))
            subtitle_y -= 22

    paragraph_y = subtitle_y - 18
    for paragraph in slide.paragraphs:
        for part in wrap_text(paragraph, 15, 400):
            lines.append(text_line(MARGIN_X, paragraph_y, part, 15, theme.body))
            paragraph_y -= 20
        paragraph_y -= 8

    bullet_y = max(96, paragraph_y - 8)
    for bullet in slide.bullets[:4]:
        wrapped = wrap_text(bullet, 15, 372)
        lines.append(text_line(MARGIN_X + 18, bullet_y, "- " + wrapped[0], 15, theme.body))
        bullet_y -= 20
        for continuation in wrapped[1:]:
            lines.append(text_line(MARGIN_X + 36, bullet_y, continuation, 15, theme.body))
            bullet_y -= 18
        bullet_y -= 6

    footer = f"Agent Memory Runtime | {theme.name} | {page_number}/{total_pages}"
    lines.append(text_line(MARGIN_X, 26, footer, 10, theme.footer))
    return ("\n".join(lines) + "\n").encode("latin-1", errors="replace")


def build_content_slide_stream(slide: Slide, theme: Theme, page_number: int, total_pages: int) -> bytes:
    lines: list[str] = []
    lines.append(fill_rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, theme.background))
    lines.append(fill_rect(0, PAGE_HEIGHT - 18, PAGE_WIDTH, 18, theme.accent))
    lines.append(fill_rect(0, 0, 16, PAGE_HEIGHT, theme.accent_soft))
    lines.append(fill_rect(MARGIN_X - 4, 74, CONTENT_WIDTH + 8, 458, theme.surface))
    lines.append(stroke_rect(MARGIN_X - 4, 74, CONTENT_WIDTH + 8, 458, theme.accent_soft, 1.2))
    lines.append(fill_rect(PAGE_WIDTH - 164, PAGE_HEIGHT - 126, 110, 66, theme.accent_soft))
    lines.append(fill_rect(PAGE_WIDTH - 118, PAGE_HEIGHT - 232, 64, 38, theme.accent))

    subtitle_box_width = min(330, max(180, len((slide.subtitle or theme.name)) * 7))
    subtitle_box_y = PAGE_HEIGHT - 112
    lines.extend(draw_pill(MARGIN_X + 24, subtitle_box_y, subtitle_box_width, 24, theme.accent_soft))
    lines.append(
        text_line(MARGIN_X + 36, subtitle_box_y + 7, slide.subtitle or theme.name, 11, theme.accent_dark)
    )

    cursor_y = PAGE_HEIGHT - 160
    for part in wrap_text(slide.title, 28, CONTENT_WIDTH - 88):
        lines.append(text_line(MARGIN_X + 24, cursor_y, part, 28, theme.title))
        cursor_y -= 34

    cursor_y -= 8
    for paragraph in slide.paragraphs:
        for part in wrap_text(paragraph, 14, CONTENT_WIDTH - 72):
            lines.append(text_line(MARGIN_X + 24, cursor_y, part, 14, theme.body))
            cursor_y -= 18
        cursor_y -= 8

    bullet_x = MARGIN_X + 34
    followup_x = MARGIN_X + 54
    for bullet in slide.bullets:
        wrapped = wrap_text(bullet, 16, CONTENT_WIDTH - 88)
        if not wrapped:
            continue
        lines.append(text_line(bullet_x, cursor_y, "- " + wrapped[0], 16, theme.body))
        cursor_y -= 22
        for continuation in wrapped[1:]:
            lines.append(text_line(followup_x, cursor_y, continuation, 16, theme.body))
            cursor_y -= 20
        cursor_y -= 8

    footer = f"Agent Memory Runtime | {theme.name} | {page_number}/{total_pages}"
    lines.append(text_line(MARGIN_X, 26, footer, 10, theme.footer))
    return ("\n".join(lines) + "\n").encode("latin-1", errors="replace")


def build_slide_stream(slide: Slide, theme: Theme, page_number: int, total_pages: int) -> bytes:
    if page_number == 1:
        return build_title_slide_stream(slide, theme, page_number, total_pages)
    return build_content_slide_stream(slide, theme, page_number, total_pages)


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
        content_ids.append(pdf.add_stream(build_slide_stream(slide, theme, index, total_pages)))

    pages_kids_refs = []
    page_object_ids: list[int] = []
    pages_id = len(pdf.objects) + len(slides) + 1

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
        (
            PRESENTATIONS_DIR / "agent-memory-runtime-short-overview.md",
            PRESENTATIONS_DIR / "agent-memory-runtime-short-overview.pdf",
            SHORT_THEME,
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
        choices=("developer", "executive", "short"),
        help="Theme to use when building a single deck.",
    )
    args = parser.parse_args()

    if args.source or args.output or args.theme:
        if not (args.source and args.output and args.theme):
            raise SystemExit("--source, --output, and --theme must be provided together.")
        if args.theme == "developer":
            theme = DEVELOPER_THEME
        elif args.theme == "executive":
            theme = EXECUTIVE_THEME
        else:
            theme = SHORT_THEME
        build_deck(args.source, args.output, theme)
        print(args.output)
        return

    for output in build_all():
        print(output)


if __name__ == "__main__":
    main()
