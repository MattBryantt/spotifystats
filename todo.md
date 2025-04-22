# TODO List

## Features

- [ ] Find the longest repeat of a track
- [X] Add filter by year or month for all `print_object`
- [ ] Add search by specific album or track?

## Improvements

- [ ] Potentially remove `album_plays` / `artist_plays` ?
- [ ] Add types to code
- [X] Change track keys to ISRC from spotify API -> Too slow!
- [ ] Calculate the artist for an album based on how much they appear OR get from spotify API
- [ ] Potentially change the ranking of albums to include multiple songs at a minimum? (e.g. must have >= 3 different songs to count)

### Printing
- [X] Only print out song name of 'first played' if object is NOT track
- [X] Only print 'by {artist}' if object is NOT artist
- [ ] Change 'Total listens" for skip command

## Duplicate Issues
- [ ] 10. Saw You In a Dream by The Japanese House, played 108 times for 4 hours 31 minutes, first played on 18 May, 2019
- [ ] 13. Saw You in a Dream by The Japanese House, played 88 times for 4 hours 38 minutes, first played on 19 July, 2020
- [ ] Ignore case?