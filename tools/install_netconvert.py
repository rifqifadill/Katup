import hashlib
import json
from pathlib import Path
import platform
import urllib.request
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.28.0'


def install():
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'AMD64'):
        raise SystemExit('installer ini untuk Linux x86_64, platform lain bisa memakai netconvert 1.28 dari instalasi SUMO resmi')
    directory = ROOT / '.runtime-llm' / 'netconvert-1.28'
    directory.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(f'https://pypi.org/pypi/eclipse-sumo/{VERSION}/json', timeout=30) as response:
        metadata = json.load(response)
    artifact = next(item for item in metadata['urls'] if 'manylinux2014_x86_64' in item['filename'])
    archive = directory / artifact['filename']
    try:
        urllib.request.urlretrieve(artifact['url'], archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != artifact['digests']['sha256']:
            raise ValueError('checksum paket netconvert ga cocok')
        with zipfile.ZipFile(archive) as package:
            for name in package.namelist():
                if name.startswith(('eclipse_sumo.libs/', 'sumo/data/')) or name == 'sumo/bin/netconvert' or '/licenses/' in name:
                    package.extract(name, directory)
        binary = directory / 'sumo/bin/netconvert'
        binary.chmod(0o755)
        (directory / 'provenance.json').write_text(json.dumps({'package': 'eclipse-sumo', 'version': VERSION, 'url': artifact['url'], 'sha256': artifact['digests']['sha256'], 'runtime_sumo_unchanged': True}, indent=2) + '\n')
        print(binary)
    finally:
        archive.unlink(missing_ok=True)


if __name__ == '__main__':
    install()
