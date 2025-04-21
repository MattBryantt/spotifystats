from enum import Enum

class Mode(Enum):
    TIME = "time"
    PLAYS = "plays"

ALBUMMODE = Mode.TIME
TRACKMODE = Mode.PLAYS
ARTISTMODE = Mode.TIME

RESULTS = 100

# Songs that have the same name across different albums and are in fact different songs.
# Duplicates can be manually updated in the config file.
DUPLICATES = ["The 1975"]
IGNORE = ["Miracle Tones", "Timo Krantz"]