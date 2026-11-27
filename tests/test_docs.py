"""The docs site's config (mkdocs.yml)."""

from pathlib import Path
from typing import Any

import yaml

from vukery.testing import expect

ROOT = Path(__file__).parents[1]
DOCS = ROOT / "docs"


class _IgnoreTags(yaml.SafeLoader):
    """mkdocs.yml has !!python/name tags (for mermaid); they don't matter here."""


_IgnoreTags.add_multi_constructor("tag:yaml.org,2002:python/", lambda *_: None)


def url(page: str) -> str:
    """Where mkdocs serves a page: modes.md and modes/index.md are both modes/."""
    path = page.removesuffix(".md")
    return "" if path == "index" else path.removesuffix("/index").removesuffix("index") + "/"


def redirects() -> dict[str, str]:
    config: Any = yaml.load((ROOT / "mkdocs.yml").read_text(), Loader=_IgnoreTags)  # a SafeLoader
    for plugin in config["plugins"]:
        if isinstance(plugin, dict) and "redirects" in plugin:
            return dict(plugin["redirects"]["redirect_maps"])
    return {}


def describe_the_docs_redirects():
    def it_never_redirects_from_a_page_that_exists():   # it would replace the page with a loop
        pages = {url(str(path.relative_to(DOCS))) for path in DOCS.rglob("*.md")}
        expect(sorted(old for old in redirects() if url(old) in pages)).to_equal([])

    def it_redirects_to_pages_that_exist():
        expect(sorted(new for new in redirects().values() if not (DOCS / new).is_file())).to_equal([])
