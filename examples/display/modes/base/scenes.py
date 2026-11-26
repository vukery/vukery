"""The base mode's scene: the score, and whose turn and ball it is.

A scene is a function marked @scene that returns a Scene: a container of
actors (texts, or other scenes). The engine runs it once and sends the result
to the media controller as data.
"""

from vukery.media.scenes import Scene, Text, scene


@scene
def score():
    return Scene(
        # {player.score:,} is filled in live by the media controller, with Python
        # formatting: 12340 shows as 12,340. Any player variable works.
        Text("{player.score:,}", y=0.55, size=0.25).enters("left"),   # slides in when the ball starts
        Text("PLAYER {player.number}   BALL {player.ball}", y=0.15, size=0.07, color="aaaaaa"),
    )
