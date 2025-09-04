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
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
from pathlib import Path
from datetime import datetime, timedelta
from dateutil import parser
from dataclasses import dataclass
from enum import Enum, auto
from dotenv import load_dotenv
from rapidfuzz import process, fuzz

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
    TRACKS = ("tracks", Mode.PLAYS)
    TRACK = ("track", Mode.PLAYS)
    ALBUMS = ("albums", Mode.TIME)
    ALBUM = ("album", Mode.PLAYS)
    ARTISTS = ("artists", Mode.TIME)
    ARTIST = ("artist", Mode.PLAYS)
    SKIPS = ("skips", Mode.PLAYS)
    SUMMARY = ("summary", None)
    FILTER = ("filter", None)
    RESULT = ("result", None)
    MAKE = ("make", None)
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
ALBUMSLIMIT = 3

STARTFILTER = datetime.min
ENDFILTER = datetime.max

def make_cmd(top_songs):
    if not top_songs:
        print("No track list found. Please make a query to get a list.")
    if len(top_songs) > 1000:
        print("Number of results exceeds limit (1000 tracks).")
        return
    
    try:
        load_dotenv()

        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            scope="playlist-modify-public playlist-modify-private",
            client_id=os.getenv("SPOTIFY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
            redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI")
        ))

        user_id = sp.current_user()["id"]

        playlist = sp.user_playlist_create(
            user=user_id,
            name=f"top {RESULTS}", # TODO: Add artist to name if singular artist
            public=False,
            description=f"{STARTFILTER.strftime('%d-%m-%Y')} to {ENDFILTER.strftime('%d-%m-%Y')}"
        )
    
        top_song_uris = []
        for item in top_songs:
            top_song_uris.append(item[1][0]["spotify_track_uri"])
        
        MAX_URIS = 100
        for i in range(0, len(top_song_uris), MAX_URIS):
            sp.playlist_add_items(
                playlist_id=playlist["id"],
                items=top_song_uris[i:i+MAX_URIS]
            )
        print("Successfully created new playlist!")
    except:
        print("Error creating playlist.")

def result_cmd():
    global RESULTS
    number = input("How many results? ")
    if not number:
        print("No number provded. Please provide a number to set result limit.")
        return
    RESULTS = int(number)

def filter_cmd():
    global STARTFILTER, ENDFILTER
    startfilter = input("Please provide a start date: ")
    endfilter = input("Please provide an end date: ")
    startfilter.strip()
    endfilter.strip()

    if startfilter:
        try:
            startfilter = parser.parse(startfilter)
            STARTFILTER = startfilter
            print("Added start date:", STARTFILTER.strftime("%d-%m-%Y"))
        except parser.ParserError:
            print("Invalid date. Please provide a correct date format.")
            return
    if endfilter:
        try:
            endfilter = parser.parse(endfilter)
            print(endfilter)
            ENDFILTER = endfilter
            print("Added end date:", ENDFILTER.strftime("%d-%m-%Y"))
        except parser.ParserError:
            print("Invalid date. Please provide a correct date format.")
            return
    if ENDFILTER < STARTFILTER:
        STARTFILTER = datetime.min
        ENDFILTER = datetime.max
        print("Invalid filters. Start date must be before end date.")
        return

def artist_cmd(pd):
    artist_name = input("Which artist? ")
    match_list = difflib.get_close_matches(artist_name, (key.lower() for key in pd.artist_plays.keys()), n=1, cutoff=0.5)
    if not match_list:
        print("Could not find artist.")
        return
    match_list = [key for key in pd.artist_plays if key.lower() in match_list]
    artist_song_plays = {song: plays for song, plays in pd.song_plays.items() if song[1] == match_list[0]}
    return print_object(Cmd.TRACKS, artist_song_plays)

