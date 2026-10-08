import csv
from collections import defaultdict
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from files.models import Assembly, FileRelation, GenomeFile


PLACEHOLDER_NAME = "default"
GENOME_ROLES = {"genome", "genome_fasta"}
COPY_IF_BLANK_FIELDS = (
    "assembly_accession",
    "species_code",
    "assembly_level",
    "biosample_accession",
    "assembly_type",
    "assembly_method",
    "sequencing_technology",
    "genome_size",
    "chromosome_count",
    "contig_count",
    "n50",
    "gc_content",
    "at_content",
    "n_count",
    "n_percentage",
    "sequence_count",
    "sequence_md5",
    "gap_count",
    "source_database",
    "external_project",
    "file_name",
    "file_type",
    "standard_id",
    "bio_project",
    "reference",
    "description",
)


def _basename(value):
    return PurePosixPath((value or "").replace("\\", "/")).name


def _is_blank(value):
    return value is None or value == ""


class Command(BaseCommand):
    help = (
        "Migrate legacy default Assembly dependencies to the real Assembly selected "
        "by genome.<Accession>.fasta in the production manifests, then delete the placeholder."
    )

    def add_arguments(self, parser):
        parser.add_argument("--assembly-file", required=True)
        parser.add_argument("--file-manifest", required=True)
        parser.add_argument("--output-dir", default=None)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--apply", action="store_true")
        parser.add_argument(
            "--accession",
            action="append",
            default=[],
            help="Limit migration to one Accession. Repeat for multiple Accessions.",
        )

    def handle(self, *args, **options):
        if options["apply"] and options["dry_run"]:
            raise CommandError("Use either --apply or --dry-run, not both.")
        dry_run = not options["apply"]
        assembly_path = self._input_path(options["assembly_file"], "assembly-file")
        file_manifest_path = self._input_path(options["file_manifest"], "file-manifest")
        output_dir = Path(
            options["output_dir"] or Path(settings.BASE_DIR) / "audit_reports"
        ).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        mapping = self._manifest_mapping(assembly_path, file_manifest_path)
        accessions = set(options.get("accession") or [])
        placeholders = Assembly.objects.filter(
            name=PLACEHOLDER_NAME,
        ).filter(
            Q(assembly_code__isnull=True) | Q(assembly_code="")
        ).select_related("accession")
        if accessions:
            placeholders = placeholders.filter(accession__accession__in=accessions)

        plans = [self._plan(item, mapping) for item in placeholders.order_by("id")]
        timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S_%f")
        report_path = output_dir / f"migrate_placeholder_hierarchy_{timestamp}.tsv"
        blocked = sum(item["status"] == "blocked" for item in plans)
        if not dry_run and blocked:
            self._write_report(report_path, plans)
            raise CommandError(
                f"Refusing APPLY because {blocked} placeholder rows are blocked. "
                f"No database changes were made. Report: {report_path}"
            )

        if not dry_run:
            with transaction.atomic():
                for plan in plans:
                    if plan["status"] == "ready":
                        self._apply_plan(plan)
                        plan["status"] = "migrated"

        self._write_report(report_path, plans)
        migrated_or_ready = sum(item["status"] in {"ready", "migrated"} for item in plans)
        self.stdout.write(
            f"mode\t{'DRY_RUN' if dry_run else 'APPLY'}\n"
            f"placeholder_total\t{len(plans)}\n"
            f"ready_or_migrated\t{migrated_or_ready}\n"
            f"blocked\t{blocked}\n"
            f"relations_to_move\t{sum(item['relations_to_move'] for item in plans)}\n"
            f"relations_to_reuse\t{sum(item['relations_to_reuse'] for item in plans)}\n"
            f"legacy_files_to_move\t{sum(item['legacy_files_to_move'] for item in plans)}\n"
            f"report\t{report_path}"
        )

    @staticmethod
    def _input_path(raw_path, option_name):
        path = Path(raw_path).expanduser().resolve()
        if not path.is_file():
            raise CommandError(f"--{option_name} does not exist or is not a file: {path}")
        return path

    @staticmethod
    def _read_tsv(path, required_fields):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            missing = required_fields - set(reader.fieldnames or [])
            if missing:
                raise CommandError(
                    f"Manifest {path} is missing columns: {', '.join(sorted(missing))}"
                )
            return list(reader)

    def _manifest_mapping(self, assembly_path, file_manifest_path):
        assembly_rows = self._read_tsv(
            assembly_path,
            {"assembly_code", "accession", "file_name"},
        )
        file_rows = self._read_tsv(
            file_manifest_path,
            {"file_path", "file_role", "accession", "assembly_code"},
        )
        assembly_candidates = defaultdict(set)
        file_candidates = defaultdict(set)

        for row in assembly_rows:
            accession = (row.get("accession") or "").strip()
            assembly_code = (row.get("assembly_code") or "").strip()
            expected = f"genome.{accession}.fasta"
            if accession and assembly_code and _basename(row.get("file_name")) == expected:
                assembly_candidates[accession].add(assembly_code)

        for row in file_rows:
            accession = (row.get("accession") or "").strip()
            assembly_code = (row.get("assembly_code") or "").strip()
            role = (row.get("file_role") or "").strip().lower()
            expected = f"genome.{accession}.fasta"
            if (
                accession
                and assembly_code
                and role in GENOME_ROLES
                and _basename(row.get("file_path")) == expected
            ):
                file_candidates[accession].add(assembly_code)

        mapping = {}
        for accession in set(assembly_candidates) | set(file_candidates):
            # A file manifest is the strongest binding evidence. The assembly
            # manifest remains the deterministic fallback when the physical
            # genome file is intentionally absent.
            mapping[accession] = file_candidates[accession] or assembly_candidates[accession]
        return mapping

    def _plan(self, placeholder, mapping):
        accession = placeholder.accession.accession
        expected_file = f"genome.{accession}.fasta"
        codes = sorted(mapping.get(accession, set()))
        reasons = []
        target = None
        if not codes:
            reasons.append("no_exact_genome_manifest_mapping")
        elif len(codes) > 1:
            reasons.append("ambiguous_genome_manifest_mapping=" + ",".join(codes))
        else:
            target = Assembly.objects.filter(
                accession_id=placeholder.accession_id,
                assembly_code=codes[0],
            ).exclude(id=placeholder.id).first()
            if target is None:
                reasons.append(f"target_assembly_not_imported={codes[0]}")

        annotation_count = placeholder.annotations.count()
        if annotation_count:
            reasons.append(f"placeholder_has_annotations={annotation_count}")
        if target:
            conflicting_default = Assembly.objects.filter(
                accession_id=placeholder.accession_id,
                is_default=True,
            ).exclude(id__in=(placeholder.id, target.id)).first()
            if conflicting_default:
                reasons.append(f"conflicting_default_assembly={conflicting_default.id}")

        relations = list(
            FileRelation.objects.filter(
                related_type="assembly",
                related_id=str(placeholder.id),
            ).select_related("file")
        )
        relations_to_reuse = 0
        if target:
            relations_to_reuse = sum(
                FileRelation.objects.filter(
                    file_id=relation.file_id,
                    related_type="assembly",
                    related_id=str(target.id),
                    file_role=relation.file_role,
                ).exists()
                for relation in relations
            )
        legacy_files = GenomeFile.objects.filter(assembly_id=placeholder.id).count()

        return {
            "status": "blocked" if reasons else "ready",
            "accession": accession,
            "expected_genome_file": expected_file,
            "placeholder_id": placeholder.id,
            "target_id": target.id if target else "",
            "target_assembly_code": target.assembly_code if target else (codes[0] if len(codes) == 1 else ""),
            "relations_to_move": len(relations) - relations_to_reuse,
            "relations_to_reuse": relations_to_reuse,
            "legacy_files_to_move": legacy_files,
            "metadata_fields_to_copy": ",".join(
                field
                for field in COPY_IF_BLANK_FIELDS
                if target
                and not _is_blank(getattr(placeholder, field))
                and _is_blank(getattr(target, field))
            ),
            "reason": ";".join(reasons),
        }

    @staticmethod
    def _apply_plan(plan):
        placeholder = Assembly.objects.select_for_update().get(id=plan["placeholder_id"])
        target = Assembly.objects.select_for_update().get(id=plan["target_id"])

        for relation in FileRelation.objects.select_for_update().filter(
            related_type="assembly",
            related_id=str(placeholder.id),
        ):
            duplicate = FileRelation.objects.filter(
                file_id=relation.file_id,
                related_type="assembly",
                related_id=str(target.id),
                file_role=relation.file_role,
            ).exclude(id=relation.id).first()
            if duplicate:
                relation.delete()
            else:
                relation.related_id = str(target.id)
                relation.related_code = target.assembly_code
                relation.save(update_fields=["related_id", "related_code", "updated_at"])

        GenomeFile.objects.filter(assembly_id=placeholder.id).update(assembly_id=target.id)

        copied_fields = []
        for field in COPY_IF_BLANK_FIELDS:
            old_value = getattr(placeholder, field)
            if not _is_blank(old_value) and _is_blank(getattr(target, field)):
                setattr(target, field, old_value)
                copied_fields.append(field)

        if placeholder.is_default:
            placeholder.is_default = False
            placeholder.save(update_fields=["is_default", "updated_at"])
        if not target.is_default:
            target.is_default = True
            copied_fields.append("is_default")
        if copied_fields:
            target.save(update_fields=sorted(set(copied_fields + ["updated_at"])))
        placeholder.delete()

    @staticmethod
    def _write_report(path, plans):
        fields = (
            "status",
            "accession",
            "expected_genome_file",
            "placeholder_id",
            "target_id",
            "target_assembly_code",
            "relations_to_move",
            "relations_to_reuse",
            "legacy_files_to_move",
            "metadata_fields_to_copy",
            "reason",
        )
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
            writer.writeheader()
            writer.writerows(plans)
