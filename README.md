# Mmediasmith

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