def track_cmd(pd):
    track_name = input("What track? ")
    artist_name = input("By which artist? ")

    # Search by artist
    match_list = difflib.get_close_matches( # TODO: Change to RapidFuzz?
        artist_name, 
        (artist for artist in pd.artist_plays.keys()),
        n=1, 
        cutoff=0.5
    )
    if not match_list:
        print("Could not find artist. Please try again.")
        return
    artist_name = match_list[0]
    artist_song_plays = {song: plays for song, plays in pd.song_plays.items() if song[1] == artist_name}

    # Search by tracks for that artist
    track_match_list = process.extract( # TODO: Create search helper function?
        track_name.lower(),
        (song[0].lower() for song in artist_song_plays.keys()), # TODO: Convert to list beforehand?
        scorer=fuzz.partial_ratio,
        limit=5
    )
    song_key_list = list(artist_song_plays.keys())
    song_match_list = [song_key_list[match[2]] for match in track_match_list if match[1] >= 80]

    if len(song_match_list) <= 0:
        print("Could not find song. Please check your spelling and try again.")
        return
    elif len(song_match_list) == 1:
        number = 1
    else:
        print("Songs found:")
        for i, match in enumerate(song_match_list):
            res = f"{i+1}. {match[0]} by {match[1]}"
            if len(match) >= 3:
                res += f", from {match[2]}"
            print(res)
        number = int(input("Please type a number to select the result you are looking for: "))
        while number < 1 or number > len(song_match_list):
            number = int(input("Invalid number. Please try again."))

    song = song_match_list[number-1]
    print_object(Cmd.TRACK, {song: pd.song_plays[song]})

def custom_score(query, choice, **kwargs):
        return (0.4 * fuzz.partial_ratio(query, choice) + 0.4 * fuzz.token_set_ratio(query, choice) + 0.2 * fuzz.WRatio(query, choice))

def album_cmd(pd):
    album_name = input("Which album? ")

    album_match_list = process.extract(
        album_name.lower(),
        (album.lower() for album in pd.album_plays.keys()),
        scorer=custom_score,
        limit=5
    )
    if not album_match_list:
        print("Could not find album. Please check spelling and try again.")
        return
    print(album_match_list)
    index = album_match_list[0][2]
    album = list(pd.album_plays)[index]

    album_song_plays = {}
    for play in pd.album_plays[album]:
        artist = play["master_metadata_album_artist_name"]
        track = play["master_metadata_track_name"]

        song = (track, artist) # TODO: Artist potentially not needed?
        if song not in album_song_plays:
            album_song_plays[song] = []
        album_song_plays[song].append(play)

    print_object(Cmd.TRACKS, album_song_plays)

def help_cmd():
    print("Commands:")
    print("summary - Show a summary of your data")
    print("artist - Show data for a specific artist")
    print("artists - Show data for all artists")
    print("track - Show data for a specific track")
    print("tracks - Show your top tracks")
    print("album - Show data for a specific album")
    print("albums - Show your top albums")
    print("skip - Show your most skipped songs")
    print("filter - Sets filters for results")
    print("help - Shows this list of commands")
    print("make - Make a spotify playlist based on the previous track or specific artist query")
    print("exit - Exit the program")

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

    global RESULTS, STARTFILTER, ENDFILTER
    top_songs = None
    
    # Process commands
    try:
        while True:
            msg = input("What would you like to do? ")
            msg = msg.split(" ", maxsplit=1)
            cmd = msg[0]
            match cmd:
                case Cmd.MAKE.text:
                    make_cmd(top_songs)
                case Cmd.RESULT.text:
                    result_cmd()
                case Cmd.FILTER.text:
                    filter_cmd()
                case Cmd.SUMMARY.text:
                    print_summary(pd)
                case Cmd.ARTISTS.text:
                    print_object(Cmd.ARTISTS, pd.artist_plays)
                case Cmd.ARTIST.text:
                    top_songs = artist_cmd(pd)
                case Cmd.TRACKS.text:
                    print_object(Cmd.TRACKS, pd.song_plays)
                case Cmd.TRACK.text:
                    track_cmd(pd)
                case Cmd.ALBUMS.text:
                    print_object(Cmd.ALBUMS, pd.album_plays)
                case Cmd.ALBUM.text:
                    album_cmd(pd)
                case Cmd.SKIPS.text:
                    print_object(Cmd.SKIPS, pd.skips)
                case Cmd.EXIT.text:
                    print("Exiting program...")
                    break
                case Cmd.HELP.text:
                    help_cmd()
                case _:
                    print("Unknown command. Type 'help' for a list of commands.") 
                    continue
            print("=" * shutil.get_terminal_size().columns)
    except KeyboardInterrupt:
        print("\nExiting program...")

