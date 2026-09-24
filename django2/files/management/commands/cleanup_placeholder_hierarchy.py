import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from files.models import Annotation, Assembly, FileRelation, GenomeFile


ASSEMBLY_METADATA_FIELDS = (
    "assembly_code",
    "assembly_name",
    "assembly_accession",
    "file_name",
    "display_name",
    "standard_id",
    "bio_project",
    "reference",
)
ANNOTATION_METADATA_FIELDS = (
    "annotation_code",
    "annotation_name",
    "annotation_version",
    "file_name",
    "display_name",
    "standard_id",
    "release_version",
)


class Command(BaseCommand):
    help = (
        "Conservatively remove migration-era default/default-annotation placeholders. "
        "Default mode is dry-run; --apply is required to delete rows."
    )

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", default=None)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--apply", action="store_true")
        parser.add_argument(
            "--accession",
            action="append",
            default=[],
            help="Limit cleanup to one accession. Repeat for multiple accessions.",
        )

    def handle(self, *args, **options):
        if options["apply"] and options["dry_run"]:
            raise CommandError("Use either --apply or --dry-run, not both.")
        dry_run = not options["apply"]
        output_dir = Path(
            options["output_dir"] or Path(settings.BASE_DIR) / "audit_reports"
        ).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        accession_codes = set(options.get("accession") or [])
        assembly_rows, assembly_candidates = self.audit_assemblies(
            accession_codes=accession_codes
        )
        annotation_rows, annotation_candidates = self.audit_annotations(
            parent_assembly_candidate_ids={item.id for item in assembly_candidates},
            accession_codes=accession_codes,
        )
        rows = assembly_rows + annotation_rows

        if not dry_run:
            self.apply_cleanup(assembly_candidates, annotation_candidates)
            for row in rows:
                if row["status"] == "candidate":
                    row["status"] = "deleted"

        timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
        report_path = output_dir / f"cleanup_placeholder_hierarchy_{timestamp}.tsv"
        self.write_report(report_path, rows)
        candidate_count = sum(row["status"] in {"candidate", "deleted"} for row in rows)
        blocked_count = sum(row["status"] == "blocked" for row in rows)
        self.stdout.write(
            f"mode\t{'DRY_RUN' if dry_run else 'APPLY'}\n"
            f"placeholder_total\t{len(rows)}\n"
            f"candidate_or_deleted\t{candidate_count}\n"
            f"blocked\t{blocked_count}\n"
            f"report\t{report_path}"
        )

    def audit_assemblies(self, *, accession_codes=None):
        rows = []
        candidates = []
        queryset = Assembly.objects.filter(name="default").select_related("accession")
        if accession_codes:
            queryset = queryset.filter(accession__accession__in=accession_codes)
        for assembly in queryset.order_by("id"):
            reasons = []
            replacements = assembly.accession.assemblies.exclude(id=assembly.id)
            if not replacements.exists():
                reasons.append("no_real_replacement_assembly")
            if self.has_metadata(assembly, ASSEMBLY_METADATA_FIELDS):
                reasons.append("placeholder_has_metadata")
            if self.has_relations("assembly", assembly.id):
                reasons.append("assembly_has_file_relations")
            if GenomeFile.objects.filter(assembly=assembly).exists():
                reasons.append("assembly_has_legacy_files")

            unsafe_children = []
            for annotation in assembly.annotations.all():
                if annotation.name != "default-annotation":
                    unsafe_children.append(f"real_annotation:{annotation.id}")
                    continue
                if self.has_metadata(annotation, ANNOTATION_METADATA_FIELDS):
                    unsafe_children.append(f"annotation_metadata:{annotation.id}")
                if self.has_relations("annotation", annotation.id):
                    unsafe_children.append(f"annotation_relations:{annotation.id}")
                if GenomeFile.objects.filter(annotation=annotation).exists():
                    unsafe_children.append(f"annotation_legacy_files:{annotation.id}")
            if unsafe_children:
                reasons.append("unsafe_child_annotations=" + ",".join(unsafe_children))

            status = "blocked" if reasons else "candidate"
            if status == "candidate":
                candidates.append(assembly)
            rows.append(
                self.row(
                    status=status,
                    object_type="assembly",
                    object_id=assembly.id,
                    accession=assembly.accession.accession,
                    parent_id="",
                    replacement_ids=",".join(str(item) for item in replacements.values_list("id", flat=True)),
                    reason=";".join(reasons) if reasons else "safe_placeholder_with_replacement",
                )
            )
        return rows, candidates

    def audit_annotations(self, *, parent_assembly_candidate_ids, accession_codes=None):
        rows = []
        candidates = []
        queryset = Annotation.objects.filter(name="default-annotation").select_related(
            "assembly__accession"
        )
        if accession_codes:
            queryset = queryset.filter(assembly__accession__accession__in=accession_codes)
        for annotation in queryset.order_by("id"):
            reasons = []
            replacements = annotation.assembly.annotations.exclude(id=annotation.id)
            parent_will_be_deleted = annotation.assembly_id in parent_assembly_candidate_ids
            if not replacements.exists() and not parent_will_be_deleted:
                reasons.append("no_real_replacement_annotation")
            if self.has_metadata(annotation, ANNOTATION_METADATA_FIELDS):
                reasons.append("placeholder_has_metadata")
            if self.has_relations("annotation", annotation.id):
                reasons.append("annotation_has_file_relations")
            if GenomeFile.objects.filter(annotation=annotation).exists():
                reasons.append("annotation_has_legacy_files")

            status = "blocked" if reasons else "candidate"
            if status == "candidate" and not parent_will_be_deleted:
                candidates.append(annotation)
            reason = ";".join(reasons)
            if not reason:
                reason = (
                    "removed_with_placeholder_assembly"
                    if parent_will_be_deleted
                    else "safe_placeholder_with_replacement"
                )
            rows.append(
                self.row(
                    status=status,
                    object_type="annotation",
                    object_id=annotation.id,
                    accession=annotation.assembly.accession.accession,
                    parent_id=annotation.assembly_id,
                    replacement_ids=",".join(str(item) for item in replacements.values_list("id", flat=True)),
                    reason=reason,
                )
            )
        return rows, candidates

    @transaction.atomic
    def apply_cleanup(self, assembly_candidates, annotation_candidates):
        for annotation in annotation_candidates:
            replacement = annotation.assembly.annotations.exclude(id=annotation.id).order_by(
                "-is_default", "id"
            ).first()
            annotation.is_default = False
            annotation.save(update_fields=["is_default", "updated_at"])
            if replacement and not replacement.is_default:
                replacement.is_default = True
                replacement.save(update_fields=["is_default", "updated_at"])
            annotation.delete()

        for assembly in assembly_candidates:
            replacement = assembly.accession.assemblies.exclude(id=assembly.id).order_by(
                "-is_default", "id"
            ).first()
            assembly.is_default = False
            assembly.save(update_fields=["is_default", "updated_at"])
            if replacement and not replacement.is_default:
                replacement.is_default = True
                replacement.save(update_fields=["is_default", "updated_at"])
            if replacement and not replacement.annotations.filter(is_default=True).exists():
                replacement_annotation = replacement.annotations.order_by("id").first()
                if replacement_annotation:
                    replacement_annotation.is_default = True
                    replacement_annotation.save(update_fields=["is_default", "updated_at"])
            assembly.delete()

    @staticmethod
    def has_metadata(instance, fields):
        return any(getattr(instance, field, None) not in (None, "") for field in fields)

    @staticmethod
    def has_relations(related_type, related_id):
        return FileRelation.objects.filter(
            related_type=related_type,
            related_id=str(related_id),
        ).exists()

    @staticmethod
    def row(**values):
        return values

    @staticmethod
    def write_report(path, rows):
        fields = [
            "status", "object_type", "object_id", "accession", "parent_id",
            "replacement_ids", "reason",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)
