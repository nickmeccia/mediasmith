![Mediasmith](docs/images/banner.png)

# Mediasmith

Mediasmith is a metadata editor & conversion tool for audio, video, image, and ebook files. Compared to traditional GUI workflows, Mediasmith offers a more convenient user expeience for numerous, frequent, and batch operations.

## User Setup

### Getting Started

Clone & install project.
```
uv tool install git+https://github.com/nickmeccia/mediasmith
```

### Launch App

Launch mediasmith from the current directory:
```
mediasmith
```

Launch mediasmith from another directory:
```
mediasmith ~/Downloads
```

### Automatic Updates

Mediasmith is under active development, and updates, bug fixes, and new features are shipped regularly. By installing this project with `uv tool install`, you will automatically receive updates once per day. 

If you want to turn automatic updates off, add the following line to your `zshrc` or `bashrc`:
```
MEDIASMITH_NO_UPDATE=1
```

### External Dependencies

Four features found in Mediasmith require external dependencies to function. They are:

- **Convert Video to GIF** — *Requires [ffmpeg](https://github.com/ffmpeg/ffmpeg)*
- **Sync Subtitles with Video** — *Requires [alass](https://github.com/kaegi/alass)*
- **Trace Image & Convert to Vector** — *Requires [potrace](https://github.com/skyrpex/potrace)*
- **Convert Ebook** — *Requires [Calibre](https://calibre-ebook.com/download)*

A fifth feature, **Download Movie Posters**, requires a free API key from [The Movie Database](https://www.themoviedb.org/).

- First, follow [these instructions](https://developer.themoviedb.org/docs/getting-started) for acquiring an API key.
- Then, create a new file in your home directory at `~/.config/mediasmith/tmdb_api_key` and paste your API key. 

## Developer Setup

### Install Dependencies

This project depends on `uv` to simplify its Python environment.
```
brew install uv
```
Launch `mediasmith` from any directory by running the install script.
```
./install.sh
```

### Launch App

Launch Mediasmith from the current directory:
```
mediasmith
```

Launch Mediasmith from another directory:
```
mediasmith ~/Downloads
```

If you did not install the `mediasmith` command, this app must be launched from the `/mediasmith` repository location.
```
cd ~/code/mediasmith
uv run mediasmith
```

### Run Tests

Run unit & interaction tests:
```
uv run pytest
```

Run random-input stress gate:
```
uv run python tests/fuzz.py
```

