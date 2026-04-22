import os

from django.core.management.base import BaseCommand
from django.db import transaction

from files.models import Accession, Annotation, Assembly, GenomeFile
from files.services.accession_context import classify_file_scope


DEMO_ASSEMBLIES = [
    {
        "name": "v2-polish",
        "description": "Demo assembly copied from the default chain for UI preview.",
        "annotations": [
            {
                "name": "default-annotation",
                "description": "Default annotation for the v2-polish demo assembly.",
                "is_default": True,
            },
            {
                "name": "gene-v2",
                "description": "Alternative gene annotation for hierarchy preview.",
                "is_default": False,
            },
        ],
    },
    {
        "name": "haplotype-demo",
        "description": "Demo assembly used to preview multi-assembly rendering.",
        "annotations": [
            {
                "name": "default-annotation",
                "description": "Default annotation for the haplotype demo assembly.",
                "is_default": True,
            },
            {
                "name": "functional-demo",
                "description": "Functional annotation placeholder for UI preview.",
                "is_default": False,
            },
        ],
    },
]

EXTRA_DEFAULT_ASSEMBLY_ANNOTATIONS = [
    {
        "name": "gene-v2",
        "description": "Alternative gene annotation on the default assembly.",
        "is_default": False,
    },
    {
        "name": "functional-demo",
        "description": "Functional annotation placeholder on the default assembly.",
        "is_default": False,
    },
]


