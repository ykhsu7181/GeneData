import ast
from pathlib import Path

from django.test import SimpleTestCase


FILES_PACKAGE = Path(__file__).resolve().parents[2]
RETIRED_COMMANDS = {
    'audit_file_migration',
    'audit_legacy_fallback',
    'backfill_genomefile_to_datafile',
    'cleanup_data',
    'compare_accession_files',
    'compare_annotation_files',
    'compare_overview_files',
    'generate_legacy_fix_todo',
    'link_genomefiles_to_accessions',
    'report_genomefile_archive_status',
    'report_legacy_usage',
}


def _active_python_files():
    for path in FILES_PACKAGE.rglob('*.py'):
        if {'migrations', 'tests'} & set(path.parts):
            continue
        if path.name.startswith('test_'):
            continue
        yield path


class GenomeFileT3ReadBarrierTests(SimpleTestCase):
    def test_genomefile_model_definition_is_removed(self):
        tree = ast.parse(
            (FILES_PACKAGE / 'models.py').read_text(encoding='utf-8-sig'),
            filename='models.py',
        )
        class_names = {
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        }
        self.assertNotIn('GenomeFile', class_names)

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

    def test_genomefile_specific_commands_are_removed(self):
        command_dir = FILES_PACKAGE / 'management' / 'commands'
        remaining = {
            command_name
            for command_name in RETIRED_COMMANDS
            if (command_dir / f'{command_name}.py').exists()
        }
        self.assertEqual(remaining, set())
