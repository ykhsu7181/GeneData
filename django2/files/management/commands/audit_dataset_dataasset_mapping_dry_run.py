from collections import Counter, defaultdict
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from files.management.commands.audit_datafile_asset_mapping_readiness import (
    Command as DataFileCandidateAudit,
)
from files.management.external_data_command import write_tsv
from files.models import (
    DataAsset,
    DataAssetAccession,
    DataFile,
    Dataset,
    DatasetAccession,
    FileRelation,
)
from files.services.data_asset_registry_service import (
    DataAssetRegistryError,
    load_data_asset_registry,
)
from files.services.datafile_access_service import LEVEL_RANK, resolve_datafile_access_level


SUMMARY_FIELDS = ("metric", "value")
ASSET_FIELDS = (
    "dataset_id",
    "dataset_code",
    "mapping_action",
    "mapping_status",
    "project_code",
    "proposed_name",
    "proposed_description",
    "legacy_dataset_type",
    "legacy_bioproject_accession",
    "legacy_species_code",
    "species_context_resolution",
    "data_type_key",
    "profile_key",
    "schema_version",
    "schema_digest",
    "proposed_status",
    "proposed_visibility",
    "proposed_metadata",
    "version",
    "accession_count",
    "member_candidate_count",
    "ready_member_count",
    "review_member_count",
    "blocked_member_count",
    "issues",
)
ACCESSION_FIELDS = (
    "dataset_code",
    "accession_id",
    "accession",
    "relation_role",
    "source",
    "proposed_primary_slot",
    "mapping_status",
    "issues",
)
MEMBERSHIP_FIELDS = (
    "data_file_id",
    "file_code",
    "dataset_code",
    "candidate_source",
    "t1_classification",
    "legacy_file_roles",
    "proposed_file_role",
    "proposed_position",
    "proposed_is_primary",
    "file_access_level",
    "file_publication_status",
    "current_effective_access_level",
    "proposed_effective_access_level",
    "permission_comparison",
    "mapping_status",
    "issues",
)
ISSUE_FIELDS = ("entity_type", "entity_code", "severity", "issue")
REPORT_NAMES = {
    "summary": "dataasset_t4_summary.tsv",
    "assets": "dataasset_t4_assets.tsv",
    "accessions": "dataasset_t4_accessions.tsv",
    "memberships": "dataasset_t4_memberships.tsv",
    "issues": "dataasset_t4_issues.tsv",
}

# Migration-only mapping. Missing entries are intentionally blocked until a
# profile is approved; this does not expand the core DataAsset model.
LEGACY_DATASET_PROFILE_MAP = {
    "genome": ("sequence", "reference_genome"),
}

LEGACY_FILE_ROLE_MAP = {
    "genome": "genome_fasta",
    "genome_fasta": "genome_fasta",
    "fasta": "genome_fasta",
    "fa": "genome_fasta",
    "genome_index": "fasta_index",
    "fai": "fasta_index",
    "compression_index": "compression_index",
    "gzi": "compression_index",
    "metadata": "metadata",
    "checksum": "metadata",
}

BLOCKING_T1_ISSUES = {
    "invalid_related_id",
    "missing_related_object",
    "annotation_accession_conflict",
    "multiple_accession_contexts",
    "multiple_current_datasets",
    "current_dataset_outside_accession_context",
}
ALLOWED_ACCESSION_ROLES = dict(DataAssetAccession.RELATION_ROLE_CHOICES)


