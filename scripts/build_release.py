"""Build a versioned standalone Windows release and its distribution archive."""
import hashlib
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config.version import VERSION


def main():
    if sys.platform != 'win32':
        raise SystemExit('Build this Windows release on Windows.')
    if not re.fullmatch(r'\d+\.\d+\.\d+', VERSION):
        raise SystemExit('VERSION must use major.minor.patch.')
    notes = ROOT / 'releases' / f'v{VERSION}.md'
    ytdlp = ROOT / 'bin' / 'yt-dlp.exe'
    for required in (notes, ytdlp, ROOT / 'icon.ico'):
        if not required.is_file():
            raise SystemExit(f'Missing release input: {required}')

    name = f'MovieDownloader-v{VERSION}'
    work = ROOT / 'work' / 'release-build' / VERSION
    output = ROOT / 'dist-aggiornata' / f'v{VERSION}'
    work.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    numeric = tuple(map(int, VERSION.split('.'))) + (0,)
    resource = work / 'version-info.txt'
    resource.write_text(f'''VSVersionInfo(
  ffi=FixedFileInfo(filevers={numeric!r}, prodvers={numeric!r},
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('FileDescription', 'Movie Downloader'),
    StringStruct('FileVersion', '{VERSION}.0'),
    StringStruct('InternalName', 'MovieDownloader'),
    StringStruct('OriginalFilename', '{name}.exe'),
    StringStruct('ProductName', 'Movie Downloader'),
    StringStruct('ProductVersion', '{VERSION}')
  ])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])]
)
''', encoding='utf-8')

    subprocess.run([
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
        '--windowed', '--onefile', '--name', name,
        '--distpath', str(output), '--workpath', str(work / 'build'),
        '--specpath', str(work), '--icon', str(ROOT / 'icon.ico'),
        '--version-file', str(resource),
        '--add-binary', f'{ytdlp};bin', str(ROOT / 'main.py'),
    ], cwd=ROOT, check=True)

    executable = output / f'{name}.exe'
    release_notes = output / f'RELEASE_NOTES-v{VERSION}.md'
    shutil.copy2(notes, release_notes)
    readme = output / 'LEGGIMI.txt'
    readme.write_text(
        f'Movie Downloader {VERSION} - Windows x64\n\n'
        f'Avvia {executable.name}. Non serve installare Python.\n'
        'FFmpeg deve essere installato o indicato nelle impostazioni.\n'
        'yt-dlp e incluso. La ricerca film richiede una credenziale TMDb.\n'
        'Le preferenze esistenti restano in %LOCALAPPDATA%\\MovieDownloader.\n'
        'Chiudi normalmente la versione precedente prima di avviare questa.\n'
        f'Consulta {release_notes.name} per le novita.\n', encoding='utf-8')
    archive = output / f'{name}-windows-x64.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for file in (executable, release_notes, readme, ROOT / 'LICENSE'):
            bundle.write(file, arcname=file.name)
    checksum = output / 'SHA256SUMS.txt'
    hashes = []
    for file in (executable, archive):
        with file.open('rb') as stream:
            hashes.append(f'{hashlib.file_digest(stream, "sha256").hexdigest()}  {file.name}\n')
    checksum.write_text(''.join(hashes), encoding='ascii')
    launcher = ROOT / 'Avvia aggiornato.bat'
    launcher.write_text(
        '@echo off\ncd /d "%~dp0"\n'
        f'start "Movie Downloader {VERSION}" "dist-aggiornata\\v{VERSION}\\{name}.exe"\n',
        encoding='utf-8')
    print(f'Release {VERSION}: {output}')


if __name__ == '__main__':
    main()
