"""
Brief rendering.

A ``Brief`` is a titled list of sections; each section has a heading, an
optional one-line summary, and a list of bullet lines. The same structure
renders three ways:

  * ``to_terminal()`` — ANSI-coloured text for the CLI
  * ``to_markdown()`` — for journals, git, Telegram
  * ``to_html()``     — a standalone styled page for a browser / artifact

Keeping presentation out of the workflow means the ten-minute routine stays
readable and testable.
"""

from __future__ import annotations

import html as _html
from dataclasses import dataclass, field
from typing import List, Optional

# ANSI helpers ---------------------------------------------------------------
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_COLORS = {
    "green": "\033[32m",
    "red": "\033[31m",
    "yellow": "\033[33m",
    "cyan": "\033[36m",
    "magenta": "\033[35m",
    "blue": "\033[34m",
}


def _c(text: str, color: str, use_color: bool) -> str:
    if not use_color or color not in _COLORS:
        return text
    return f"{_COLORS[color]}{text}{_RESET}"


@dataclass
class Section:
    heading: str
    summary: str = ""
    lines: List[str] = field(default_factory=list)
    tone: str = "neutral"   # neutral | good | warn | alert — drives colour


@dataclass
class Brief:
    title: str
    subtitle: str = ""
    sections: List[Section] = field(default_factory=list)

    def add(self, section: Section) -> "Brief":
        self.sections.append(section)
        return self

    # -- terminal ------------------------------------------------------------

    def to_terminal(self, use_color: bool = True) -> str:
        tone_color = {"good": "green", "warn": "yellow", "alert": "red", "neutral": "cyan"}
        out: List[str] = []
        bar = "═" * max(len(self.title) + 4, 40)
        out.append(_c(bar, "blue", use_color))
        out.append(_c(f"  {self.title}", "blue", use_color) if not use_color
                   else f"  {_BOLD}{_COLORS['blue']}{self.title}{_RESET}")
        if self.subtitle:
            out.append(f"  {_c(self.subtitle, 'blue', use_color) if not use_color else _DIM + self.subtitle + _RESET}")
        out.append(_c(bar, "blue", use_color))
        out.append("")

        for i, sec in enumerate(self.sections, 1):
            color = tone_color.get(sec.tone, "cyan")
            head = f"{i}. {sec.heading}"
            out.append(_c(head, color, use_color) if not use_color
                       else f"{_BOLD}{_COLORS[color]}{head}{_RESET}")
            if sec.summary:
                out.append(f"   {sec.summary}")
            for line in sec.lines:
                out.append(f"     • {line}")
            out.append("")
        return "\n".join(out).rstrip() + "\n"

    # -- markdown ------------------------------------------------------------

    def to_markdown(self) -> str:
        icon = {"good": "🟢", "warn": "🟡", "alert": "🔴", "neutral": "🔵"}
        out = [f"# {self.title}"]
        if self.subtitle:
            out.append(f"_{self.subtitle}_")
        out.append("")
        for i, sec in enumerate(self.sections, 1):
            out.append(f"## {icon.get(sec.tone, '🔵')} {i}. {sec.heading}")
            if sec.summary:
                out.append(f"**{sec.summary}**")
            for line in sec.lines:
                out.append(f"- {line}")
            out.append("")
        return "\n".join(out).rstrip() + "\n"

    # -- html ----------------------------------------------------------------

    def to_html(self) -> str:
        tone_bg = {"good": "#0f3d2e", "warn": "#4a3c0f", "alert": "#4a1414", "neutral": "#12263a"}
        tone_bd = {"good": "#2ecc71", "warn": "#f1c40f", "alert": "#e74c3c", "neutral": "#3498db"}
        secs = []
        for i, sec in enumerate(self.sections, 1):
            lis = "".join(f"<li>{_html.escape(l)}</li>" for l in sec.lines)
            summary = f'<p class="summary">{_html.escape(sec.summary)}</p>' if sec.summary else ""
            secs.append(
                f'<section style="background:{tone_bg.get(sec.tone, "#12263a")};'
                f'border-left:4px solid {tone_bd.get(sec.tone, "#3498db")}">'
                f"<h2>{i}. {_html.escape(sec.heading)}</h2>{summary}"
                f"<ul>{lis}</ul></section>"
            )
        body = "".join(secs)
        sub = f'<p class="sub">{_html.escape(self.subtitle)}</p>' if self.subtitle else ""
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_html.escape(self.title)}</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ font-family: ui-monospace,SFMono-Regular,Menlo,monospace; background:#0a0e14;
          color:#e6edf3; margin:0; padding:2rem; line-height:1.5; }}
  .wrap {{ max-width:760px; margin:0 auto; }}
  h1 {{ margin:0 0 .25rem; font-size:1.6rem; }}
  .sub {{ color:#8b98a5; margin:0 0 1.5rem; }}
  section {{ border-radius:10px; padding:1rem 1.25rem; margin:0 0 1rem; }}
  h2 {{ margin:0 0 .5rem; font-size:1.05rem; }}
  .summary {{ font-weight:700; margin:.2rem 0 .6rem; }}
  ul {{ margin:.2rem 0 0; padding-left:1.2rem; }}
  li {{ margin:.15rem 0; }}
</style></head>
<body><div class="wrap"><h1>{_html.escape(self.title)}</h1>{sub}{body}
<p class="sub">Generated by Daily Driver — ten minutes a day, the rest is patience.</p>
</div></body></html>
"""
