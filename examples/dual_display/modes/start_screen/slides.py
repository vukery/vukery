"""Between games: a title on the main display, "press start" on the apron."""

from vukery.media.slides import Slide, Text

SLIDES = {
    "title": Slide(Text("vukery", y=0.5, size=0.25, color="ffcc00")),
    "press_start": Slide(Text("PRESS START", y=0.5, size=0.2), background="202060"),
}