def print_summary(pd):
    print("Summary:")
    print(f"Total songs played: {sum(len(song) for song in pd.song_plays.values())}")
    print(f"Unique songs played: {len(pd.song_plays.keys())}")
    print(f"Unique artists played: {len(pd.artist_plays.keys())}")
    print(f"Total time: {pd.total_time // 3600000} hours")

def print_object(cmd, object_plays, sp=None):
    print("=" * shutil.get_terminal_size().columns)
    # Filter object plays and remove keys with no valid filtered results
    object_plays = {
        obj: filtered
        for obj, plays in object_plays.items()
        if (filtered := [play for play in plays if STARTFILTER <= date(play) <= ENDFILTER])
    }
    if not object_plays:
        print("No plays found.")
        return

    # Filter albums and remove those with less than ALBUMSLIMIT number of unique songs
    if cmd == Cmd.ALBUMS:
        object_plays = {
            obj: plays
            for obj, plays in object_plays.items()
            if len({play["master_metadata_track_name"] for play in plays}) >= ALBUMSLIMIT
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

    if cmd == Cmd.TRACK:
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            scope="user-library-read",
            client_id=os.getenv("SPOTIFY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
            redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI")
        ))

        uri = all_plays[0]["spotify_track_uri"]
        id = uri.split(":")[2]
        song = sp.track(id)
        print(f"Popularity: {song['popularity']} / 100")

    # TODO: Create get_object() helper function that gets artist / album / track name based on current cmd?
    if cmd == Cmd.TRACK:
        print(f"First played {first_play_track} by {first_play_artist} on {first_play_date}")

    print(f"Total: {sum(len(plays) for plays in object_plays.values())} {'skip' if cmd == Cmd.SKIPS else 'play'}(s)")
    if cmd != Cmd.TRACK:
        print(f"Unique: {len(object_plays.keys())} {cmd.text}(s)")
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
            if cmd == Cmd.TRACKS or cmd == Cmd.SKIPS:
                result = f"{i+1}. {object[0]} by {object[1]}"
            else:
                result = f"{i+1}. {object}"
            result += f", played {len(plays)} times for {play_hours} hours {play_mins} minutes, first played" 
            if cmd != Cmd.TRACKS:
                result += f" {first_play_track}"
            result += f" on {first_play_date}"
            print(result)
        return top_objects[:RESULTS]

def parse_data():
    folder = Path(".data")
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
    global STARTFILTER, ENDFILTER
    song_plays = {}
    artist_plays = {}
    album_plays = {}
    skips = {}
    total_time = 0

    for play in data:
        # TODO: Introduce with multithreading.
        # play_date = date(play)
        # STARTFILTER = min(play_date, STARTFILTER)
        # ENDFILTER = max(play_date, ENDFILTER)

        # uri = play["spotify_track_uri"]

        artist = play["master_metadata_album_artist_name"]
        track = play["master_metadata_track_name"]
        album = play["master_metadata_album_album_name"]
        if DUPLICATES and track in DUPLICATES:
            song = (track, artist, album) # Include album to differentiate
        else:
            song = (track, artist) # Otherwise assume songs from different albums are the same
        
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
    parser = argparse.ArgumentParser(description="A tool to analyse your spotify data")
    args = parser.parse_args()
    main(args)

if __name__ == "__main__":
    parse_args()