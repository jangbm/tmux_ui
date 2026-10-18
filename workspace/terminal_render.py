"""Render captured terminal text against the chat theme, not terminal backgrounds."""
import re
from rich.style import Style
from rich.text import Text, Span


def chat_terminal_text(screen):
    text=Text.from_ansi(screen)
    spans=[]
    for span in text.spans:
        style=span.style if isinstance(span.style,Style) else Style.parse(span.style)
        color=style.color
        if color is not None and color.is_default: color=None
        # ANSI default backgrounds and reverse video can become white rectangles
        # under Textual. Keep text emphasis, including dim suggestion text.
        cleaned=Style(color=color,bold=style.bold,dim=style.dim,italic=style.italic,
                      underline=style.underline,strike=style.strike,reverse=False,
                      conceal=style.conceal,link=style.link)
        spans.append(Span(span.start,span.end,cleaned))
    text.spans=spans
    # Native prompt dividers have the source pane's width; wrapping them in a
    # narrower chat panel creates multiple empty rows. Table borders stay intact.
    lines=[]
    for line in text.split('\n',allow_blank=True):
        if re.fullmatch(r'\s*[─━═]{6,}\s*',line.plain): continue
        titled=re.fullmatch(r'\s*[─━═]{3,}\s*(.*?)\s*[─━═]+\s*',line.plain)
        if titled:
            start,end=titled.span(1)
            line=line[start:end]
        lines.append(line)
    return Text('\n').join(lines)
