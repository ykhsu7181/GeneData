import uuid
from unittest import skipIf

from django.db import connection
from django.test import TestCase

from files.models import Accession, Annotation, Assembly
from files.services.accession_context import (
    AmbiguousContextError,
    resolve_annotation_context,
    resolve_assembly_context,
)


class AccessionContextResolutionTests(TestCase):
    def setUp(self):
        suffix = uuid.uuid4().hex[:8].upper()
        self.accession = Accession.objects.create(accession=f"CTX_{suffix}")

    def create_assembly(self, name, is_default=False):
        return Assembly.objects.create(
            accession=self.accession,
            name=name,
            is_default=is_default,
        )

    def test_unique_assembly_is_selected_without_default(self):
        assembly = self.create_assembly("only")

        accession, resolved = resolve_assembly_context(accession=self.accession.accession)

        self.assertEqual(accession, self.accession)
        self.assertEqual(resolved, assembly)

    def test_single_default_wins_when_multiple_assemblies_exist(self):
        self.create_assembly("secondary")
        default = self.create_assembly("primary", is_default=True)

        _, resolved = resolve_assembly_context(accession=self.accession.accession)

        self.assertEqual(resolved, default)

    def test_multiple_assemblies_without_default_are_ambiguous(self):
        self.create_assembly("one")
        self.create_assembly("two")

        with self.assertRaises(AmbiguousContextError) as caught:
            resolve_assembly_context(accession=self.accession.accession)

        self.assertEqual(caught.exception.related_type, "assembly")

    @skipIf(connection.features.supports_partial_indexes, "database enforces one default assembly")
    def test_multiple_default_assemblies_are_ambiguous_on_mysql(self):
        self.create_assembly("one", is_default=True)
        self.create_assembly("two", is_default=True)

        with self.assertRaises(AmbiguousContextError):
            resolve_assembly_context(accession=self.accession.accession)

    def test_invalid_explicit_assembly_does_not_fall_back(self):
        self.create_assembly("only")

        self.assertEqual(
            resolve_assembly_context(assembly_id=999999, accession=self.accession.accession),
            (None, None),
        )

    def test_annotation_uses_default_then_rejects_ambiguous_context(self):
        assembly = self.create_assembly("primary", is_default=True)
        default = Annotation.objects.create(
            assembly=assembly,
            accession=self.accession,
            name="primary",
            is_default=True,
        )
        Annotation.objects.create(
            assembly=assembly,
            accession=self.accession,
            name="secondary",
        )

        _, _, resolved = resolve_annotation_context(assembly_id=assembly.id)
        self.assertEqual(resolved, default)

        default.is_default = False
        default.save(update_fields=["is_default"])
        with self.assertRaises(AmbiguousContextError) as caught:
            resolve_annotation_context(assembly_id=assembly.id)
        self.assertEqual(caught.exception.related_type, "annotation")

    @skipIf(connection.features.supports_partial_indexes, "database enforces one default annotation")
    def test_multiple_default_annotations_are_ambiguous_on_mysql(self):
        assembly = self.create_assembly("primary", is_default=True)
        for name in ("one", "two"):
            Annotation.objects.create(
                assembly=assembly,
                accession=self.accession,
                name=name,
                is_default=True,
            )

        with self.assertRaises(AmbiguousContextError):
            resolve_annotation_context(assembly_id=assembly.id)

    def test_invalid_explicit_annotation_does_not_fall_back(self):
        assembly = self.create_assembly("primary", is_default=True)
        Annotation.objects.create(
            assembly=assembly,
            accession=self.accession,
            name="only",
        )

        self.assertEqual(
            resolve_annotation_context(annotation_id=999999, assembly_id=assembly.id),
            (None, None, None),
        )
