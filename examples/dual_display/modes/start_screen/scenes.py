"""Between games: a title on the main display, "press start" on the apron."""

from vukery.media.scenes import Scene, Text, scene


@scene
def title():
    return Scene(Text("vukery", y=0.5, size=0.25, color="ffcc00"))


@scene
def press_start():
    return Scene(Text("PRESS START", y=0.5, size=0.2), background="202060")
