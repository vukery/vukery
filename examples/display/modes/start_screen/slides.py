"""The start screen's slides. Positions and sizes are fractions of the display."""

from vukery.media.slides import Slide, Text

SLIDES = {
    "start_screen": Slide(
        Text("vukery", y=0.6, size=0.2, color="ffcc00"),
        Text("PRESS START", y=0.3, size=0.08),
    ),
}
