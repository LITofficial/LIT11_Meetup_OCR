"""Create two public, fictitious PDF posters for the live demo.

Run once: python scripts/generate_sample_posters.py
The generated PDFs are committed so reportlab is not needed to run the demo.
"""

from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

OUTPUT = Path(__file__).resolve().parents[1] / "samples"
OUTPUT.mkdir(exist_ok=True)
W, H = A4

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
if (FONT_DIR / "DejaVuSans.ttf").exists():
    # Embed fonts so letters render cleanly in any PDF viewer.
    pdfmetrics.registerFont(TTFont("LITRegular", str(FONT_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("LITBold", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
    REGULAR_FONT, BOLD_FONT = "LITRegular", "LITBold"
else:
    REGULAR_FONT, BOLD_FONT = "Helvetica", "Helvetica-Bold"


def background(c: Canvas, dark: bool) -> None:
    c.setFillColor(HexColor("#10253A" if dark else "#F0FAFB"))
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(HexColor("#16A6A0" if dark else "#127E8D"))
    c.rect(0, H - 16, W, 16, fill=1, stroke=0)
    for i in range(5):
        c.setStrokeColor(HexColor("#1C6476" if dark else "#D5EEF0"))
        c.setLineWidth(2)
        c.circle(W + 20, H + 20, 80 + i * 40)


def write(c: Canvas, x: float, y: float, text: str, size: int, *, bold=False, dark=False):
    c.setFillColor(white if dark else HexColor("#10253A"))
    c.setFont(BOLD_FONT if bold else REGULAR_FONT, size)
    c.drawString(x, y, text)


def easy_poster() -> None:
    path = OUTPUT / "easy_event.pdf"
    c = Canvas(str(path), pagesize=A4)
    background(c, dark=False)
    write(c, 54, 700, "LIT TECH MEETUP", 34, bold=True)
    write(c, 54, 655, "BUILD SOMETHING REAL WITH AI", 16)
    write(c, 54, 564, "EVENT DATE", 13, bold=True)
    write(c, 54, 524, "2026-11-11  18:00 - 20:00", 24, bold=True)
    write(c, 54, 465, "PLACE", 13, bold=True)
    write(c, 54, 427, "KNU IT-5, Room B102", 21, bold=True)
    write(c, 54, 368, "ORGANIZED BY", 13, bold=True)
    write(c, 54, 331, "LIT Student Developer Club", 19)
    write(c, 54, 246, "REGISTER BY 2026-11-08", 18, bold=True)
    write(c, 54, 208, "https://example.org/lit-meetup", 14)
    c.showPage()
    c.save()


def tricky_poster() -> None:
    path = OUTPUT / "tricky_event.pdf"
    c = Canvas(str(path), pagesize=A4)
    background(c, dark=True)
    write(c, 48, 696, "APPLICATIONS CLOSE", 27, bold=True, dark=True)
    write(c, 48, 628, "NOV 09", 53, bold=True, dark=True)
    write(c, 48, 588, "Last day to submit your application!", 16, dark=True)
    c.setStrokeColor(HexColor("#16A6A0"))
    c.setLineWidth(3)
    c.line(48, 554, W - 48, 554)
    write(c, 48, 501, "YOU ARE INVITED", 15, bold=True, dark=True)
    write(c, 48, 451, "Discover AI: Hands-on Night", 27, bold=True, dark=True)
    write(c, 48, 392, "THE ACTUAL EVENT", 13, bold=True, dark=True)
    write(c, 48, 354, "NOV 13  |  18:30 - 20:00", 22, bold=True, dark=True)
    write(c, 48, 293, "WHERE", 13, bold=True, dark=True)
    write(c, 48, 255, "KNU IT-5 B102", 21, bold=True, dark=True)
    write(c, 48, 189, "Hosted by LIT  /  Details: https://example.org/lit", 12, dark=True)
    write(c, 48, 129, "Note: The EVENT YEAR is not printed on this poster.", 13, dark=True)
    c.showPage()
    c.save()


if __name__ == "__main__":
    easy_poster()
    tricky_poster()
    print(f"Created: {OUTPUT / 'easy_event.pdf'}")
    print(f"Created: {OUTPUT / 'tricky_event.pdf'}")

