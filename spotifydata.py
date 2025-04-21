import json
import argparse
import difflib
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

from config import *

@dataclass
class ProcessedData:
    song_plays: dict
    artist_plays: dict
    album_plays: dict
    skips: dict
    total_time: int

class Object(Enum):
    TRACK = "track"
    ALBUM = "album"
    ARTIST = "artist"

def main(args):
    data = parse_data()
    pd = process_data(args, data)

    # TODO: Find the longest repeat of a track!
    # TODO: Change tracks to URIs?

    # TODO: Add filter by Year or Month for all print_object

    try:
        while True:
            search = input("What would you like to search? ").lower()
            search = search.split(" ", maxsplit=1)
            cmd = search[0]
            match cmd:
                case "summary":
                    print_summary(data, pd)
                case "artist":
                    if len(search) < 2:
                        print_object(ARTISTMODE, pd.artist_plays) # TODO: Link enum of cmds to their modes
                        continue
                    artist = search[1]
                    match_list = difflib.get_close_matches(artist, pd.artist_plays.keys(), n=1, cutoff=0.5)
                    if not match_list:
                        print("No artist found.")
                        continue
                    print_artist(pd.artist_plays, match_list[0])
                case Object.TRACK.value:
                    print_object(TRACKMODE, pd.song_plays)
                case Object.ALBUM.value:
                    print_object(ALBUMMODE, pd.album_plays)
                case "skips":
                    print_object(Mode.PLAYS, pd.skips)
                case "exit":
                    print("Bye!")
                    break
                case "help":
                    print("Commands:")
                    print("summary - Show a summary of your data")
                    print("artists - Show your top artists")
                    print("artist 'artist_name' - Show data for a specific artist")
                    print("tracks - Show your top tracks")
                    print("albums - Show your top albums")
                    print("skips - Show your most skipped songs")
                    print("exit - Exit the program")
                case _:
                    print("Unknown command. Type 'help' for a list of commands.")
                    continue
    except KeyboardInterrupt:
        print("\nBye!")

def print_summary(data, pd):
    print("Summary:")
    print(f"Total songs played: {len(data)}")
    print(f"Unique songs played: {len(pd.song_plays.keys())}")
    print(f"Unique artists played: {len(pd.artist_plays.keys())}")
    print(f"Total time: {pd.total_time // 3600000} hours")
    print_artists(pd.artist_plays)
    print_tracks(pd.song_plays)
    print_skips(pd.skips)

def print_artists(artist_plays):
    # A list of artists sorted by their highest plays
    if ARTISTMODE == Mode.PLAYS:
        top_artists = sorted(artist_plays.items(), key=lambda item: len(item[1]), reverse=True)
    elif ARTISTMODE == Mode.TIME:
        top_artists = sorted(artist_plays.items(), key=lambda item: sum(play["ms_played"] for play in item[1]), reverse=True)
    print("Top artists:")
    for i in range(RESULTS):
        artist = top_artists[i][0]
        plays = top_artists[i][1]
        plays_no = len(top_artists[i][1])
        play_time = sum(play["ms_played"] for play in top_artists[i][1])
        first_play = min(plays, key=lambda play: datetime.strptime(play["ts"], "%Y-%m-%dT%H:%M:%SZ"))
        first_play_track = first_play["master_metadata_track_name"]
        first_play_date = datetime.strptime(first_play["ts"], "%Y-%m-%dT%H:%M:%SZ").strftime("%-d %B, %Y")
        print(f"{artist}, played {plays_no} times for {play_time // 3600000} hours {(play_time // 60000) % 60} minutes, first played: {first_play_track} on {first_play_date}")

