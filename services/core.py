import json
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

FLAGS = {'creationflags': subprocess.CREATE_NO_WINDOW} if hasattr(subprocess, 'CREATE_NO_WINDOW') else {}

def validate_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ('https', 'http') or not parsed.hostname:
        raise ValueError('Inserisci un URL HTTP o HTTPS valido.')
    return url

def safe_name(title, year=''):
    title = re.sub(r'[<>:"/\\|?*\x00-\x1f%]', '_', title).strip(' .')[:140] or 'Video'
    if title.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}:
        title = '_' + title
    return f'{title} ({year})' if re.fullmatch(r'\d{4}', str(year)) else title

def unique_base(directory, name, reserved=()):
    root = Path(directory)
    candidate = root / name
    n = 2
    existing = {p.name.casefold() for p in root.iterdir()} if root.exists() else set()
    reserved = {str(p).casefold() for p in reserved}
    while str(candidate).casefold() in reserved or any(name.startswith(candidate.name.casefold() + '.') for name in existing):
        candidate = root / f'{name} ({n})'
        n += 1
    return candidate

def metadata(data):
    if data.get('_type') in ('playlist', 'multi_video'):
        raise ValueError('Inserisci il link di un singolo video, non una playlist.')
    if data.get('has_drm'):
        raise ValueError('La sorgente usa DRM: download non consentito.')
    formats = [f for f in data.get('formats', []) if not f.get('has_drm')]
    heights = sorted({int(f['height']) for f in formats if f.get('height') and f.get('vcodec') != 'none'}, reverse=True)
    return {'title': data.get('title') or 'Video', 'year': str(data.get('release_year') or '') , 'heights': heights}

def progress(line):
    if not line.startswith('MD_PROGRESS:'):
        return None
    try:
        d = json.loads(line.split(':',1)[1])
        total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
        return {'percent': min(100, (d.get('downloaded_bytes') or 0)*100/total) if total else 0,
                'size': total, 'speed': d.get('speed') or 0, 'eta': d.get('eta'), 'status': d.get('status')}
    except (ValueError, TypeError):
        return None

def find_ffmpeg(path=''):
    if path:
        p = Path(path)
        return str(p / 'ffmpeg.exe' if p.is_dir() else p)
    return shutil.which('ffmpeg') or ''

def version(path):
    if not path or not Path(path).is_file():
        raise ValueError('Eseguibile non trovato: ' + (path or 'FFmpeg'))
    result = subprocess.run([path, '-version' if 'ffmpeg' in Path(path).name.lower() else '--version'], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=20, **FLAGS)
    if result.returncode:
        raise ValueError(result.stderr[-1000:])
    return result.stdout.splitlines()[0]

def command(exe, job, ffmpeg):
    args = [exe, '--ignore-config', '--no-playlist', '--no-overwrites', '--continue', '--newline', '--progress', '--progress-template', 'download:MD_PROGRESS:%(progress)j', '--socket-timeout','20','--retries','3','--fragment-retries','3', '--concurrent-fragments', str(job['fragments']), '-o', job['base'] + '.%(ext)s']
    if ffmpeg:
        args += ['--ffmpeg-location', ffmpeg]
    if job.get('subtitles') and job.get('sub_langs'):
        args += ['--write-subs', '--sub-langs', job['sub_langs'], '--embed-subs']
    quality = job['quality']
    if quality == 'audio':
        args += ['-f', 'bestaudio/best', '-x', '--audio-format', 'm4a']
    else:
        limit = '' if quality == 'best' else f'[height<={quality}]'
        args += ['-f', f'bv*{limit}+ba/b{limit}', '--merge-output-format', 'mp4/mkv']
        if ffmpeg:
            args += ['--remux-video','mp4/mkv']
    return args + ['--', job['url']]
