Tiny synthetic containers for `tests/test_container.py` — one second of
`testsrc` at 32×32, generated once with ffmpeg and committed so the test
suite never needs ffmpeg to build a fixture (the point of container.py is
that mediasmith no longer needs ffmpeg to read one).

`titled.*` carry `title=Aliens.1986.SE.1080p.BluRay.x265-RARBG`;
`untitled.*` were muxed with `-map_metadata -1`.
