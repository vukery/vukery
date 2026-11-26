"""During a game: the score on the main display, player and ball on the apron."""

from vukery.media.slides import Slide, Text

SLIDES = {
    "score": Slide(Text("{player.score:,}", y=0.5, size=0.3)),
    "ball_info": Slide(
        Text("PLAYER {player.number}", y=0.65, size=0.2),
        Text("BALL {player.ball}", y=0.3, size=0.2, color="ffcc00"),
        background="202060",   # six hex digits, like every color in vukery
    ),
}
