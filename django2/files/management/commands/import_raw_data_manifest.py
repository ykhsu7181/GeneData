import csv
import json
import os
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from files.models import Accession, Sample, Species
from files.services.file_write_service import (
    create_or_get_datafile_from_path,
    create_or_get_file_relation,
)
from files.services.ingestion.roles import validate_file_role
from files.services.import_log_service import (
    build_import_stats,
    add_provenance_arguments,
    import_timestamp,
    provenance_options,
    write_key_value_report,
)


REQUIRED_COLUMNS = {"file_path", "file_role"}


def _clean(value):
    return (value or "").strip()


def _normalize_manifest_path(file_path):
    value = _clean(file_path).replace("\\", "/")
    while "//" in value:
        value = value.replace("//", "/")
    drive, _ = os.path.splitdrive(value)
    if drive:
        return os.path.abspath(os.path.normpath(value))
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
        add_provenance_arguments(parser)

    def handle(self, *args, **options):
        input_path = options["input_path"]
        dry_run = options["dry_run"]
        limit = options["limit"]
        started_at = datetime.now().isoformat(timespec="seconds")
        if not os.path.exists(input_path):
            raise CommandError(f"Input file does not exist: {input_path}")

        created_datafile = 0
        reused_datafile = 0
        updated_datafile = 0
        created_relation = 0
        reused_relation = 0
        unmapped = []
        scanned = 0
        skipped = 0

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
                updated_datafile += int(result["updated_datafile"])
                created_relation += result["created_relation"]
                reused_relation += result["reused_relation"]
                unmapped.extend(result["unmapped"])
                skipped += int(result["skipped"])

        finished_at = datetime.now().isoformat(timespec="seconds")
        timestamp = import_timestamp()
        log_path = f"import_raw_data_log_{timestamp}.txt"
        unmapped_path = f"import_raw_data_unmapped_{timestamp}.tsv"
        stats = build_import_stats(
            command="import_raw_data_manifest",
            input_path=input_path,
            dry_run=dry_run,
            started_at=started_at,
            finished_at=finished_at,
            scanned_count=scanned,
            created_count=created_datafile + created_relation,
            reused_count=reused_datafile + reused_relation,
            updated_count=updated_datafile,
            skipped_count=skipped,
            unmapped_count=len(unmapped),
            **provenance_options(options),
            extra={
                "created_datafile_count": created_datafile,
                "reused_datafile_count": reused_datafile,
                "updated_datafile_count": updated_datafile,
                "created_filerelation_count": created_relation,
                "reused_filerelation_count": reused_relation,
            },
        )
        self.write_reports(
            log_path,
            unmapped_path,
            stats,
            unmapped,
        )
        self.stdout.write(f"scanned_count={scanned}")
        self.stdout.write(f"created_datafile_count={created_datafile}")
        self.stdout.write(f"created_filerelation_count={created_relation}")
        self.stdout.write(f"log={log_path}")
        self.stdout.write(f"unmapped={unmapped_path}")

    @transaction.atomic
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
                "updated_datafile": False,
                "created_relation": 0,
                "reused_relation": 0,
                "unmapped": [{"file_path": file_path, "reason": "missing file_path or file_role"}],
                "skipped": True,
            }

        try:
            validate_file_role(file_role)
        except ValueError:
            return self._rejected_row(file_path, f"invalid file_role: {file_role}")

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

        if unmapped:
            return self._rejected_row(file_path, unmapped)
        if not accession and not sample:
            return self._rejected_row(file_path, "no valid relation target")

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

        data_file, created_datafile, reused_datafile, updated_datafile = (
            create_or_get_datafile_from_path(
                file_path=file_path,
                file_name=_file_name_from_path(file_path),
                file_size=_int_or_none(row.get("file_size")),
                md5=_clean(row.get("md5")) or None,
                description=json.dumps(description, ensure_ascii=False),
                normalize_path=False,
                dry_run=dry_run,
            )
        )
        if reused_datafile:
            merged_description = _merge_raw_data_description(data_file.description, description)
            if data_file.description != merged_description:
                updated_datafile = True
                if not dry_run:
                    data_file.description = merged_description
                    data_file.save(update_fields=["description", "updated_at"])

        created_relation = 0
        reused_relation = 0
        for related_type, related_obj, related_code in (
            ("accession", accession, accession_code),
            ("sample", sample, sample_code),
        ):
            if not related_obj:
                continue
            _, relation_created, relation_reused = create_or_get_file_relation(
                data_file=data_file,
                related_type=related_type,
                related_id=related_obj.id,
                related_code=related_code,
                file_role=file_role,
                dry_run=dry_run,
            )
            if relation_created:
                created_relation += 1
            elif relation_reused:
                reused_relation += 1

        return {
            "created_datafile": created_datafile,
            "reused_datafile": reused_datafile,
            "updated_datafile": updated_datafile,
            "created_relation": created_relation,
            "reused_relation": reused_relation,
            "unmapped": unmapped,
            "skipped": False,
        }

    def _rejected_row(self, file_path, reasons):
        if isinstance(reasons, str):
            reasons = [{"file_path": file_path, "reason": reasons}]
        return {
            "created_datafile": False,
            "reused_datafile": False,
            "updated_datafile": False,
            "created_relation": 0,
            "reused_relation": 0,
            "unmapped": reasons,
            "skipped": True,
        }

    def write_reports(self, log_path, unmapped_path, stats, unmapped):
        write_key_value_report(log_path, stats)

        with open(unmapped_path, "w", encoding="utf-8") as handle:
            handle.write("file_path\treason\n")
            for item in unmapped:
                handle.write(f"{item.get('file_path', '')}\t{item.get('reason', '')}\n")
