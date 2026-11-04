from django.core.management.base import BaseCommand
from django.db import transaction

from files.models import Accession, Annotation, Assembly, FileRelation
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

        source_assembly_files = list(
            FileRelation.objects.filter(
                related_type="assembly",
                related_id=str(source_assembly.id),
            ).select_related("file").order_by("id")
        )
        source_annotation_files = list(
            FileRelation.objects.filter(
                related_type="annotation",
                related_id=str(source_annotation.id),
            ).select_related("file").order_by("id")
        )

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
        created_relations = 0

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
            created_relations += self.clone_files_to_annotation(
                source_files=source_annotation_files,
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
            created_relations += self.clone_files_to_assembly(
                source_files=source_assembly_files,
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
                created_relations += self.clone_files_to_annotation(
                    source_files=source_annotation_files,
                    target_annotation=target_annotation,
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Demo hierarchy seed completed. "
                f"Assemblies created: {created_assemblies}, "
                f"Annotations created: {created_annotations}, "
                f"FileRelations created: {created_relations}"
            )
        )

    def clone_files_to_assembly(self, *, source_files, target_assembly):
        created = 0
        for source_relation in source_files:
            scope = classify_file_scope(source_relation.file_role)
            if scope not in {"assembly", "compatibility_assembly"}:
                continue

            _, was_created = FileRelation.objects.get_or_create(
                file=source_relation.file,
                related_type="assembly",
                related_id=str(target_assembly.id),
                file_role=source_relation.file_role,
                defaults={
                    "related_code": target_assembly.assembly_code or target_assembly.name,
                    "is_primary": source_relation.is_primary,
                    "description": source_relation.description,
                },
            )
            if was_created:
                created += 1
        return created

    def clone_files_to_annotation(self, *, source_files, target_annotation):
        created = 0
        for source_relation in source_files:
            scope = classify_file_scope(source_relation.file_role)
            if scope != "annotation":
                continue

            _, was_created = FileRelation.objects.get_or_create(
                file=source_relation.file,
                related_type="annotation",
                related_id=str(target_annotation.id),
                file_role=source_relation.file_role,
                defaults={
                    "related_code": target_annotation.annotation_code
                    or target_annotation.name,
                    "is_primary": source_relation.is_primary,
                    "description": source_relation.description,
                },
            )
            if was_created:
                created += 1
        return created
