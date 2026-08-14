import csv
import os
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db.models import Q

from files.models import Accession, Annotation, Assembly, DataFile, FileRelation, Sample, Species
from files.services.genome_list_service import GENOME_FILE_ROLES
from files.services.transcriptome_list_service import TRANSCRIPTOME_ROLE_TOKENS


def _timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _transcriptome_role_query():
    query = Q()
    for token in TRANSCRIPTOME_ROLE_TOKENS:
        query |= Q(file_role__icontains=token)
    return query


def _write_key_value_report(path, stats):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        for key, value in stats.items():
            handle.write(f"{key}: {value}\n")


def _write_detail_report(path, rows):
    fieldnames = ["check_type", "object_type", "object_id", "code", "issue", "suggested_action"]
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


class Command(BaseCommand):
    help = "Audit whether Genome and Transcriptome list pages have enough new-structure data."

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", default=".")
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **options):
        output_dir = options["output_dir"]
        limit = options["limit"]
        os.makedirs(output_dir, exist_ok=True)

        genome_relations = FileRelation.objects.filter(file_role__in=GENOME_FILE_ROLES)
        accession_genome_relations = genome_relations.filter(related_type="accession")
        assembly_genome_relations = genome_relations.filter(related_type="assembly")
        transcriptome_relations = FileRelation.objects.filter(_transcriptome_role_query())

        accessions_with_genome = self._accessions_with_relations(accession_genome_relations, limit=limit)
        accessions_missing_assembly = [
            accession
            for accession in accessions_with_genome
            if not accession.assemblies.exists()
        ]
        accessions_without_species = list(
            Accession.objects.filter(species__isnull=True).order_by("accession")[:limit]
            if limit
            else Accession.objects.filter(species__isnull=True).order_by("accession")
        )

        invalid_accession_relation_count, invalid_accession_rows = self._invalid_relation_rows(
            accession_genome_relations,
            Accession,
            "accession",
            limit=limit,
        )
        invalid_assembly_relation_count, invalid_assembly_rows = self._invalid_relation_rows(
            assembly_genome_relations,
            Assembly,
            "assembly",
            limit=limit,
        )

        detail_rows = []
        for accession in accessions_missing_assembly[:limit]:
            detail_rows.append(
                {
                    "check_type": "genome_readiness",
                    "object_type": "accession",
                    "object_id": accession.id,
                    "code": accession.accession,
                    "issue": "has accession-level genome FileRelation but no Assembly",
                    "suggested_action": "run backfill_assembly_from_genome_relations",
                }
            )
        for accession in accessions_without_species:
            detail_rows.append(
                {
                    "check_type": "metadata_readiness",
                    "object_type": "accession",
                    "object_id": accession.id,
                    "code": accession.accession,
                    "issue": "accession has no species",
                    "suggested_action": "import or backfill accession species metadata",
                }
            )
        detail_rows.extend(invalid_accession_rows)
        detail_rows.extend(invalid_assembly_rows)

        stats = {
            "species_count": Species.objects.count(),
            "accession_count": Accession.objects.count(),
            "accession_without_species_count": Accession.objects.filter(species__isnull=True).count(),
            "assembly_count": Assembly.objects.count(),
            "annotation_count": Annotation.objects.count(),
            "sample_count": Sample.objects.count(),
            "datafile_count": DataFile.objects.count(),
            "filerelation_count": FileRelation.objects.count(),
            "accession_genome_relation_count": accession_genome_relations.count(),
            "assembly_genome_relation_count": assembly_genome_relations.count(),
            "accessions_with_genome_relation_count": len(accessions_with_genome),
            "accessions_with_genome_relation_without_assembly_count": len(accessions_missing_assembly),
            "invalid_accession_genome_relation_count": invalid_accession_relation_count,
            "invalid_assembly_genome_relation_count": invalid_assembly_relation_count,
            "transcriptome_relation_count": transcriptome_relations.count(),
            "transcriptome_sample_relation_count": transcriptome_relations.filter(related_type="sample").count(),
            "transcriptome_accession_relation_count": transcriptome_relations.filter(related_type="accession").count(),
            "transcriptome_assembly_relation_count": transcriptome_relations.filter(related_type="assembly").count(),
            "status": "PASS" if not detail_rows else "WARN",
        }

        stamp = _timestamp()
        txt_path = os.path.join(output_dir, f"genome_transcriptome_readiness_{stamp}.txt")
        tsv_path = os.path.join(output_dir, f"genome_transcriptome_readiness_{stamp}.tsv")
        _write_key_value_report(txt_path, stats)
        _write_detail_report(tsv_path, detail_rows)

        for key, value in stats.items():
            self.stdout.write(f"{key}={value}")
        self.stdout.write(f"report={txt_path}")
        self.stdout.write(f"details={tsv_path}")

    def _accessions_with_relations(self, relations, limit=None):
        ids = []
        for related_id in relations.values_list("related_id", flat=True).distinct():
            if str(related_id).isdigit():
                ids.append(int(related_id))
        queryset = Accession.objects.filter(id__in=ids).order_by("accession")
        if limit:
            queryset = queryset[:limit]
        return list(queryset)

    def _invalid_relation_rows(self, relations, model, object_type, limit=None):
        valid_ids = set(model.objects.values_list("id", flat=True))
        rows = []
        invalid_count = 0
        queryset = relations.order_by("id")
        for relation in queryset:
            related_id = str(relation.related_id or "")
            is_valid = related_id.isdigit() and int(related_id) in valid_ids
            if is_valid:
                continue
            invalid_count += 1
            if limit and len(rows) >= limit:
                continue
            rows.append(
                {
                    "check_type": "relation_integrity",
                    "object_type": "file_relation",
                    "object_id": relation.id,
                    "code": relation.related_code or related_id,
                    "issue": f"{object_type} relation points to missing object",
                    "suggested_action": "fix related_id or remove invalid FileRelation",
                }
            )
        return invalid_count, rows
