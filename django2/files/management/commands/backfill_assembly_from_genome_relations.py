import csv
import json
import os
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction

from files.models import Accession, Assembly, FileRelation
from files.services.genome_list_service import GENOME_FILE_ROLES


def _timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _write_key_value_report(path, stats):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        for key, value in stats.items():
            handle.write(f"{key}: {value}\n")


def _write_unmapped_report(path, rows):
    fieldnames = ["file_relation_id", "related_id", "related_code", "file_role", "reason"]
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


class Command(BaseCommand):
    help = "Create Assembly rows and assembly-level FileRelation rows from accession-level genome files."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=None, help="Limit number of accessions processed.")
        parser.add_argument("--output-dir", default=".")
        parser.add_argument("--assembly-name", default="default")
        parser.add_argument("--assembly-level", default="")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]
        output_dir = options["output_dir"]
        assembly_name = options["assembly_name"]
        assembly_level = (options["assembly_level"] or "").strip()
        os.makedirs(output_dir, exist_ok=True)

        stats = {
            "dry_run": dry_run,
            "scanned_accession_count": 0,
            "scanned_relation_count": 0,
            "created_assembly_count": 0,
            "reused_assembly_count": 0,
            "updated_assembly_count": 0,
            "created_filerelation_count": 0,
            "reused_filerelation_count": 0,
            "unmapped_count": 0,
        }
        unmapped = []

        for relation in self._invalid_accession_genome_relations():
            unmapped.append(
                {
                    "file_relation_id": relation.id,
                    "related_id": relation.related_id,
                    "related_code": relation.related_code or "",
                    "file_role": relation.file_role,
                    "reason": "accession related_id is not numeric",
                }
            )

        accession_ids = self._accession_ids(limit=limit)
        for accession_id in accession_ids:
            accession = Accession.objects.filter(id=accession_id).first()
            if not accession:
                unmapped.append(
                    {
                        "file_relation_id": "",
                        "related_id": accession_id,
                        "related_code": "",
                        "file_role": "",
                        "reason": "accession not found",
                    }
                )
                continue

            relations = list(self._accession_genome_relations(accession.id))
            stats["scanned_accession_count"] += 1
            stats["scanned_relation_count"] += len(relations)
            if not relations:
                continue

            assembly, assembly_result = self._get_or_create_assembly(
                accession,
                assembly_name=assembly_name,
                assembly_level=assembly_level,
                dry_run=dry_run,
            )
            stats[assembly_result] += 1

            for relation in relations:
                if dry_run:
                    exists = False
                    if assembly:
                        exists = FileRelation.objects.filter(
                            file=relation.file,
                            related_type="assembly",
                            related_id=str(assembly.id),
                            file_role=relation.file_role,
                        ).exists()
                    if exists:
                        stats["reused_filerelation_count"] += 1
                    else:
                        stats["created_filerelation_count"] += 1
                    continue

                created = self._create_or_reuse_assembly_relation(relation, assembly)
                if created:
                    stats["created_filerelation_count"] += 1
                else:
                    stats["reused_filerelation_count"] += 1

        stats["unmapped_count"] = len(unmapped)
        stamp = _timestamp()
        log_path = os.path.join(output_dir, f"backfill_assembly_from_genome_relations_log_{stamp}.txt")
        unmapped_path = os.path.join(output_dir, f"backfill_assembly_from_genome_relations_unmapped_{stamp}.tsv")
        _write_key_value_report(log_path, stats)
        _write_unmapped_report(unmapped_path, unmapped)

        for key, value in stats.items():
            self.stdout.write(f"{key}={value}")
        self.stdout.write(f"log={log_path}")
        self.stdout.write(f"unmapped={unmapped_path}")

    def _accession_ids(self, limit=None):
        ids = []
        seen = set()
        queryset = (
            FileRelation.objects.filter(related_type="accession", file_role__in=GENOME_FILE_ROLES)
            .order_by("related_id")
            .values_list("related_id", flat=True)
        )
        for related_id in queryset:
            if not str(related_id).isdigit():
                continue
            accession_id = int(related_id)
            if accession_id in seen:
                continue
            seen.add(accession_id)
            ids.append(accession_id)
            if limit and len(ids) >= limit:
                break
        return ids

    def _accession_genome_relations(self, accession_id):
        return (
            FileRelation.objects.select_related("file")
            .filter(
                related_type="accession",
                related_id=str(accession_id),
                file_role__in=GENOME_FILE_ROLES,
            )
            .order_by("-is_primary", "file_role", "id")
        )

    def _invalid_accession_genome_relations(self):
        invalid = []
        for relation in FileRelation.objects.filter(
            related_type="accession",
            file_role__in=GENOME_FILE_ROLES,
        ).order_by("id"):
            if not str(relation.related_id or "").isdigit():
                invalid.append(relation)
        return invalid

    def _get_or_create_assembly(self, accession, *, assembly_name, assembly_level, dry_run):
        assembly = accession.default_assembly or accession.assemblies.filter(name=assembly_name).first()
        if assembly:
            if not assembly.is_default and not accession.assemblies.filter(is_default=True).exists():
                if not dry_run:
                    assembly.is_default = True
                    assembly.save(update_fields=["is_default", "updated_at"])
                return assembly, "updated_assembly_count"
            return assembly, "reused_assembly_count"

        display_name = f"{accession.accession} default assembly"
        description = {}
        if assembly_level:
            description["assembly_level"] = assembly_level

        if dry_run:
            return None, "created_assembly_count"

        try:
            with transaction.atomic():
                assembly = Assembly.objects.create(
                    accession=accession,
                    name=assembly_name,
                    display_name=display_name,
                    description=json.dumps(description, ensure_ascii=False) if description else None,
                    is_default=not accession.assemblies.filter(is_default=True).exists(),
                )
        except IntegrityError:
            assembly = accession.default_assembly or accession.assemblies.filter(name=assembly_name).first()
            return assembly, "reused_assembly_count"
        return assembly, "created_assembly_count"

    def _create_or_reuse_assembly_relation(self, relation, assembly):
        _, created = FileRelation.objects.get_or_create(
            file=relation.file,
            related_type="assembly",
            related_id=str(assembly.id),
            file_role=relation.file_role,
            defaults={
                "related_code": assembly.display_name or assembly.name,
                "is_primary": relation.is_primary,
                "description": "Backfilled from accession-level genome FileRelation.",
            },
        )
        return created
