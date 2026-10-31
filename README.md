# Mediasmith

Mediasmith is a metadata editor for audio, video, image, and ebook files.


## Set Up

This project depends on `uv` to simplify its Python environment.
```
brew install uv
```
Launch `mediasmith` from any directory by running the install script.
```
./install.sh
```


## Install it somewhere else

For someone who is not working on mediasmith — a friend who just wants
to use it. One command, every platform, and it keeps itself current:

```
uv tool install git+https://github.com/nickmeccia/mediasmith
```

`mediasmith` is then on their PATH. On launch it quietly asks GitHub
(at most once a day) whether there is a newer commit, upgrades itself
when there is, and says so — the new version runs the next time they
start it. `MEDIASMITH_NO_UPDATE=1` turns that off, and a copy run from
a git checkout is never touched.

Four features need a tool mediasmith cannot bundle, and each is absent
rather than broken without it: **ffmpeg** (video → GIF), **alass**
(subtitle sync), **potrace** (image trace) and **Calibre** (ebook
conversion). Poster search also wants a TMDB key in
`~/.config/mediasmith/tmdb_api_key`.


## Run

Launch mediasmith from the current directory:
```
mediasmith
```

Launch mediasmith from another directory:
```
mediasmith ~/Downloads
```

If you did not install the `mediasmith` command, this app must be launched from the `/mediasmith` repository location.
```
cd ~/code/mediasmith
uv run mediasmith
```


## Test

Run unit & interaction tests:
```
uv run pytest
```

Run random-input stress gate:
```
uv run python tests/fuzz.py
```

