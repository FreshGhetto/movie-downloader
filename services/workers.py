import json
import re
import subprocess
import requests
from PySide6.QtCore import QThread, Signal
from services.core import FLAGS, validate_url, metadata

class Task(QThread):
    result = Signal(object)
    error = Signal(str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.result.emit(self.fn())
        except Exception as e:
            self.error.emit(str(e))

def analyze(exe, url):
    validate_url(url)
    p = subprocess.run([exe,'--ignore-config','--no-playlist','--skip-download','--dump-single-json','--socket-timeout','20','--retries','1','--',url], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=90, **FLAGS)
    if p.returncode:
        raise ValueError('Link non supportato, scaduto o non accessibile.\n' + p.stderr[-2500:])
    return metadata(json.loads(p.stdout))

def _tmdb_auth(key):
    key = key.strip()
    if not key:
        raise ValueError('Configura la chiave API TMDb nelle impostazioni.')
    headers = {}
    params = {}
    if key.lower().startswith('bearer ') or key.count('.') == 2:
        token = key[7:].strip() if key.lower().startswith('bearer ') else key
        headers['Authorization'] = 'Bearer ' + token
    else:
        params['api_key'] = key
    return headers, params

def _fetch_posters(results):
    for item in results:
        if item.get('poster_path'):
            try:
                poster = requests.get('https://image.tmdb.org/t/p/w185' + item['poster_path'], timeout=8)
                if poster.ok:
                    item['poster_bytes'] = poster.content
            except requests.RequestException:
                pass

def search_tmdb(query, key, kind):
    headers, auth_params = _tmdb_auth(key)
    params = {'query': query, 'language': 'it-IT', 'include_adult': 'false', **auth_params}
    try:
        r = requests.get(f'https://api.themoviedb.org/3/search/{kind}', params=params, headers=headers, timeout=20)
    except requests.RequestException:
        raise ValueError('TMDb non raggiungibile. Controlla la connessione e riprova.') from None
    if r.status_code != 200:
        raise ValueError(f'TMDb: errore HTTP {r.status_code}. Verifica la chiave API.')
    results = r.json().get('results', [])[:12]
    for item in results:
        item['_kind'] = kind
    _fetch_posters(results)
    return results

def search_tmdb_both(query, key):
    headers, auth_params = _tmdb_auth(key)
    combined = []
    for kind in ('movie', 'tv'):
        params = {'query': query, 'language': 'it-IT', 'include_adult': 'false', **auth_params}
        try:
            r = requests.get(f'https://api.themoviedb.org/3/search/{kind}', params=params, headers=headers, timeout=20)
            if r.status_code == 200:
                for item in r.json().get('results', [])[:8]:
                    item['_kind'] = kind
                    combined.append(item)
        except requests.RequestException:
            pass
    if not combined:
        raise ValueError('TMDb non raggiungibile o nessun risultato.')
    combined.sort(key=lambda x: x.get('popularity', 0), reverse=True)
    combined = combined[:12]
    _fetch_posters(combined)
    return combined

def update_ytdlp(exe_path):
    p = subprocess.run([exe_path, '--update'], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120, **FLAGS)
    output = (p.stdout + '\n' + p.stderr).strip()
    if p.returncode:
        raise ValueError(output[-2000:])
    return output

def check_app_update(current_version):
    try:
        r = requests.get('https://api.github.com/repos/FreshGhetto/movie-downloader/releases/latest', timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        tag = data.get('tag_name', '').lstrip('v')
        if not re.fullmatch(r'\d+\.\d+\.\d+', tag) or not re.fullmatch(r'\d+\.\d+\.\d+', current_version):
            return None
        if tuple(map(int, tag.split('.'))) > tuple(map(int, current_version.split('.'))):
            url = data.get('html_url', '')
            return {'version': tag, 'url': url}
        return {'version': tag, 'url': '', 'up_to_date': True}
    except requests.RequestException:
        return None
