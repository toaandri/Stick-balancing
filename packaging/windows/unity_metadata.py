"""Create deterministic .meta identities for new hand-authored Unity source assets."""
from pathlib import Path
import uuid


def main():
    root = Path(__file__).resolve().parents[2] / 'unity/Assets'
    for path in root.rglob('*'):
        if path.suffix == '.meta':
            continue
        destination = Path(str(path) + '.meta')
        if destination.exists():
            continue
        guid = uuid.uuid5(uuid.NAMESPACE_URL, 'stick-balancing/' + path.relative_to(root.parent).as_posix()).hex
        importer = 'DefaultImporter' if path.is_dir() else ('MonoImporter' if path.suffix == '.cs' else 'AssemblyDefinitionImporter')
        text = f'fileFormatVersion: 2\nguid: {guid}\n'
        if path.is_dir():
            text += 'folderAsset: yes\n'
        text += f'{importer}:\n  externalObjects: {{}}\n'
        if path.suffix == '.cs':
            text += '  serializedVersion: 2\n  defaultReferences: []\n  executionOrder: 0\n  icon: {instanceID: 0}\n'
        text += '  userData:\n  assetBundleName:\n  assetBundleVariant:\n'
        destination.write_text(text, encoding='utf-8')


if __name__ == '__main__':
    main()
