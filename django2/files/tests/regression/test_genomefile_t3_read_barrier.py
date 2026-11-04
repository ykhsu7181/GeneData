import ast
from pathlib import Path

from django.test import SimpleTestCase


FILES_PACKAGE = Path(__file__).resolve().parents[2]
ALLOWED_FILES = {
    FILES_PACKAGE / 'models.py',
    FILES_PACKAGE / 'archive_views.py',
    FILES_PACKAGE / 'urls.py',
}


def _active_python_files():
    for path in FILES_PACKAGE.rglob('*.py'):
        if path in ALLOWED_FILES:
            continue
        if {'migrations', 'management', 'tests'} & set(path.parts):
            continue
        if path.name.startswith('test_'):
            continue
        yield path


class GenomeFileT3ReadBarrierTests(SimpleTestCase):
    def test_active_code_does_not_import_or_reference_genomefile_model(self):
        violations = []
        for path in _active_python_files():
            tree = ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id == 'GenomeFile':
                    violations.append(f'{path.relative_to(FILES_PACKAGE)}:{node.lineno}')
                elif isinstance(node, ast.ImportFrom):
                    if any(alias.name == 'GenomeFile' for alias in node.names):
                        violations.append(f'{path.relative_to(FILES_PACKAGE)}:{node.lineno}')
        self.assertEqual(violations, [])

    def test_active_code_does_not_use_legacy_files_reverse_relation(self):
        violations = []
        for path in _active_python_files():
            tree = ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and node.attr == 'files':
                    violations.append(f'{path.relative_to(FILES_PACKAGE)}:{node.lineno}')
        self.assertEqual(violations, [])

    def test_active_code_has_no_genomefile_fallback_markers(self):
        violations = []
        for path in _active_python_files():
            source = path.read_text(encoding='utf-8-sig')
            for marker in ('legacy_genomefile', 'organism_fallback'):
                if marker in source:
                    violations.append(f'{path.relative_to(FILES_PACKAGE)}:{marker}')
        self.assertEqual(violations, [])
