"""Between games: a title on the main display, "press start" on the apron."""

from vukery.media.scenes import Scene, Text, scene


@scene
def title():
    # From where it's placed (y=0.45) up to y=0.55 and back again, forever
    return Scene(Text("vukery", y=0.45, size=0.25, color="ffcc00").moves(y=0.55, seconds=2, repeat=True, back=True))


@scene
def press_start():
    return Scene(Text("PRESS START", y=0.5, size=0.2).blinks(every=0.4, fade=True), background="202060")  # fades out and in
