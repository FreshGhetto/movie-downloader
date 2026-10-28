import json
import os
from pathlib import Path

ROOT = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'MovieDownloader'
DEFAULTS = {'movie_dir': 'E:/Film', 'tv_dir': 'E:/Serie TV', 'tmdb_key': '', 'ffmpeg': '', 'fragments': 16, 'subtitles': True, 'sub_langs': 'it,en', 'custom_paths': []}

def load():
    try:
        return DEFAULTS | json.loads((ROOT / 'settings.json').read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError):
        return DEFAULTS.copy()

def save(data):
    ROOT.mkdir(parents=True, exist_ok=True)
    temp = ROOT / 'settings.tmp'
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(ROOT / 'settings.json')

def load_queue():
    try:
        return json.loads((ROOT / 'queue.json').read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError):
        return []

def save_queue(jobs):
    ROOT.mkdir(parents=True, exist_ok=True)
    temp = ROOT / 'queue.tmp'
    temp.write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(ROOT / 'queue.json')

def load_history():
    try:
        return json.loads((ROOT / 'history.json').read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError):
        return []

def save_history(entries):
    ROOT.mkdir(parents=True, exist_ok=True)
    temp = ROOT / 'history.tmp'
    temp.write_text(json.dumps(entries[-500:], ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(ROOT / 'history.json')
