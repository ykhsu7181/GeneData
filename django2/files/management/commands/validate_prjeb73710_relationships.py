import csv
import os
from datetime import datetime

from django.core.management.base import BaseCommand

from files.models import Accession, AccessionExternalMapping, Dataset, Sample


def _timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


class Command(BaseCommand):
    help = "Read-only validation for imported BioProject, Sample, and ENA relationships."

    def add_arguments(self, parser):
        parser.add_argument("--bioproject", default="PRJEB73710")
        parser.add_argument("--ena-study", default="ERP158450")
        parser.add_argument("--output-dir", default="audit_reports")

    def handle(self, *args, **options):
        bioproject = options["bioproject"]
        ena_study = options["ena_study"]
        output_dir = options["output_dir"]
        os.makedirs(output_dir, exist_ok=True)

        datasets = Dataset.objects.filter(bioproject_accession=bioproject).select_related("species", "project")
        mappings = AccessionExternalMapping.objects.filter(
            external_study_accession=ena_study
        ).select_related("accession__species")
        experiment_ids = set(
            mappings.exclude(experiment_accession__isnull=True)
            .exclude(experiment_accession="")
            .values_list("experiment_accession", flat=True)
        )
        samples = Sample.objects.filter(experiment_accession__in=experiment_ids).select_related("accession__species", "species")

        issues = []
        self._check_datasets(datasets, bioproject, issues)
        self._check_samples(samples, experiment_ids, issues)
        self._check_mappings(mappings, issues)

        datafile_count = sum(dataset.data_files.count() for dataset in datasets)
        stats = {
            "bioproject": bioproject,
            "ena_study": ena_study,
            "dataset_count": datasets.count(),
            "sample_count": samples.count(),
            "external_mapping_count": mappings.count(),
            "accession_count": mappings.values("accession_id").distinct().count(),
            "dataset_without_species_count": datasets.filter(species__isnull=True).count(),
            "dataset_without_project_count": datasets.filter(project__isnull=True).count(),
            "sample_without_accession_count": samples.filter(accession__isnull=True).count(),
            "sample_without_species_count": samples.filter(species__isnull=True).count(),
            "sample_species_mismatch_count": sum(
                sample.accession_id is not None
                and sample.species_id is not None
                and sample.accession.species_id != sample.species_id
                for sample in samples
            ),
            "mapping_accession_without_species_count": mappings.filter(accession__species__isnull=True).count(),
            "mapping_without_run_count": mappings.filter(run_accession__isnull=True).count() + mappings.filter(run_accession="").count(),
            "dataset_datafile_count": datafile_count,
            "issue_count": len(issues),
            "status": "PASS" if not issues else "FAIL",
        }

        stamp = _timestamp()
        report_path = os.path.join(output_dir, f"prjeb_relationship_validation_{stamp}.txt")
        detail_path = os.path.join(output_dir, f"prjeb_relationship_validation_{stamp}.tsv")
        self._write_report(report_path, stats)
        self._write_details(detail_path, issues)
        for key, value in stats.items():
            self.stdout.write(f"{key}={value}")
        self.stdout.write(f"report={report_path}")
        self.stdout.write(f"details={detail_path}")

    @staticmethod
    def _check_datasets(datasets, bioproject, issues):
        for dataset in datasets:
            if dataset.species_id is None:
                issues.append(Command._issue("dataset", dataset.id, dataset.dataset_code, "missing species", "set Dataset.species from the related Accession"))
            if dataset.project_id is None:
                issues.append(Command._issue("dataset", dataset.id, dataset.dataset_code, "missing project", "set Dataset.project to the BioProject record"))
            elif dataset.project.project_code != bioproject:
                issues.append(Command._issue("dataset", dataset.id, dataset.dataset_code, "project code differs from BioProject", "review Project mapping"))

    @staticmethod
    def _check_samples(samples, experiment_ids, issues):
        for sample in samples:
            if sample.accession_id is None:
                issues.append(Command._issue("sample", sample.id, sample.sample_code, "missing accession", "import or repair Sample.accession"))
            if sample.species_id is None:
                issues.append(Command._issue("sample", sample.id, sample.sample_code, "missing species", "import or repair Sample.species"))
            if sample.experiment_accession not in experiment_ids:
                issues.append(Command._issue("sample", sample.id, sample.sample_code, "experiment not present in ENA mapping", "review Experiment accession"))
            if sample.accession_id and sample.species_id and sample.accession.species_id != sample.species_id:
                issues.append(Command._issue("sample", sample.id, sample.sample_code, "species differs from accession species", "align Sample.species with Accession.species"))

    @staticmethod
    def _check_mappings(mappings, issues):
        for mapping in mappings:
            if mapping.accession.species_id is None:
                issues.append(Command._issue("accession_external_mapping", mapping.id, mapping.run_accession, "accession missing species", "repair Accession.species"))
            if not mapping.run_accession:
                issues.append(Command._issue("accession_external_mapping", mapping.id, mapping.experiment_accession, "missing run accession", "supplement ENA run metadata"))

    @staticmethod
    def _issue(object_type, object_id, code, issue, suggested_action):
        return {
            "object_type": object_type,
            "object_id": object_id,
            "code": code or "-",
            "issue": issue,
            "suggested_action": suggested_action,
        }

    @staticmethod
    def _write_report(path, stats):
        with open(path, "w", encoding="utf-8") as handle:
            for key, value in stats.items():
                handle.write(f"{key}: {value}\n")

    @staticmethod
    def _write_details(path, rows):
        with open(path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["object_type", "object_id", "code", "issue", "suggested_action"],
                delimiter="\t",
            )
            writer.writeheader()
            writer.writerows(rows)
