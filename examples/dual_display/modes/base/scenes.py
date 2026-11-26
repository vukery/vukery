"""During a game: the score on the main display, player and ball on the apron."""

from vukery.media.scenes import Scene, Text, scene


@scene
def score():
    return Scene(Text("{player.score:,}", y=0.5, size=0.3))


@scene
def ball_info():
    return Scene(
        Text("PLAYER {player.number}", y=0.65, size=0.2),
        Text("BALL {player.ball}", y=0.3, size=0.2, color="ffcc00"),
        background="202060",   # six hex digits, like every color in vukery
    )
