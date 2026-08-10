import csv
import json
import os
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from files.models import Accession, DataFile, FileRelation, Sample, Species
from files.services.file_write_service import make_next_file_code


REQUIRED_COLUMNS = {"file_path", "file_role"}


def _clean(value):
    return (value or "").strip()


def _normalize_manifest_path(file_path):
    value = _clean(file_path).replace("\\", "/")
    while "//" in value:
        value = value.replace("//", "/")
    return value


def _file_name_from_path(file_path):
    return os.path.basename(file_path.rstrip("/")) or file_path


def _int_or_none(value):
    value = _clean(value)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _safe_json(raw):
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _merge_raw_data_description(existing_description, raw_data_description):
    payload = _safe_json(existing_description)
    payload["raw_data"] = raw_data_description["raw_data"]
    return json.dumps(payload, ensure_ascii=False)


class Command(BaseCommand):
    help = "Import raw sequencing data manifest into DataFile and FileRelation."

    def add_arguments(self, parser):
        parser.add_argument("--input", dest="input_path", required=True)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **options):
        input_path = options["input_path"]
        dry_run = options["dry_run"]
        limit = options["limit"]
        if not os.path.exists(input_path):
            raise CommandError(f"Input file does not exist: {input_path}")

        created_datafile = 0
        reused_datafile = 0
        created_relation = 0
        reused_relation = 0
        unmapped = []
        scanned = 0

        with open(input_path, newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            missing_columns = REQUIRED_COLUMNS - set(reader.fieldnames or [])
            if missing_columns:
                raise CommandError(f"Missing required columns: {', '.join(sorted(missing_columns))}")

            for row in reader:
                if limit is not None and scanned >= limit:
                    break
                scanned += 1
                result = self.import_row(row, dry_run=dry_run)
                created_datafile += int(result["created_datafile"])
                reused_datafile += int(result["reused_datafile"])
                created_relation += result["created_relation"]
                reused_relation += result["reused_relation"]
                unmapped.extend(result["unmapped"])

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = f"import_raw_data_log_{timestamp}.txt"
        unmapped_path = f"import_raw_data_unmapped_{timestamp}.tsv"
        self.write_reports(
            log_path,
            unmapped_path,
            {
                "dry_run": dry_run,
                "scanned_count": scanned,
                "created_datafile_count": created_datafile,
                "reused_datafile_count": reused_datafile,
                "created_filerelation_count": created_relation,
                "reused_filerelation_count": reused_relation,
                "unmapped_count": len(unmapped),
            },
            unmapped,
        )
        self.stdout.write(f"scanned_count={scanned}")
        self.stdout.write(f"created_datafile_count={created_datafile}")
        self.stdout.write(f"created_filerelation_count={created_relation}")
        self.stdout.write(f"log={log_path}")
        self.stdout.write(f"unmapped={unmapped_path}")

    def import_row(self, row, dry_run=False):
        file_path = _normalize_manifest_path(row.get("file_path"))
        file_role = _clean(row.get("file_role"))
        accession_code = _clean(row.get("accession_code"))
        sample_code = _clean(row.get("sample_code"))
        species_code = _clean(row.get("species_code"))
        unmapped = []

        if not file_path or not file_role:
            return {
                "created_datafile": False,
                "reused_datafile": False,
                "created_relation": 0,
                "reused_relation": 0,
                "unmapped": [{"file_path": file_path, "reason": "missing file_path or file_role"}],
            }

        species = None
        if species_code:
            species = Species.objects.filter(species_code=species_code).first()

        accession = None
        if accession_code:
            accession = Accession.objects.filter(accession=accession_code).first()
            if not accession:
                unmapped.append({"file_path": file_path, "reason": f"accession not found: {accession_code}"})

        sample = None
        if sample_code:
            sample = Sample.objects.filter(sample_code=sample_code).first()
            if not sample:
                unmapped.append({"file_path": file_path, "reason": f"sample not found: {sample_code}"})

        description = {
            "raw_data": {
                "sample_code": sample_code,
                "species_code": species_code,
                "raw_data_type": _clean(row.get("raw_data_type")),
                "sequencing_platform": _clean(row.get("sequencing_platform")),
                "cluster_name": _clean(row.get("cluster_name")),
                "check_status": _clean(row.get("check_status")) or "unchecked",
                "remark": _clean(row.get("remark")),
            }
        }

        data_file = DataFile.objects.filter(file_path=file_path).first()
        created_datafile = False
        reused_datafile = bool(data_file)
        if not data_file:
            data_file = DataFile(
                file_code=make_next_file_code(),
                file_name=_file_name_from_path(file_path),
                original_name=_file_name_from_path(file_path),
                file_path=file_path,
                file_size=_int_or_none(row.get("file_size")),
                md5=_clean(row.get("md5")) or None,
                description=json.dumps(description, ensure_ascii=False),
            )
            created_datafile = True
            if not dry_run:
                data_file.save()
        elif not dry_run:
            update_fields = []
            if row.get("file_size") and data_file.file_size is None:
                data_file.file_size = _int_or_none(row.get("file_size"))
                update_fields.append("file_size")
            if row.get("md5") and not data_file.md5:
                data_file.md5 = _clean(row.get("md5"))
                update_fields.append("md5")
            merged_description = _merge_raw_data_description(data_file.description, description)
            if data_file.description != merged_description:
                data_file.description = merged_description
                update_fields.append("description")
            if update_fields:
                update_fields.append("updated_at")
                data_file.save(update_fields=update_fields)

        created_relation = 0
        reused_relation = 0
        for related_type, related_obj, related_code in (
            ("accession", accession, accession_code),
            ("sample", sample, sample_code),
        ):
            if not related_obj:
                continue
            relation_exists = data_file.pk and FileRelation.objects.filter(
                file=data_file,
                related_type=related_type,
                related_id=str(related_obj.id),
                file_role=file_role,
            ).exists()
            if relation_exists:
                reused_relation += 1
                continue
            created_relation += 1
            if not dry_run:
                FileRelation.objects.get_or_create(
                    file=data_file,
                    related_type=related_type,
                    related_id=str(related_obj.id),
                    file_role=file_role,
                    defaults={
                        "related_code": related_code,
                        "is_primary": False,
                    },
                )

        return {
            "created_datafile": created_datafile,
            "reused_datafile": reused_datafile,
            "created_relation": created_relation,
            "reused_relation": reused_relation,
            "unmapped": unmapped,
        }

    def write_reports(self, log_path, unmapped_path, stats, unmapped):
        with open(log_path, "w", encoding="utf-8") as handle:
            for key, value in stats.items():
                handle.write(f"{key}: {value}\n")

        with open(unmapped_path, "w", encoding="utf-8") as handle:
            handle.write("file_path\treason\n")
            for item in unmapped:
                handle.write(f"{item.get('file_path', '')}\t{item.get('reason', '')}\n")
