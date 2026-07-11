#!/bin/bash
npm install left-pad
pip install requests
brew install ffmpeg
uv sync
uv run --with requests python script.py
uv run --with=requests python script.py
uv run --with "requests>=2" python script.py
uv run --with='requests>=2' python script.py
uvx unreviewed-tool
git clone https://example.com/unreviewed-course.git
