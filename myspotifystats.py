import os
import json
import argparse
import re
import difflib
import spotipy
import readline
import atexit
import shutil
from itertools import chain
from spotipy.oauth2 import SpotifyClientCredentials
from pathlib import Path
from datetime import datetime, timedelta
from dateutil import parser
from dataclasses import dataclass
from enum import Enum, auto
from dotenv import load_dotenv

@dataclass
class ProcessedData:
    song_plays: dict
    artist_plays: dict
    album_plays: dict
    skips: dict
    total_time: int

class Mode(Enum):
    TIME = auto()
    PLAYS = auto()

class Cmd(Enum):
    TRACK = ("track", Mode.PLAYS)
    ALBUM = ("album", Mode.TIME)
    ARTIST = ("artist", Mode.TIME)
    SKIP = ("skip", Mode.PLAYS)
    SUMMARY = ("summary", None)
    FILTER = ("filter", None)
    RESULT = ("result", None)
    EXIT = ("exit", None)
    HELP = ("help", None)

    @property
    def text(self):
        return self.value[0]
    
    @property
    def mode(self):
        return self.value[1]


# Songs that have the same name across different albums and are in fact different songs.
# Duplicates can be manually updated in the config file.
DUPLICATES = ["The 1975"] # TODO: Update with spotify API?
# TODO: Add songs that have different names / URIs but are in fact the same song! (eg. popular)
IGNORE = ["Miracle Tones", "Timo Krantz"]
RESULTS = 10
ALBUMLIMIT = 3

STARTFILTER = datetime.min
ENDFILTER = datetime.max

def main(args):
    data = parse_data()
    pd = process_data(args, data)
    
    # Setup command history
    history_file = os.path.expanduser("~/.history_file")
    try:
        readline.read_history_file(history_file)
    except FileNotFoundError:
        pass
    atexit.register(readline.write_history_file, history_file)

    # Process commands
    try:
        while True:
            msg = input("What would you like to do? ")
            msg = msg.split(" ", maxsplit=1)
            cmd = msg[0]
            match cmd:
                case Cmd.RESULT.text:
                    global RESULTS
                    if len(msg) <= 1:
                        print("No number provded. Please provide a number to set result limit.")
                        continue
                    RESULTS = int(msg[1])
                case Cmd.FILTER.text:
                    global STARTFILTER, ENDFILTER
                    if len(msg) <= 1:
                        print("No dates proved. Please provide: filter STARTDATE to ENDDATE")
                        continue
                    filters = msg[1].split(" to ")
                    startfilter = filters[0]
                    try:
                        startfilter = parser.parse(startfilter)
                        if len(filters) > 1:
                            endfilter = filters[1]
                            endfilter = parser.parse(endfilter)
                    except parser.ParserError:
                        print("Invalid date. Please provide a correct date format.")
                        continue
                    STARTFILTER = startfilter
                    print("Added start date:", STARTFILTER.strftime("%d-%m-%Y"))
                    if len(filters) > 1:
                        if endfilter < startfilter:
                            print("Invalid filters. Start date must be before end date.")
                            continue
                        ENDFILTER = endfilter
                        print("Added end date:", ENDFILTER.strftime("%d-%m-%Y"))
                case Cmd.SUMMARY.text:
                    print_summary(pd)
                case Cmd.ARTIST.text:
                    if len(msg) < 2:
                        print_object(Cmd.ARTIST, pd.artist_plays)
                        continue
                    artist = msg[1]
                    match_list = difflib.get_close_matches(artist, (key.lower() for key in pd.artist_plays.keys()), n=1, cutoff=0.5)
                    if not match_list:
                        print("No artist found.")
                        continue
                    match_list = [key for key in pd.artist_plays if key.lower() in match_list]
                    print_artist(pd.artist_plays, pd.song_plays, match_list[0])
                case Cmd.TRACK.text:
                    print_object(Cmd.TRACK, pd.song_plays)
                case Cmd.ALBUM.text:
                    print_object(Cmd.ALBUM, pd.album_plays)
                case Cmd.SKIP.text:
                    print_object(Cmd.SKIP, pd.skips)
                case Cmd.EXIT.text:
                    print("Exiting program...")
                    break
                case Cmd.HELP.text:
                    print("Commands:")
                    print("summary - Show a summary of your data")
                    print("artist - Show data for all artists")
                    print("artist 'artist_name' - Show data for a specific artist")
                    print("track - Show your top tracks")
                    print("album - Show your top albums")
                    print("skip - Show your most skipped songs")
                    print("filter 'startdate' to 'enddate' - Sets filters for results")
                    print("help - Shows this list of commands")
                    print("exit - Exit the program")
                case _:
                    print("Unknown command. Type 'help' for a list of commands.") 
                    continue
            print("=" * shutil.get_terminal_size().columns) # TODO: Not working for artist (general)
    except KeyboardInterrupt:
        print("\nExiting program...")

def print_summary(pd):
    print("Summary:")
    print(f"Total songs played: {sum(len(song) for song in pd.song_plays.values())}")
    print(f"Unique songs played: {len(pd.song_plays.keys())}")
    print(f"Unique artists played: {len(pd.artist_plays.keys())}") # TODO: How hard would this be using just song plays? 
    print(f"Total time: {pd.total_time // 3600000} hours")

