import ast
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

from files.models import (
    Accession,
    Annotation,
    Assembly,
    DataFile,
    FileRelation,
    GenomeFile,
)

GENOMEFILE_WRITE_METHODS = {
    "create",
    "update_or_create",
    "get_or_create",
    "bulk_create",
    "bulk_update",
    "save",
    "update",
    "delete",
}


class DisabledGenomeFileCommandTests(TestCase):
    def test_retired_mutation_commands_fail_closed(self):
        for command_name in ("cleanup_data", "link_genomefiles_to_accessions"):
            with self.subTest(command=command_name), self.assertRaises(CommandError):
                call_command(command_name, stdout=StringIO())


class SeedIr64DemoHierarchyTests(TestCase):
    def setUp(self):
        self.accession = Accession.objects.create(accession="IR64")
        self.assembly = Assembly.objects.create(
            accession=self.accession,
            name="default",
            is_default=True,
        )
        self.annotation = Annotation.objects.create(
            accession=self.accession,
            assembly=self.assembly,
            name="default-annotation",
            is_default=True,
        )
        self.genome_file = DataFile.objects.create(
            file_code="FILE_SEED_GENOME",
            file_name="genome.IR64.fasta",
            file_path="/test/genome.IR64.fasta",
        )
        self.annotation_file = DataFile.objects.create(
            file_code="FILE_SEED_ANNOTATION",
            file_name="annotation.IR64.gff",
            file_path="/test/annotation.IR64.gff",
        )
        FileRelation.objects.create(
            file=self.genome_file,
            related_type="assembly",
            related_id=str(self.assembly.id),
            related_code=self.assembly.name,
            file_role="genome",
            is_primary=True,
        )
        FileRelation.objects.create(
            file=self.annotation_file,
            related_type="annotation",
            related_id=str(self.annotation.id),
            related_code=self.annotation.name,
            file_role="annotation",
            is_primary=True,
        )

    def test_seed_reuses_datafiles_through_relations_without_genomefile_writes(self):
        first_stdout = StringIO()
        second_stdout = StringIO()

        call_command("seed_ir64_demo_hierarchy", stdout=first_stdout)
        call_command("seed_ir64_demo_hierarchy", stdout=second_stdout)

        self.assertEqual(GenomeFile.objects.count(), 0)
        self.assertEqual(DataFile.objects.count(), 2)
        self.assertIn("FileRelations created: 8", first_stdout.getvalue())
        self.assertIn("FileRelations created: 0", second_stdout.getvalue())
        self.assertEqual(
            FileRelation.objects.filter(
                file=self.genome_file,
                related_type="assembly",
            ).count(),
            3,
        )
        self.assertEqual(
            FileRelation.objects.filter(
                file=self.annotation_file,
                related_type="annotation",
            ).count(),
            7,
        )


class GenomeFileStaticWriteBarrierTests(SimpleTestCase):
    def test_non_migration_application_code_has_no_genomefile_writes(self):
        django_root = Path(__file__).resolve().parents[3]
        violations = []
        source_paths = [django_root / "manage.py"]
        for source_dir in ("filemanager", "files", "integrations"):
            source_paths.extend((django_root / source_dir).rglob("*.py"))
        for path in source_paths:
            relative = path.relative_to(django_root)
            if "migrations" in relative.parts or "tests" in relative.parts:
                continue
            if path.name.startswith("test_"):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            visitor = _GenomeFileWriteVisitor()
            visitor.visit(tree)
            violations.extend(
                f"{relative}:{line}:{method}"
                for line, method in visitor.violations
            )

        self.assertEqual(violations, [])


class _GenomeFileWriteVisitor(ast.NodeVisitor):
    def __init__(self):
        self.genomefile_names = set()
        self.violations = []

    @staticmethod
    def _references_manager(node):
        return any(
            isinstance(item, ast.Attribute)
            and item.attr == "objects"
            and isinstance(item.value, ast.Name)
            and item.value.id == "GenomeFile"
            for item in ast.walk(node)
        )

    @classmethod
    def _returns_genomefile(cls, node):
        return cls._references_manager(node) or (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "GenomeFile"
        )

    def visit_Assign(self, node):
        if self._returns_genomefile(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.genomefile_names.add(target.id)
        self.generic_visit(node)

    def visit_For(self, node):
        if self._references_manager(node.iter) and isinstance(node.target, ast.Name):
            self.genomefile_names.add(node.target.id)
        self.generic_visit(node)

    def visit_Call(self, node):
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in GENOMEFILE_WRITE_METHODS
        ):
            receiver = node.func.value
            manager_write = self._references_manager(receiver)
            instance_write = (
                isinstance(receiver, ast.Name)
                and (
                    receiver.id in self.genomefile_names
                    or "genomefile" in receiver.id.lower().replace("_", "")
                )
            )
            if manager_write or instance_write:
                self.violations.append((node.lineno, node.func.attr))
        self.generic_visit(node)