class Command(BaseCommand):
    help = "Write a strictly read-only T4 Dataset-to-DataAsset mapping dry-run."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            required=True,
            help="Private directory for deterministic DataAsset T4 TSV reports.",
        )

    def handle(self, *args, **options):
        output_dir = Path(options["output_dir"]).resolve()
        paths = {name: output_dir / filename for name, filename in REPORT_NAMES.items()}
        existing = [path for path in paths.values() if path.exists()]
        if existing:
            raise CommandError(
                "Refusing to overwrite existing DataAsset T4 reports: "
                + ", ".join(str(path) for path in existing)
            )
        output_dir.mkdir(parents=True, exist_ok=True)

        with transaction.atomic():
            reports = self.collect_reports()
            transaction.set_rollback(True)

        write_tsv(paths["summary"], SUMMARY_FIELDS, reports["summary"])
        write_tsv(paths["assets"], ASSET_FIELDS, reports["assets"])
        write_tsv(paths["accessions"], ACCESSION_FIELDS, reports["accessions"])
        write_tsv(paths["memberships"], MEMBERSHIP_FIELDS, reports["memberships"])
        write_tsv(paths["issues"], ISSUE_FIELDS, reports["issues"])

        self.stdout.write("mode\tREAD_ONLY_DRY_RUN")
        for name in ("summary", "assets", "accessions", "memberships", "issues"):
            self.stdout.write(f"{name}\t{len(reports[name])}\t{paths[name]}")

    def collect_reports(self):
        registry = load_data_asset_registry()
        datasets = list(
            Dataset.objects.select_related("project", "species").order_by(
                "dataset_code", "id"
            )
        )
        accession_links = list(
            DatasetAccession.objects.select_related(
                "accession", "accession__species", "dataset"
            ).order_by("dataset__dataset_code", "accession__accession", "id")
        )
        accessions_by_dataset = defaultdict(list)
        for link in accession_links:
            accessions_by_dataset[link.dataset_id].append(link)

        existing_assets = self.load_existing_assets()
        plans = {}
        accession_rows = []
        for dataset in datasets:
            plan = self.build_asset_plan(
                dataset,
                accessions_by_dataset[dataset.id],
                existing_assets.get(dataset.dataset_code),
                registry,
            )
            plans[dataset.dataset_code] = plan
            accession_rows.extend(plan["accession_rows"])

        data_files = {
            data_file.id: data_file
            for data_file in DataFile.objects.order_by("id")
        }
        relation_primary = defaultdict(list)
        for relation in FileRelation.objects.values(
            "file_id", "file_role", "is_primary"
        ).order_by("file_id", "id"):
            relation_primary[relation["file_id"]].append(relation)

        t1_rows = DataFileCandidateAudit().collect_reports()["files"]
        membership_rows = [
            self.build_membership_row(
                row,
                data_files[row["data_file_id"]],
                relation_primary[row["data_file_id"]],
                plans,
                registry,
            )
            for row in t1_rows
        ]
        self.assign_positions_and_primary_flags(membership_rows)
        asset_rows = self.finalize_asset_rows(datasets, plans, membership_rows)
        issue_rows = self.build_issue_rows(asset_rows, accession_rows, membership_rows)
        summary = self.build_summary(asset_rows, accession_rows, membership_rows, issue_rows)
        summary.append(
            {
                "metric": "target_table_available",
                "value": int("data_asset" in connection.introspection.table_names()),
            }
        )
        return {
            "summary": summary,
            "assets": asset_rows,
            "accessions": accession_rows,
            "memberships": membership_rows,
            "issues": issue_rows,
        }

    @staticmethod
    def load_existing_assets():
        if "data_asset" not in connection.introspection.table_names():
            return {}
        return {
            asset.asset_code: asset
            for asset in DataAsset.objects.select_related("project").order_by("id")
        }

    def build_asset_plan(self, dataset, accession_links, existing_asset, registry):
        issues = []
        profile = None
        proposed_metadata = {}
        species_context_resolution = "not_applicable"
        if not (dataset.dataset_code or "").strip():
            issues.append(("blocked", "empty_dataset_code"))
        if dataset.project_id is None:
            issues.append(("blocked", "missing_project"))

        profile_keys = LEGACY_DATASET_PROFILE_MAP.get(dataset.dataset_type)
        if profile_keys is None:
            issues.append(("blocked", "unregistered_dataset_type"))
        else:
            try:
                profile = registry.get_profile(*profile_keys)
            except DataAssetRegistryError:
                issues.append(("blocked", "registered_profile_missing"))

        bioproject_accession = (dataset.bioproject_accession or "").strip()
        if bioproject_accession:
            proposed_metadata = {
                "external_identifiers": {"bioproject": bioproject_accession}
            }
        if profile is not None:
            try:
                registry.validate_metadata(
                    profile.data_type_key,
                    profile.profile_key,
                    proposed_metadata,
                )
            except DataAssetRegistryError:
                issues.append(("blocked", "proposed_metadata_invalid"))

        if dataset.species_id is not None:
            accession_species_ids = {
                link.accession.species_id for link in accession_links
            }
            if accession_links and accession_species_ids == {dataset.species_id}:
                species_context_resolution = "accession_context"
            else:
                species_context_resolution = "requires_review"
                issues.append(("review", "species_context_requires_review"))

        if dataset.status not in dict(DataAsset.STATUS_CHOICES):
            issues.append(("blocked", "unsupported_status"))
        if dataset.visibility not in dict(DataAsset.VISIBILITY_CHOICES):
            issues.append(("blocked", "unsupported_visibility"))
        if dataset.status == DataAsset.STATUS_RELEASED:
            issues.append(("review", "released_asset_requires_published_at"))

        primary_count = sum(
            link.relation_role == DataAssetAccession.ROLE_PRIMARY
            for link in accession_links
        )
        if primary_count > 1:
            issues.append(("blocked", "multiple_primary_accessions"))
        if any(link.relation_role not in ALLOWED_ACCESSION_ROLES for link in accession_links):
            issues.append(("blocked", "unsupported_accession_role"))

        mapping_action = "create"
        if existing_asset is not None:
            if profile and self.existing_asset_core_matches(
                dataset,
                existing_asset,
                profile,
                proposed_metadata,
            ):
                mapping_action = "existing_core_match"
                issues.append(("review", "existing_relations_require_review"))
            else:
                mapping_action = "existing_conflict"
                issues.append(("blocked", "existing_asset_conflict"))

        blocked = self.has_severity(issues, "blocked")
        accession_rows = []
        for link in accession_links:
            link_issues = []
            if link.relation_role not in ALLOWED_ACCESSION_ROLES:
                link_issues.append("unsupported_accession_role")
            if blocked:
                link_issues.append("asset_mapping_blocked")
            accession_rows.append(
                {
                    "dataset_code": dataset.dataset_code,
                    "accession_id": link.accession_id,
                    "accession": link.accession.accession,
                    "relation_role": link.relation_role,
                    "source": link.source or "",
                    "proposed_primary_slot": (
                        1 if link.relation_role == DataAssetAccession.ROLE_PRIMARY else ""
                    ),
                    "mapping_status": "blocked" if link_issues else "ready",
                    "issues": ",".join(self.unique(link_issues)),
                }
            )

        return {
            "dataset": dataset,
            "profile": profile,
            "mapping_action": mapping_action,
            "proposed_metadata": proposed_metadata,
            "species_context_resolution": species_context_resolution,
            "issues": issues,
            "accession_rows": accession_rows,
        }

    @staticmethod
    def existing_asset_core_matches(dataset, asset, profile, proposed_metadata):
        return all(
            (
                asset.project_id == dataset.project_id,
                asset.name == (dataset.dataset_name or ""),
                asset.data_type_key == profile.data_type_key,
                asset.profile_key == profile.profile_key,
                asset.schema_version == profile.schema_version,
                asset.schema_digest == profile.schema_digest,
                asset.version == dataset.version,
                asset.status == dataset.status,
                asset.visibility == dataset.visibility,
                asset.metadata == proposed_metadata,
                asset.description == (dataset.description or ""),
            )
        )

    def build_membership_row(
        self, t1_row, data_file, primary_relations, plans, registry
    ):
        t1_issues = self.split_values(t1_row["issues"])
        current_codes = self.split_values(t1_row["current_dataset_codes"])
        compatible_codes = self.split_values(t1_row["type_compatible_candidates"])
        dataset_code = ""
        candidate_source = ""
        issues = list(t1_issues)

        if len(current_codes) == 1 and not BLOCKING_T1_ISSUES.intersection(t1_issues):
            dataset_code = current_codes[0]
            candidate_source = "explicit_dataset"
        elif (
            t1_row["classification"] == "unique_type_candidate"
            and len(compatible_codes) == 1
            and not BLOCKING_T1_ISSUES.intersection(t1_issues)
        ):
            dataset_code = compatible_codes[0]
            candidate_source = "t1_unique_type_candidate"
        else:
            issues.append("no_automatic_dataset_mapping")

        plan = plans.get(dataset_code)
        legacy_roles = self.split_values(t1_row["file_roles"])
        proposed_role = self.map_file_role(legacy_roles)
        if dataset_code and proposed_role is None:
            issues.append("file_role_unresolved")
        if plan and plan["profile"] and proposed_role:
            try:
                registry.validate_file_role(
                    plan["profile"].data_type_key,
                    plan["profile"].profile_key,
                    proposed_role,
                )
            except DataAssetRegistryError:
                issues.append("file_role_not_allowed_by_profile")

        current_level, current_reason = resolve_datafile_access_level(data_file)
        proposed_level = ""
        permission_comparison = "not_evaluated"
        if current_reason == "policy_integrity_error":
            issues.append("current_permission_integrity_error")
        if plan is not None:
            proposed_level = self.proposed_access_level(plan["dataset"], data_file)
            permission_comparison = self.compare_access(current_level, proposed_level)
            if permission_comparison == "widening":
                issues.append("permission_widening")
            elif permission_comparison == "tightening":
                issues.append("permission_tightening")

        if not data_file.is_current:
            issues.append("file_not_current")
        if data_file.publication_status != DataFile.PUBLICATION_RELEASED:
            issues.append("file_not_released")
        if data_file.published_at is None:
            issues.append("file_published_at_missing")
        if data_file.content_version is None:
            issues.append("file_checksum_unverified")

        mapping_status = "ready"
        if not dataset_code or proposed_role is None:
            mapping_status = "review"
        if plan is not None and self.has_severity(plan["issues"], "blocked"):
            mapping_status = "blocked"
            issues.append("asset_mapping_blocked")
        if "permission_widening" in issues or "current_permission_integrity_error" in issues:
            mapping_status = "blocked"
        elif mapping_status == "ready" and issues:
            mapping_status = "review"

        explicit_primary = any(
            relation["is_primary"]
            and LEGACY_FILE_ROLE_MAP.get((relation["file_role"] or "").strip().lower())
            == proposed_role
            for relation in primary_relations
        )
        return {
            "data_file_id": data_file.id,
            "file_code": data_file.file_code,
            "dataset_code": dataset_code,
            "candidate_source": candidate_source,
            "t1_classification": t1_row["classification"],
            "legacy_file_roles": ",".join(legacy_roles),
            "proposed_file_role": proposed_role or "",
            "proposed_position": "",
            "proposed_is_primary": 0,
            "_explicit_primary": explicit_primary,
            "file_access_level": data_file.access_level,
            "file_publication_status": data_file.publication_status,
            "current_effective_access_level": current_level,
            "proposed_effective_access_level": proposed_level,
            "permission_comparison": permission_comparison,
            "mapping_status": mapping_status,
            "issues": ",".join(self.unique(issues)),
        }

    def assign_positions_and_primary_flags(self, rows):
        groups = defaultdict(list)
        for row in rows:
            if row["dataset_code"] and row["proposed_file_role"]:
                groups[(row["dataset_code"], row["proposed_file_role"])].append(row)

        for group_rows in groups.values():
            group_rows.sort(key=lambda row: (row["file_code"], row["data_file_id"]))
            for position, row in enumerate(group_rows):
                row["proposed_position"] = position
            primary_rows = [row for row in group_rows if row["_explicit_primary"]]
            if len(primary_rows) == 1:
                primary_rows[0]["proposed_is_primary"] = 1
            elif len(primary_rows) > 1:
                for row in group_rows:
                    if row["mapping_status"] == "ready":
                        row["mapping_status"] = "review"
                    row["issues"] = self.append_issue(
                        row["issues"], "multiple_primary_file_candidates"
                    )
        for row in rows:
            row.pop("_explicit_primary", None)

    def finalize_asset_rows(self, datasets, plans, membership_rows):
        memberships_by_dataset = defaultdict(list)
        for row in membership_rows:
            if row["dataset_code"]:
                memberships_by_dataset[row["dataset_code"]].append(row)

        asset_rows = []
        for dataset in datasets:
            plan = plans[dataset.dataset_code]
            members = memberships_by_dataset[dataset.dataset_code]
            issues = list(plan["issues"])
            if not members:
                issues.append(("review", "no_file_membership_candidate"))
            if any(row["mapping_status"] == "blocked" for row in members):
                issues.append(("blocked", "blocked_file_membership"))
            elif any(row["mapping_status"] == "review" for row in members):
                issues.append(("review", "file_membership_requires_review"))

            if self.has_severity(issues, "blocked"):
                mapping_status = "blocked"
            elif self.has_severity(issues, "review"):
                mapping_status = "review"
            else:
                mapping_status = "ready"
            profile = plan["profile"]
            asset_rows.append(
                {
                    "dataset_id": dataset.id,
                    "dataset_code": dataset.dataset_code,
                    "mapping_action": plan["mapping_action"],
                    "mapping_status": mapping_status,
                    "project_code": dataset.project.project_code if dataset.project_id else "",
                    "proposed_name": dataset.dataset_name or "",
                    "proposed_description": dataset.description or "",
                    "legacy_dataset_type": dataset.dataset_type,
                    "legacy_bioproject_accession": dataset.bioproject_accession or "",
                    "legacy_species_code": (
                        dataset.species.species_code if dataset.species_id else ""
                    ),
                    "species_context_resolution": plan["species_context_resolution"],
                    "data_type_key": profile.data_type_key if profile else "",
                    "profile_key": profile.profile_key if profile else "",
                    "schema_version": profile.schema_version if profile else "",
                    "schema_digest": profile.schema_digest if profile else "",
                    "proposed_status": dataset.status,
                    "proposed_visibility": dataset.visibility,
                    "proposed_metadata": json.dumps(
                        plan["proposed_metadata"],
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    "version": dataset.version or "",
                    "accession_count": len(plan["accession_rows"]),
                    "member_candidate_count": len(members),
                    "ready_member_count": sum(
                        row["mapping_status"] == "ready" for row in members
                    ),
                    "review_member_count": sum(
                        row["mapping_status"] == "review" for row in members
                    ),
                    "blocked_member_count": sum(
                        row["mapping_status"] == "blocked" for row in members
                    ),
                    "issues": ",".join(self.unique(issue for _, issue in issues)),
                    "_issues_with_severity": issues,
                }
            )
        return asset_rows

    @staticmethod
    def build_issue_rows(asset_rows, accession_rows, membership_rows):
        issue_rows = []
        for row in asset_rows:
            for severity, issue in row.pop("_issues_with_severity"):
                issue_rows.append(
                    {
                        "entity_type": "dataset",
                        "entity_code": row["dataset_code"],
                        "severity": severity,
                        "issue": issue,
                    }
                )
        for entity_type, rows, code_field in (
            ("accession_link", accession_rows, "accession"),
            ("data_file", membership_rows, "file_code"),
        ):
            for row in rows:
                severity = "blocked" if row["mapping_status"] == "blocked" else "review"
                for issue in Command.split_values(row["issues"]):
                    issue_rows.append(
                        {
                            "entity_type": entity_type,
                            "entity_code": row[code_field],
                            "severity": severity,
                            "issue": issue,
                        }
                    )
        return sorted(
            issue_rows,
            key=lambda row: (
                row["severity"],
                row["entity_type"],
                row["entity_code"],
                row["issue"],
            ),
        )

    @staticmethod
    def build_summary(asset_rows, accession_rows, membership_rows, issue_rows):
        summary = [
            {"metric": "dataset_total", "value": len(asset_rows)},
            {"metric": "accession_link_total", "value": len(accession_rows)},
            {"metric": "datafile_total", "value": len(membership_rows)},
            {
                "metric": "membership_candidate_total",
                "value": sum(bool(row["dataset_code"]) for row in membership_rows),
            },
        ]
        for prefix, rows in (
            ("asset_status", asset_rows),
            ("accession_status", accession_rows),
            ("membership_status", membership_rows),
        ):
            counts = Counter(row["mapping_status"] for row in rows)
            for status in ("ready", "review", "blocked"):
                summary.append(
                    {"metric": f"{prefix}:{status}", "value": counts[status]}
                )
        issue_counts = Counter(row["issue"] for row in issue_rows)
        for issue, count in sorted(issue_counts.items()):
            summary.append({"metric": f"issue:{issue}", "value": count})
        return summary

    @staticmethod
    def map_file_role(legacy_roles):
        mapped = {
            LEGACY_FILE_ROLE_MAP[role.strip().lower()]
            for role in legacy_roles
            if role.strip().lower() in LEGACY_FILE_ROLE_MAP
        }
        return next(iter(mapped)) if len(mapped) == 1 else None

    @staticmethod
    def proposed_access_level(dataset, data_file):
        asset_level = Command.dataset_access_level(dataset)
        if data_file.access_level == DataFile.ACCESS_LEVEL_INHERITED:
            return asset_level
        return max(
            (data_file.access_level, asset_level),
            key=lambda level: LEVEL_RANK.get(
                level, LEVEL_RANK[DataFile.ACCESS_LEVEL_PRIVATE]
            ),
        )

    @staticmethod
    def dataset_access_level(dataset):
        if dataset.status != DataAsset.STATUS_RELEASED:
            return DataFile.ACCESS_LEVEL_PRIVATE
        return {
            DataAsset.VISIBILITY_PUBLIC: DataFile.ACCESS_LEVEL_PUBLIC,
            DataAsset.VISIBILITY_INTERNAL: DataFile.ACCESS_LEVEL_INTERNAL,
            DataAsset.VISIBILITY_PRIVATE: DataFile.ACCESS_LEVEL_PRIVATE,
        }.get(dataset.visibility, DataFile.ACCESS_LEVEL_PRIVATE)

    @staticmethod
    def compare_access(current_level, proposed_level):
        current_rank = LEVEL_RANK.get(current_level, LEVEL_RANK[DataFile.ACCESS_LEVEL_PRIVATE])
        proposed_rank = LEVEL_RANK.get(
            proposed_level, LEVEL_RANK[DataFile.ACCESS_LEVEL_PRIVATE]
        )
        if proposed_rank < current_rank:
            return "widening"
        if proposed_rank > current_rank:
            return "tightening"
        return "same"

    @staticmethod
    def has_severity(issues, severity):
        return any(item_severity == severity for item_severity, _ in issues)

    @staticmethod
    def split_values(value):
        return [item for item in (value or "").split(",") if item]

    @staticmethod
    def unique(values):
        return list(dict.fromkeys(values))

    @staticmethod
    def append_issue(existing, issue):
        return ",".join(Command.unique(Command.split_values(existing) + [issue]))
