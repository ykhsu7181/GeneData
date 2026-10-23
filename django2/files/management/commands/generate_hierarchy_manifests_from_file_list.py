import csv
import re
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from files.models import Accession
from files.services.ingestion.file_parser import parse_ingestion_filename


ASSEMBLY_FIELDS = [
    "assembly_code", "accession", "assembly_accession", "assembly_name",
    "species_code", "assembly_level", "biosample_accession", "assembly_type",
    "assembly_method", "sequencing_technology", "genome_size",
    "chromosome_count", "contig_count", "n50", "gc_content", "reference",
    "source_database", "external_project", "file_name", "file_type",
    "description",
]
ANNOTATION_FIELDS = [
    "annotation_code", "accession", "assembly_code", "annotation_name",
    "annotation_version", "is_default", "species_code", "source_database",
    "source_name", "external_project", "file_name", "file_type",
    "description",
]
FILE_FIELDS = [
    "file_path", "file_role", "accession", "assembly_code",
    "annotation_code", "sample_code", "dataset_code", "md5",
]
EXCEPTION_FIELDS = ["file_path", "file_name", "reason", "detail"]


class Command(BaseCommand):
    help = (
        "Generate full Assembly, Annotation and file-binding manifest drafts "
        "from a production manual_files path list without changing data."
    )

    def add_arguments(self, parser):
        parser.add_argument("--file-list", required=True)
        parser.add_argument("--output-dir", required=True)

    def handle(self, *args, **options):
        source = Path(options["file_list"]).expanduser().resolve()
        output_dir = Path(options["output_dir"]).expanduser().resolve()
        if not source.is_file():
            raise CommandError(f"File list not found: {source}")
        output_dir.mkdir(parents=True, exist_ok=True)

        paths = [
            line.strip()
            for line in source.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        ]
        if len(paths) != len(set(paths)):
            raise CommandError("File list contains duplicate paths.")

        accessions = {
            item.accession: item
            for item in Accession.objects.select_related("species").prefetch_related(
                "assemblies__annotations"
            )
        }
        parsed_rows = []
        exceptions = []
        for raw_path in paths:
            name = Path(raw_path).name
            parsed = parse_ingestion_filename(name)
            if not parsed:
                exceptions.append(self.exception(raw_path, name, "unrecognized_filename"))
                continue
            accession_code, annotation_version = self.resolve_accession(
                name,
                parsed,
                accessions,
            )
            if not accession_code:
                exceptions.append(self.exception(
                    raw_path,
                    name,
                    "accession_not_found",
                    parsed.get("accession_code", ""),
                ))
                continue
            parsed_rows.append({
                "file_path": raw_path,
                "file_name": name,
                "parsed": parsed,
                "accession": accession_code,
                "annotation_version": annotation_version,
            })

        grouped = defaultdict(list)
        for row in parsed_rows:
            grouped[row["accession"]].append(row)

        assembly_rows = []
        annotation_rows = []
        file_rows = []
        assembly_codes = {}
        annotation_codes = {}
        used_assembly_codes = set()
        used_annotation_codes = set()

        for accession_code in sorted(grouped, key=str.casefold):
            items = grouped[accession_code]
            genome_rows = [
                row for row in items
                if row["parsed"]["file_role"] in {"genome", "genome_fasta"}
            ]
            if len(genome_rows) != 1:
                exceptions.append(self.exception(
                    "",
                    accession_code,
                    "missing_or_ambiguous_genome",
                    str(len(genome_rows)),
                ))
                continue
            accession = accessions[accession_code]
            existing_assembly = self.select_existing_assembly(accession)
            assembly_code = (
                existing_assembly.assembly_code
                if existing_assembly and existing_assembly.assembly_code
                else f"ASM_{accession_code}"
            )
            if assembly_code in used_assembly_codes:
                raise CommandError(f"Generated duplicate assembly_code: {assembly_code}")
            used_assembly_codes.add(assembly_code)
            assembly_codes[accession_code] = assembly_code
            assembly_rows.append(self.assembly_row(
                accession,
                existing_assembly,
                assembly_code,
                genome_rows[0]["file_name"],
            ))

            annotations = sorted(
                (row for row in items if row["parsed"]["file_role"] == "annotation"),
                key=lambda row: (bool(row["annotation_version"]), row["file_name"].casefold()),
            )
            for row in annotations:
                version = row["annotation_version"]
                existing_annotation = self.select_existing_annotation(
                    existing_assembly,
                    row["file_name"],
                    version,
                )
                code = (
                    existing_annotation.annotation_code
                    if existing_annotation and existing_annotation.annotation_code
                    else self.annotation_code(accession_code, version)
                )
                if code in used_annotation_codes:
                    raise CommandError(f"Generated duplicate annotation_code: {code}")
                used_annotation_codes.add(code)
                annotation_codes[row["file_name"]] = code
                annotation_rows.append(self.annotation_row(
                    accession,
                    existing_annotation,
                    assembly_code,
                    code,
                    row["file_name"],
                    version,
                ))

        valid_accessions = set(assembly_codes)
        for row in parsed_rows:
            accession_code = row["accession"]
            if accession_code not in valid_accessions:
                continue
            file_rows.append({
                "file_path": row["file_path"],
                "file_role": row["parsed"]["file_role"],
                "accession": accession_code,
                "assembly_code": assembly_codes[accession_code],
                "annotation_code": annotation_codes.get(row["file_name"], ""),
                "sample_code": "",
                "dataset_code": "",
                "md5": "",
            })

        for accession_code in sorted(set(accessions) - valid_accessions, key=str.casefold):
            exceptions.append(self.exception(
                "",
                accession_code,
                "database_accession_without_genome_file",
            ))

        assembly_path = output_dir / "assemblies.full.tsv"
        annotation_path = output_dir / "annotations.full.tsv"
        files_path = output_dir / "files.full.tsv"
        exceptions_path = output_dir / "exceptions.full.tsv"
        self.write_tsv(assembly_path, ASSEMBLY_FIELDS, assembly_rows)
        self.write_tsv(annotation_path, ANNOTATION_FIELDS, annotation_rows)
        self.write_tsv(files_path, FILE_FIELDS, file_rows)
        self.write_tsv(exceptions_path, EXCEPTION_FIELDS, exceptions)

        self.stdout.write(
            f"input_paths\t{len(paths)}\n"
            f"assemblies\t{len(assembly_rows)}\n"
            f"annotations\t{len(annotation_rows)}\n"
            f"file_bindings\t{len(file_rows)}\n"
            f"exceptions\t{len(exceptions)}\n"
            f"assembly_manifest\t{assembly_path}\n"
            f"annotation_manifest\t{annotation_path}\n"
            f"file_manifest\t{files_path}\n"
            f"exception_report\t{exceptions_path}"
        )

    @staticmethod
    def resolve_accession(file_name, parsed, accessions):
        if parsed["file_role"] != "annotation":
            code = parsed["accession_code"]
            return (code, "") if code in accessions else (None, "")
        lower = file_name.lower()
        suffix = next(
            (item for item in (".gff3.gz", ".gff.gz", ".gff3", ".gff") if lower.endswith(item)),
            None,
        )
        if not suffix or not lower.startswith("annotation."):
            return None, ""
        body = file_name[len("annotation."):-len(suffix)]
        matches = [
            code for code in accessions
            if body == code or body.startswith(f"{code}.")
        ]
        if not matches:
            return None, ""
        code = max(matches, key=len)
        version = body[len(code):].lstrip(".")
        return code, version

    @staticmethod
    def select_existing_assembly(accession):
        assemblies = list(accession.assemblies.all())
        coded = [item for item in assemblies if item.assembly_code]
        if len(coded) == 1:
            return coded[0]
        if not coded and len(assemblies) == 1:
            return assemblies[0]
        if not assemblies:
            return None
        raise CommandError(
            f"Accession {accession.accession} has ambiguous Assembly records."
        )

    @staticmethod
    def select_existing_annotation(assembly, file_name, version):
        if not assembly:
            return None
        annotations = list(assembly.annotations.all())
        exact = [item for item in annotations if item.file_name == file_name]
        if len(exact) == 1:
            return exact[0]
        if version:
            version_matches = [
                item for item in annotations
                if (item.annotation_version or item.release_version or "") == version
            ]
            return version_matches[0] if len(version_matches) == 1 else None
        coded = [item for item in annotations if item.annotation_code]
        if len(coded) == 1:
            return coded[0]
        return None

    @staticmethod
    def annotation_code(accession, version):
        if not version:
            return f"ANN_{accession}"
        safe_version = re.sub(r"[^0-9A-Za-z_-]+", "_", version).strip("_")
        return f"ANN_{accession}_{safe_version}"

    @staticmethod
    def assembly_row(accession, assembly, code, file_name):
        meaningful_name = ""
        if assembly:
            meaningful_name = assembly.assembly_name or assembly.display_name or ""
            if not meaningful_name and assembly.name != "default":
                meaningful_name = assembly.name
        species_code = (
            (assembly.species_code if assembly else None)
            or (accession.species.species_code if accession.species else None)
            or ""
        )
        value = lambda field: getattr(assembly, field, None) if assembly else None
        return {
            "assembly_code": code,
            "accession": accession.accession,
            "assembly_accession": value("assembly_accession") or "",
            "assembly_name": meaningful_name or f"{accession.accession} genome assembly",
            "species_code": species_code,
            "assembly_level": value("assembly_level") or "",
            "biosample_accession": value("biosample_accession") or "",
            "assembly_type": value("assembly_type") or "",
            "assembly_method": value("assembly_method") or "",
            "sequencing_technology": value("sequencing_technology") or "",
            "genome_size": value("genome_size") or "",
            "chromosome_count": value("chromosome_count") or "",
            "contig_count": value("contig_count") or "",
            "n50": value("n50") or "",
            "gc_content": value("gc_content") or "",
            "reference": value("reference") or "",
            "source_database": value("source_database") or "",
            "external_project": value("external_project") or "",
            "file_name": file_name,
            "file_type": "FASTA",
            "description": value("description") or "",
        }

    @staticmethod
    def annotation_row(accession, annotation, assembly_code, code, file_name, version):
        meaningful_name = ""
        if annotation:
            meaningful_name = annotation.annotation_name or annotation.display_name or ""
            if not meaningful_name and annotation.name != "default-annotation":
                meaningful_name = annotation.name
        value = lambda field: getattr(annotation, field, None) if annotation else None
        display_version = version or value("annotation_version") or value("release_version") or ""
        return {
            "annotation_code": code,
            "accession": accession.accession,
            "assembly_code": assembly_code,
            "annotation_name": meaningful_name or (
                f"{accession.accession} {version} annotation"
                if version else f"{accession.accession} annotation"
            ),
            "annotation_version": display_version,
            "is_default": "false" if version else "true",
            "species_code": value("species_code") or (
                accession.species.species_code if accession.species else ""
            ),
            "source_database": value("source_database") or "",
            "source_name": value("source_name") or "",
            "external_project": value("external_project") or "",
            "file_name": file_name,
            "file_type": "GFF",
            "description": value("description") or "",
        }

    @staticmethod
    def exception(file_path, file_name, reason, detail=""):
        return {
            "file_path": file_path,
            "file_name": file_name,
            "reason": reason,
            "detail": detail,
        }

    @staticmethod
    def write_tsv(path, fields, rows):
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)
