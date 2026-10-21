"""Build the submission site: docs/*.md + README.md -> _site/index.html.

Run by .github/workflows/pages.yml. Locally: pip install markdown && python docs/build.py
"""

import re
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_site"
REPO = "https://github.com/dannygrowthmarketing/ticmint-internet-listener"

SECTIONS = [
    ("part-a", "A · The build", ROOT / "README.md"),
    ("part-b", "B · Other tracks", ROOT / "docs/part-b-other-tracks.md"),
    ("part-c", "C · Organic visibility", ROOT / "docs/part-c-organic-visibility.md"),
    ("part-d", "D · Growth strategy", ROOT / "docs/part-d-growth-strategy.md"),
    ("part-e", "E · Proof of work", ROOT / "docs/part-e-proof-of-work.md"),
    ("ai-note", "AI-use note", ROOT / "docs/ai-use-note.md"),
]


def fix_links(md: str, src: Path) -> str:
    """Relative repo links -> absolute GitHub links, so they work on the site too."""
    def repl(m):
        text, href = m.group(1), m.group(2)
        if href.startswith(("http", "#", "mailto:")):
            return m.group(0)
        target = (src.parent / href).resolve()
        try:
            rel = target.relative_to(ROOT)
        except ValueError:
            return m.group(0)
        kind = "tree" if target.is_dir() else "blob"
        return f"[{text}]({REPO}/{kind}/main/{rel.as_posix()})"
    return re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", repl, md)


def render(path: Path) -> str:
    md = fix_links(path.read_text(encoding="utf-8"), path)
    return markdown.markdown(md, extensions=["tables", "fenced_code", "sane_lists", "attr_list"])


def main():
    OUT.mkdir(exist_ok=True)
    tpl = (ROOT / "docs/template.html").read_text(encoding="utf-8")
    nav = "\n".join(f'<a href="#{sid}">{label}</a>' for sid, label, _ in SECTIONS)
    body = "\n".join(f'<section id="{sid}" class="doc">{render(p)}</section>' for sid, _, p in SECTIONS)
    (OUT / "index.html").write_text(tpl.replace("{{NAV}}", nav).replace("{{SECTIONS}}", body), encoding="utf-8")
    print(f"built {OUT / 'index.html'}")


if __name__ == "__main__":
    main()
