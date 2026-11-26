"""The start screen. Positions and sizes are fractions of the display (0.5, 0.5 is the middle)."""

from vukery.media.scenes import Scene, Text, scene


@scene
def start_screen():
    return Scene(
        Text("vukery", y=0.6, size=0.2, color="ffcc00"),
        Text("PRESS START", y=0.3, size=0.08).blinks(every=0.5),   # on half a second, off half a second
    )
