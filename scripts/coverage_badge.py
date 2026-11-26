"""Draw the README's coverage badge from coverage.py's JSON report.

    uv run pytest --cov --cov-report=json:coverage.json
    python scripts/coverage_badge.py coverage.json coverage.svg

CI (.github/workflows/specs.yml) runs this on every push to main and puts
coverage.svg on the `badges` branch, where the README shows it from. Standard
library only, so it runs anywhere.
"""

import json
import sys
from pathlib import Path

TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="20" role="img" aria-label="coverage: {text}">
<title>coverage: {text}</title>
<linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient>
<clipPath id="r"><rect width="{width}" height="20" rx="3" fill="#fff"/></clipPath>
<g clip-path="url(#r)"><rect width="61" height="20" fill="#555"/><rect x="61" width="{value_width}" height="20" fill="{color}"/><rect width="{width}" height="20" fill="url(#s)"/></g>
<g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
<text x="30.5" y="15" fill="#010101" fill-opacity=".3">coverage</text><text x="30.5" y="14">coverage</text>
<text x="{value_x}" y="15" fill="#010101" fill-opacity=".3">{text}</text><text x="{value_x}" y="14">{text}</text>
</g></svg>
"""


def color(percent: float) -> str:
    """Red under 50%, then orange, yellow, yellow-green, green from 90%."""
    for floor, hex_color in ((90, "#4c1"), (80, "#97ca00"), (70, "#a4a61d"), (60, "#dfb317"), (50, "#fe7d37")):
        if percent >= floor:
            return hex_color
    return "#e05d44"


def badge(percent: float) -> str:
    text = f"{percent:.0f}%"
    value_width = 10 + 7 * len(text)
    return TEMPLATE.format(width=61 + value_width, value_width=value_width, value_x=61 + value_width / 2,
                           color=color(percent), text=text)


def main(argv: list[str]) -> int:
    report, out = (Path(a) for a in argv) if len(argv) == 2 else (Path("coverage.json"), Path("coverage.svg"))
    percent = json.loads(report.read_text())["totals"]["percent_covered"]
    out.write_text(badge(percent))
    print(f"coverage {percent:.1f}% -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