# TODO: Can I refactor the print_artist and print_artists functions? they essentially do the same thing, printing top tracks for a list of artists (special case where list is length = 1)
def print_artist(artist_plays, artist):
    plays = artist_plays[artist]
    first_play = min(plays, key=lambda play: datetime.strptime(play["ts"], "%Y-%m-%dT%H:%M:%SZ"))
    first_play_track = first_play["master_metadata_track_name"]
    first_play_date = datetime.strptime(first_play["ts"], "%Y-%m-%dT%H:%M:%SZ").strftime("%-d %B, %Y")

    artist_song_plays = {}
    for play in plays:
        track = play["master_metadata_track_name"]
        album = play["master_metadata_album_album_name"]
        if DUPLICATES and track in DUPLICATES:
            song = (track, artist, album)
        else:
            song = (track, artist)
        if song not in artist_song_plays:
            artist_song_plays[song] = []
        artist_song_plays[song].append(play)
    top_tracks = sorted(artist_song_plays.items(), key=lambda item: len(item[1]), reverse=True)
    print(f"Summary for {artist}:")
    print(f"Total listens: {len(plays)}")
    print(f"First played: {first_play_track} on: {first_play_date}")

    print(f"Top tracks:")
    for i in range(min(RESULTS, len(artist_song_plays))):
        song = top_tracks[i][0]
        plays_no = len(top_tracks[i][1])
        print(f"{song[0]}, {plays_no} plays")


def print_object(mode, object_plays):
    if mode == Mode.PLAYS:
        top_objects = sorted(object_plays.items(), key=lambda item: len(item[1]), reverse=True)
    elif mode == Mode.TIME:
        top_objects = sorted(object_plays.items(), key=lambda item: sum(play["ms_played"] for play in item[1]), reverse=True)
    print(f"Top BLANK:")
    for i in range(RESULTS):
        object = top_objects[i][0] # TODO: Calculate the artist for an album based on how much they appear.
        plays_no = len(top_objects[i][1])
        play_time = sum(play["ms_played"] for play in top_objects[i][1])
        play_hours = play_time // 3600000
        play_mins = (play_time // 60000) % 60
        # TODO: Change object to enum?
        print(f"{object}, played {plays_no} times for {play_hours} hours {play_mins} minutes")


# TODO: Refactor print_albums and print_tracks
def print_albums(album_plays):
    if ALBUMMODE == Mode.PLAYS:
        top_albums = sorted(album_plays.items(), key=lambda item: len(item[1]), reverse=True)
    elif ALBUMMODE == Mode.TIME:
        top_albums = sorted(album_plays.items(), key=lambda item: sum(play["ms_played"] for play in item[1]), reverse=True)
    print("Top albums:")
    for i in range(RESULTS):
        album = top_albums[i][0]
        play_time = sum(play["ms_played"] for play in top_albums[i][1])
        plays_no = len(top_albums[i][1])
        print(f"{album}, played {plays_no} times for {play_time // 3600000} hours {(play_time // 60000) % 60} minutes")

def print_tracks(song_plays):
    if TRACKMODE == Mode.PLAYS:
        top_tracks = sorted(song_plays.items(), key=lambda item: len(item[1]), reverse=True)
    elif TRACKMODE == Mode.TIME:
        top_tracks = sorted(song_plays.items(), key=lambda item: sum(play["ms_played"] for play in item[1]), reverse=True)
    print("Top tracks:")
    for i in range(RESULTS):
        song = top_tracks[i][0]
        play_time = sum(play["ms_played"] for play in top_tracks[i][1])
        plays_no = len(top_tracks[i][1])
        print(f"{song[0]} by {song[1]}, played {plays_no} times for {play_time // 3600000} hours {(play_time // 60000) % 60} minutes")

def print_skips(skips):
    top_skips = sorted(skips.items(), key=lambda item: len(item[1]), reverse=True)
    print("Most skipped:")
    for i in range(RESULTS):
        song = top_skips[i][0]
        skip_no = len(top_skips[i][1])
        print(f"{song[0]} by {song[1]}, {skip_no} skips")

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
        artist = play["master_metadata_album_artist_name"]
        track = play["master_metadata_track_name"]
        album = play["master_metadata_album_album_name"]
        if DUPLICATES and track in DUPLICATES:
            song = (track, artist, album)
        else:
            song = (track, artist)

        # album = (album, artist)
        
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

def parse_args():
    parser = argparse.ArgumentParser(description="A tool to analyse your spotify data")
    args = parser.parse_args()
    main(args)

if __name__ == "__main__":
    parse_args()

