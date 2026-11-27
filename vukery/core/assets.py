"""Where a machine's asset files are: ``assets/{sounds,images,videos,fonts}/``, named by file name.

A machine's own file wins over vukery's: put ``assets/images/playfield.png``
in the machine folder and ``vuk me`` draws it instead of the built-in
playfield. Files are found by name, whatever their extension.
"""

from pathlib import Path

BUILT_IN = Path(__file__).parents[1] / "assets"
IMAGE_FILES = (".png", ".jpg", ".jpeg")
ARTWORK = ("playfield", "backbox")   # the dashboard's two pictures


def find(game_dir: Path, kind: str, name: str, extensions: tuple[str, ...]) -> Path | None:
    """The machine's ``assets/<kind>/<name>.<ext>``, if it has one."""
    folder = game_dir / "assets" / kind
    for extension in extensions:
        for candidate in (folder / f"{name}{extension}", folder / f"{name}{extension.upper()}"):
            if candidate.is_file():
                return candidate
    return None


def artwork(game_dir: Path, name: str) -> tuple[Path, bool]:
    """The picture ``vuk me`` draws for the playfield or backbox, and whether it's the machine's own."""
    own = find(game_dir, "images", name, IMAGE_FILES)
    return (own, True) if own is not None else (BUILT_IN / f"{name}.jpg", False)