def print_artist(artist_plays, song_plays, artist):
    # TODO: Move to print_object
    plays = artist_plays[artist]
    first_play = min(plays, key=lambda play: datetime.strptime(play["ts"], "%Y-%m-%dT%H:%M:%SZ")) 
    first_play_track = first_play["master_metadata_track_name"]
    first_play_date = datetime.strptime(first_play["ts"], "%Y-%m-%dT%H:%M:%SZ").strftime("%-d %B, %Y")
    artist_song_plays = {song: play for song, play in song_plays.items() if song[1] == artist}

    print(f"Summary for {artist}:")
    print(f"Total listens: {len(plays)}")
    print(f"First played: {first_play_track} on: {first_play_date}")
    print_object(Cmd.TRACK, artist_song_plays)

def print_object(cmd, object_plays):
    # Filter object plays and remove keys with no valid filtered results
    object_plays = {
        obj: filtered
        for obj, plays in object_plays.items()
        if (filtered := [play for play in plays if STARTFILTER <= date(play) <= ENDFILTER])
    }

    # Filter albums and remove those with less than ALBUMLIMIT number of unique songs
    if cmd == Cmd.ALBUM:
        object_plays = {
            obj: plays
            for obj, plays in object_plays.items()
            if len({play["master_metadata_track_name"] for play in plays}) >= ALBUMLIMIT
        }

    # Sort top objects based on current mode
    if cmd.mode == Mode.PLAYS:
        top_objects = sorted(object_plays.items(), key=lambda item: len(item[1]), reverse=True)
    elif cmd.mode == Mode.TIME:
        top_objects = sorted(object_plays.items(), key=lambda item: sum(play["ms_played"] for play in item[1]), reverse=True)
    
    # Get all plays and first play
    all_plays = list(chain.from_iterable(object_plays.values()))
    first_play = min(all_plays, key=lambda play: datetime.strptime(play["ts"], "%Y-%m-%dT%H:%M:%SZ")) 
    first_play_track = first_play["master_metadata_track_name"]
    first_play_artist = first_play["master_metadata_album_artist_name"]
    first_play_date = datetime.strptime(first_play["ts"], "%Y-%m-%dT%H:%M:%SZ").strftime("%-d %B, %Y")
    # artist_song_plays = {song: play for song, play in object_plays.items() if song[1] == filter}

    # TODO: Create get_object() helper function that gets artist / album / track name based on current cmd?
    if cmd == Cmd.TRACK:
        print(f"First played {first_play_track} by {first_play_artist} on {first_play_date}")

    print(f"Total listens: {sum(len(plays) for plays in object_plays.values())} track(s)") 
    print(f"Total unique listens: {len(object_plays.keys())} {cmd.text}(s)") # TODO: Length is incorrect
    print(f"Top {cmd.text}(s):")
    for i in range(min(RESULTS, len(top_objects))):
        object = top_objects[i][0]
        plays = top_objects[i][1]
        first_play = min(top_objects[i][1], key=lambda play: date(play))
        first_play_track = first_play["master_metadata_track_name"]
        first_play_date = date(first_play).strftime("%-d %B, %Y")

        # TODO: Remove first play if STARTFILTER is adjusted?
        play_time = sum(play["ms_played"] for play in top_objects[i][1])
        play_hours = play_time // 3600000
        play_mins = (play_time // 60000) % 60

        # Build result string
        if cmd == Cmd.TRACK or cmd == Cmd.SKIP:
            result = f"{i+1}. {object[0]} by {object[1]}"
        else:
            result = f"{i+1}. {object}"
        result += f", played {len(plays)} times for {play_hours} hours {play_mins} minutes, first played" 
        if cmd != Cmd.TRACK:
            result += f" {first_play_track}"
        result += f" on {first_play_date}"
        print(result)

def parse_data():
    folder = Path("data")
    data = []
    for file in folder.iterdir():
        if file.is_file() and file.suffix == ".json":
            with open(file, "r") as f:
                try:
                    parsed_data = json.load(f)
                    if isinstance(parsed_data, list):
                        data.extend(parsed_data)
                except json.JSONDecodeError as e:
                    print(f"Error parsing {file.name}: {e}")
                except Exception as e:
                    print(f"Unexpected error with {file.name}: {e}")
    return data

def process_data(args, data):
    song_plays = {}
    artist_plays = {}
    album_plays = {}
    skips = {}
    total_time = 0

    for play in data:
        uri = play["spotify_track_uri"]

        artist = play["master_metadata_album_artist_name"]
        track = play["master_metadata_track_name"]
        album = play["master_metadata_album_album_name"]
        if DUPLICATES and track in DUPLICATES:
            song = (track, artist, album)
        else:
            song = (track, artist)

        # album = (album, artist) # We don't get album by artist because we kinda can't (we could get it by average?)
        
        if artist is None or track is None:
            continue
        if IGNORE and artist in IGNORE:
            continue

        # Playtime
        time = play["ms_played"]
        skip = play["skipped"]
        if time > 30000:
            total_time += time
        elif skip:
            if song not in skips:
                skips[song] = []
            skips[song].append(play)
            continue

        # Artist plays
        if artist not in artist_plays:
            # TODO: Potentially incorrectly assumes data is iterated in chronological order!
            artist_plays[artist] = []
        artist_plays[artist].append(play)

        # Album plays
        if album not in album_plays:
            album_plays[album] = []
        album_plays[album].append(play)

        # Track plays
        if song not in song_plays:
            song_plays[song] = []
        song_plays[song].append(play)

    return ProcessedData(song_plays, artist_plays, album_plays, skips, total_time)

def date(play):
    return datetime.strptime(play["ts"], "%Y-%m-%dT%H:%M:%SZ")

def parse_args():
    load_dotenv()

    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET")
    ))

    parser = argparse.ArgumentParser(description="A tool to analyse your spotify data")
    args = parser.parse_args()
    main(args)

if __name__ == "__main__":
    parse_args()

