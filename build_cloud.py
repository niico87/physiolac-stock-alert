"""Génère la version statique du dashboard pour GitHub Pages."""
from pathlib import Path
root=Path(__file__).resolve().parent
source=(root/'static'/'index.html').read_text(encoding='utf-8')
source=source.replace('<html lang="fr">', '<html lang="fr" data-cloud="true">', 1)
(root/'docs').mkdir(exist_ok=True)
(root/'docs'/'index.html').write_text(source, encoding='utf-8')
print('docs/index.html généré')