class Command(BaseCommand):
    help = (
        "Seed demo hierarchy data for an accession by cloning existing default "
        "assembly/annotation files into extra assemblies and annotations."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--accession",
            default="IR64",
            help="Accession code to seed demo hierarchy for. Defaults to IR64.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        accession_code = options["accession"].strip()
        accession = Accession.objects.filter(accession=accession_code).first()

        if not accession:
            self.stdout.write(self.style.ERROR(f"Accession not found: {accession_code}"))
            return

        source_assembly = accession.default_assembly or accession.assemblies.order_by("id").first()
        if not source_assembly:
            self.stdout.write(
                self.style.ERROR(
                    f"No assembly found for accession {accession_code}. "
                    "Run stage-one migrations/backfill first."
                )
            )
            return

        source_annotation = (
            source_assembly.default_annotation
            or source_assembly.annotations.order_by("id").first()
        )
        if not source_annotation:
            self.stdout.write(
                self.style.ERROR(
                    f"No annotation found on source assembly {source_assembly.name}."
                )
            )
            return

        source_assembly_files = list(source_assembly.files.order_by("id"))
        source_annotation_files = list(source_annotation.files.order_by("id"))

        if not source_assembly_files:
            self.stdout.write(
                self.style.ERROR(
                    f"No source assembly files found on {accession_code}:{source_assembly.name}."
                )
            )
            return

        if not source_annotation_files:
            self.stdout.write(
                self.style.WARNING(
                    f"No source annotation files found on "
                    f"{accession_code}:{source_assembly.name}:{source_annotation.name}. "
                    "Only assembly-level demo data will be created."
                )
            )

        created_assemblies = 0
        created_annotations = 0
        created_files = 0

        for annotation_spec in EXTRA_DEFAULT_ASSEMBLY_ANNOTATIONS:
            _, annotation_created = Annotation.objects.update_or_create(
                assembly=source_assembly,
                name=annotation_spec["name"],
                defaults={
                    "description": annotation_spec["description"],
                    "is_default": annotation_spec["is_default"],
                },
            )
            if annotation_created:
                created_annotations += 1

            target_annotation = source_assembly.annotations.get(name=annotation_spec["name"])
            created_files += self.clone_files_to_annotation(
                source_files=source_annotation_files,
                accession=accession,
                target_assembly=source_assembly,
                target_annotation=target_annotation,
            )

        for assembly_spec in DEMO_ASSEMBLIES:
            _, assembly_created = Assembly.objects.update_or_create(
                accession=accession,
                name=assembly_spec["name"],
                defaults={
                    "description": assembly_spec["description"],
                    "is_default": False,
                },
            )
            if assembly_created:
                created_assemblies += 1

            target_assembly = accession.assemblies.get(name=assembly_spec["name"])
            created_files += self.clone_files_to_assembly(
                source_files=source_assembly_files,
                accession=accession,
                target_assembly=target_assembly,
            )

            for annotation_spec in assembly_spec["annotations"]:
                _, annotation_created = Annotation.objects.update_or_create(
                    assembly=target_assembly,
                    name=annotation_spec["name"],
                    defaults={
                        "description": annotation_spec["description"],
                        "is_default": annotation_spec["is_default"],
                    },
                )
                if annotation_created:
                    created_annotations += 1

                target_annotation = target_assembly.annotations.get(name=annotation_spec["name"])
                created_files += self.clone_files_to_annotation(
                    source_files=source_annotation_files,
                    accession=accession,
                    target_assembly=target_assembly,
                    target_annotation=target_annotation,
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Demo hierarchy seed completed. "
                f"Assemblies created: {created_assemblies}, "
                f"Annotations created: {created_annotations}, "
                f"Files created: {created_files}"
            )
        )

    def clone_files_to_assembly(self, *, source_files, accession, target_assembly):
        created = 0
        for source_file in source_files:
            scope = classify_file_scope(source_file.category)
            if scope not in {"assembly", "compatibility_assembly"}:
                continue

            defaults = self.build_file_defaults(
                source_file=source_file,
                accession=accession,
                target_assembly=target_assembly,
                target_annotation=None,
            )
            _, was_created = GenomeFile.objects.update_or_create(
                assembly=target_assembly,
                annotation=None,
                category=source_file.category,
                name=defaults["name"],
                defaults=defaults,
            )
            if was_created:
                created += 1
        return created

    def clone_files_to_annotation(
        self, *, source_files, accession, target_assembly, target_annotation
    ):
        created = 0
        for source_file in source_files:
            scope = classify_file_scope(source_file.category)
            if scope != "annotation":
                continue

            defaults = self.build_file_defaults(
                source_file=source_file,
                accession=accession,
                target_assembly=target_assembly,
                target_annotation=target_annotation,
            )
            _, was_created = GenomeFile.objects.update_or_create(
                assembly=target_assembly,
                annotation=target_annotation,
                category=source_file.category,
                name=defaults["name"],
                defaults=defaults,
            )
            if was_created:
                created += 1
        return created

    def build_file_defaults(
        self, *, source_file, accession, target_assembly, target_annotation
    ):
        return {
            "name": self.build_demo_name(
                source_name=source_file.name,
                assembly_name=target_assembly.name,
                annotation_name=target_annotation.name if target_annotation else None,
            ),
            "organism": accession.accession,
            "accession": accession,
            "assembly": target_assembly,
            "annotation": target_annotation,
            "category": source_file.category,
            "file_path": source_file.file_path,
            "file_type": source_file.file_type,
            "description": self.build_demo_description(
                source_file=source_file,
                target_assembly=target_assembly,
                target_annotation=target_annotation,
            ),
            "size": source_file.size,
        }

    def build_demo_name(self, *, source_name, assembly_name, annotation_name=None):
        stem, suffix = self.split_name(source_name)
        parts = [stem, assembly_name]
        if annotation_name:
            parts.append(annotation_name)
        return ".".join(parts) + suffix

    def build_demo_description(self, *, source_file, target_assembly, target_annotation):
        scope_label = f"assembly={target_assembly.name}"
        if target_annotation:
            scope_label += f", annotation={target_annotation.name}"

        source_description = source_file.description or "Cloned from existing IR64 source file."
        return f"{source_description} [demo clone: {scope_label}]"

    def split_name(self, filename):
        if filename.endswith(".tar.gz"):
            return filename[:-7], ".tar.gz"
        stem, ext = os.path.splitext(filename)
        return stem, ext
