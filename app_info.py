"""Local application version and release notes, independent of user settings."""
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent


def application_info():
    try:
        info = json.loads((ROOT / 'version.json').read_text(encoding='utf-8-sig'))
        version = str(info.get('version', '')).removeprefix('v')
        if not re.fullmatch(r'\d+(?:\.\d+){1,3}', version):
            raise ValueError('Invalid application version')
        return {'name': str(info.get('name') or '鲸伴'), 'version': version}
    except (OSError, ValueError, TypeError, AttributeError):
        return {'name': '鲸伴', 'version': '1.73'}


def release_history():
    try:
        text = (ROOT / 'CHANGELOG.txt').read_text(encoding='utf-8-sig')
    except OSError:
        return []
    headings = list(re.finditer(r'^\s*v(\d+(?:\.\d+){1,3})\s*$', text, re.M | re.I))
    records = [{'version': heading.group(1),
                'content': text[heading.end():headings[index + 1].start() if index + 1 < len(headings) else len(text)].strip()}
               for index, heading in enumerate(headings)]
    return sorted(records, key=lambda record: tuple(int(part) for part in record['version'].split('.')), reverse=True)
