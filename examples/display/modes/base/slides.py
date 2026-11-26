"""The base mode's slides, by name. The engine sends them to the media controller as data."""

from vukery.media.slides import Slide, Text

SLIDES = {
    "score": Slide(
        # {player.score:,} is filled in live by the media controller, with Python
        # formatting: 12340 shows as 12,340. Any player variable works.
        Text("{player.score:,}", y=0.55, size=0.25),
        Text("PLAYER {player.number}   BALL {player.ball}", y=0.15, size=0.07, color="aaaaaa"),
    ),
}
