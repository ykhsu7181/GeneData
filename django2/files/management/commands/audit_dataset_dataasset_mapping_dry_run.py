from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from files.management.external_data_command import write_tsv
from files.models import Assembly, DataAsset, DataFile, Dataset, DatasetAccession, FileRelation
from files.services.data_asset_registry_service import (
    DataAssetRegistryError,
    load_data_asset_registry,
)
from files.services.data_overview_service import categorize_file_role
from files.services.datafile_access_service import LEVEL_RANK, resolve_datafile_access_level


SUMMARY_FIELDS = ("metric", "value")
ASSET_FIELDS = (
    "candidate_key", "proposed_asset_code", "mapping_action", "mapping_status",
    "evidence_source", "supporting_dataset_codes", "project_code", "proposed_name",
    "data_type_key", "profile_key", "schema_version", "schema_digest",
    "proposed_status", "proposed_visibility", "proposed_metadata", "version",
    "core_file_count", "auxiliary_file_count", "context_count", "issues",
)
MEMBERSHIP_FIELDS = (
    "candidate_key", "data_file_id", "file_code", "evidence_relation_ids",
    "proposed_file_role", "file_role_class", "proposed_position",
    "proposed_is_primary", "mapping_status", "issues",
)
CONTEXT_FIELDS = (
    "candidate_key", "context_type", "context_id", "context_code",
    "evidence_source", "mapping_status", "issues",
)
EXCLUSION_FIELDS = (
    "dataset_id", "dataset_code", "dataset_type", "mapping_status", "reason",
    "has_datafile_evidence", "has_file_relation_evidence",
)
CONFLICT_FIELDS = ("entity_type", "entity_code", "severity", "issue", "evidence")
PERMISSION_FIELDS = (
    "candidate_key", "data_file_id", "file_code", "current_effective_access_level",
    "current_policy_reason", "proposed_asset_access_level",
    "proposed_effective_access_level", "permission_comparison", "mapping_status", "issues",
)
CHECKSUM_FIELDS = (
    "data_file_id", "file_code", "is_current", "publication_status",
    "physical_status", "size_status", "checksum_algorithm", "checksum_status",
    "mapping_status", "issues",
)
REPORT_NAMES = {
    "summary": "dataasset_t4_summary.tsv",
    "assets": "dataasset_t4_assets.tsv",
    "memberships": "dataasset_t4_memberships.tsv",
    "contexts": "dataasset_t4_contexts.tsv",
    "exclusions": "dataasset_t4_exclusions.tsv",
    "conflicts": "dataasset_t4_conflicts.tsv",
    "permissions": "dataasset_t4_permissions.tsv",
    "checksums": "dataasset_t4_checksums.tsv",
}
REPORT_FIELDS = {
    "summary": SUMMARY_FIELDS,
    "assets": ASSET_FIELDS,
    "memberships": MEMBERSHIP_FIELDS,
    "contexts": CONTEXT_FIELDS,
    "exclusions": EXCLUSION_FIELDS,
    "conflicts": CONFLICT_FIELDS,
    "permissions": PERMISSION_FIELDS,
    "checksums": CHECKSUM_FIELDS,
}

REFERENCE_PROFILE = ("sequence", "reference_genome")
REFERENCE_ROLE_MAP = {
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
UNREGISTERED_ROLE_PROFILES = {
    "annotation": "feature/genome_annotation",
    "annotation_gff": "feature/genome_annotation",
    "annotation_gff3": "feature/genome_annotation",
    "annotation_gtf": "feature/genome_annotation",
    "gff": "feature/genome_annotation",
    "gff3": "feature/genome_annotation",
    "gtf": "feature/genome_annotation",
    "raw_data": "sequence/raw_read_set",
    "raw_reads": "sequence/raw_read_set",
    "fastq": "sequence/raw_read_set",
    "fq": "sequence/raw_read_set",
    "expression_matrix": "matrix/expression_matrix",
    "transcriptome_matrix": "matrix/expression_matrix",
    "contact_matrix": "matrix/contact_matrix",
    "hic_contact_matrix": "matrix/contact_matrix",
    "population": "feature/genomic_region_set",
    "variant": "feature/genomic_region_set",
    "centromere": "feature/genomic_region_set",
    "te": "feature/genomic_region_set",
    "tes": "feature/genomic_region_set",
    "core_blocks": "feature/genomic_region_set",
    "coreblocks": "feature/genomic_region_set",
    "mirna": "feature/genomic_region_set",
    "trna": "feature/genomic_region_set",
    "rrna": "feature/genomic_region_set",
    "ncrna": "feature/genomic_region_set",
    "codon_usage_result": "table/codon_usage_result",
}


class Command(BaseCommand):
    help = "Write a strictly read-only T4 professional-entity DataAsset candidate audit."

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

        registry = load_data_asset_registry()
        with transaction.atomic():
            snapshot = self.load_database_snapshot()
        reports = self.collect_reports(registry, snapshot)

        for name, path in paths.items():
            write_tsv(path, REPORT_FIELDS[name], reports[name])

        self.stdout.write("mode\tREAD_ONLY_DRY_RUN")
        for name in REPORT_NAMES:
            self.stdout.write(f"{name}\t{len(reports[name])}\t{paths[name]}")

    def load_database_snapshot(self):
        target_table_available = "data_asset" in connection.introspection.table_names()
        return {
            "datasets": list(
                Dataset.objects.select_related("project").order_by("dataset_code", "id")
            ),
            "data_files": list(
                DataFile.objects.select_related("dataset").order_by("file_code", "id")
            ),
            "relations": list(FileRelation.objects.select_related("file").order_by("id")),
            "dataset_links": list(
                DatasetAccession.objects.select_related("dataset", "dataset__project").order_by(
                    "dataset__dataset_code", "id"
                )
            ),
            "assemblies": list(Assembly.objects.select_related("accession").order_by("id")),
            "existing_assets": self.load_existing_assets() if target_table_available else {},
            "target_table_available": target_table_available,
        }

    def collect_reports(self, registry, snapshot):
        profile = registry.get_profile(*REFERENCE_PROFILE)
        datasets = snapshot["datasets"]
        data_files = snapshot["data_files"]
        relations = snapshot["relations"]
        dataset_links = snapshot["dataset_links"]

        datasets_by_accession = defaultdict(list)
        for link in dataset_links:
            if link.dataset.dataset_type == "genome":
                datasets_by_accession[link.accession_id].append(link.dataset)

        checksums = [self.audit_file(data_file) for data_file in data_files]
        checksum_by_file = {row["data_file_id"]: row for row in checksums}
        conflicts = []
        files_by_checksum = defaultdict(list)
        for data_file in data_files:
            digest = (data_file.sha256 or "").strip().lower()
            if len(digest) == 64 and all(char in "0123456789abcdef" for char in digest):
                files_by_checksum[digest].append(data_file)
        for matching_files in files_by_checksum.values():
            if len(matching_files) < 2:
                continue
            verified_codes = [
                data_file.file_code
                for data_file in matching_files
                if checksum_by_file[data_file.id]["checksum_status"] == "verified"
            ]
            if len(verified_codes) >= 2:
                for file_code in sorted(verified_codes):
                    conflicts.append(
                        self.conflict(
                            "data_file", file_code, "review", "duplicate_content_checksum",
                            f"matching_file_count={len(verified_codes)}",
                        )
                    )
            if len(verified_codes) != len(matching_files):
                for file_code in sorted(data_file.file_code for data_file in matching_files):
                    conflicts.append(
                        self.conflict(
                            "data_file", file_code, "review", "duplicate_recorded_checksum",
                            f"matching_file_count={len(matching_files)}",
                        )
                    )
        relations_by_assembly = defaultdict(list)
        assembly_ids_by_file = defaultdict(set)
        assembly_relation_ids = set()
        assembly_ids = set()

        for relation in relations:
            if relation.related_type != "assembly":
                continue
            try:
                assembly_id = int(relation.related_id)
            except (TypeError, ValueError):
                conflicts.append(
                    self.conflict(
                        "file_relation", relation.id, "blocked",
                        "invalid_assembly_relation_id", f"file={relation.file.file_code}",
                    )
                )
                continue
            assembly_ids.add(assembly_id)
            assembly_relation_ids.add(relation.id)
            relations_by_assembly[assembly_id].append(relation)
            assembly_ids_by_file[relation.file_id].add(assembly_id)

        all_assemblies = snapshot["assemblies"]
        assemblies = {
            assembly.id: assembly
            for assembly in all_assemblies
            if assembly.id in assembly_ids
        }
        for assembly in all_assemblies:
            if assembly.id not in assembly_ids:
                conflicts.append(
                    self.conflict(
                        "assembly", assembly.assembly_code or assembly.id, "review",
                        "assembly_without_file_relation", "",
                    )
                )
        for missing_id in sorted(assembly_ids - set(assemblies)):
            for relation in relations_by_assembly[missing_id]:
                conflicts.append(
                    self.conflict(
                        "file_relation", relation.id, "blocked", "missing_assembly",
                        f"assembly_id={missing_id}",
                    )
                )

        existing_assets = snapshot["existing_assets"]
        assets = []
        memberships = []
        contexts = []
        permissions = []
        represented_dataset_ids = set()
        mapped_file_ids = set()

        for assembly_id in sorted(assemblies):
            assembly = assemblies[assembly_id]
            result = self.build_reference_candidate(
                assembly,
                relations_by_assembly[assembly_id],
                datasets_by_accession[assembly.accession_id],
                assembly_ids_by_file,
                checksum_by_file,
                existing_assets,
                profile,
                registry,
            )
            assets.append(result["asset"])
            memberships.extend(result["memberships"])
            contexts.append(result["context"])
            permissions.extend(result["permissions"])
            conflicts.extend(result["conflicts"])
            represented_dataset_ids.update(result["represented_dataset_ids"])
            mapped_file_ids.update(row["data_file_id"] for row in result["memberships"])

        for relation in relations:
            if relation.id in assembly_relation_ids:
                continue
            role = self.normalized_role(relation.file_role)
            target_profile = self.unregistered_target_profile(role)
            if target_profile:
                conflicts.append(
                    self.conflict(
                        "data_file", relation.file.file_code, "review",
                        "profile_not_registered",
                        f"target_profile={target_profile};relation_id={relation.id}",
                    )
                )
            if "archive" in role or categorize_file_role(role) in {
                "transcriptome",
                "codon",
            }:
                conflicts.append(
                    self.conflict(
                        "data_file", relation.file.file_code, "review",
                        "archive_inspection_required", f"relation_id={relation.id}",
                    )
                )

        exclusions, exclusion_conflicts = self.build_exclusions(
            datasets, dataset_links, relations, data_files, represented_dataset_ids
        )
        conflicts.extend(exclusion_conflicts)

        for data_file in data_files:
            if data_file.id not in mapped_file_ids:
                permissions.append(self.unmapped_permission_row(data_file))

        reports = {
            "assets": sorted(assets, key=lambda row: row["candidate_key"]),
            "memberships": sorted(
                memberships,
                key=lambda row: (
                    row["candidate_key"], row["proposed_file_role"],
                    row["proposed_position"], row["file_code"],
                ),
            ),
            "contexts": sorted(
                contexts, key=lambda row: (row["candidate_key"], row["context_type"])
            ),
            "exclusions": exclusions,
            "conflicts": self.sorted_unique_conflicts(conflicts),
            "permissions": sorted(
                permissions, key=lambda row: (row["file_code"], row["candidate_key"])
            ),
            "checksums": checksums,
        }
        reports["summary"] = self.build_summary(reports)
        reports["summary"].append(
            {
                "metric": "target_table_available",
                "value": int(snapshot["target_table_available"]),
            }
        )
        return reports

    @staticmethod
    def load_existing_assets():
        if "data_asset" not in connection.introspection.table_names():
            return {}
        return {
            asset.asset_code: asset
            for asset in DataAsset.objects.select_related("project").order_by("id")
        }

    def build_reference_candidate(
        self, assembly, relations, supporting_datasets, assembly_ids_by_file,
        checksum_by_file, existing_assets, profile, registry,
    ):
        candidate_key = f"assembly:{assembly.id}"
        issues = []
        conflicts = []
        supporting_datasets = self.unique_models(supporting_datasets)
        supporting_codes = [dataset.dataset_code for dataset in supporting_datasets]
        selected_dataset = supporting_datasets[0] if len(supporting_datasets) == 1 else None
        if not supporting_datasets:
            issues.append(("blocked", "supporting_genome_dataset_missing"))
        elif len(supporting_datasets) > 1:
            issues.append(("blocked", "multiple_supporting_genome_datasets"))
        if selected_dataset is not None and selected_dataset.project_id is None:
            issues.append(("blocked", "supporting_dataset_project_missing"))
        if (
            selected_dataset is not None
            and selected_dataset.status == DataAsset.STATUS_RELEASED
        ):
            issues.append(("review", "released_candidate_requires_release_workflow"))

        proposed_asset_code = assembly.assembly_code or f"ASSEMBLY_{assembly.id}"
        asset_code_max_length = DataAsset._meta.get_field("asset_code").max_length
        if len(proposed_asset_code) > asset_code_max_length:
            issues.append(("blocked", "asset_code_too_long"))
            conflicts.append(
                self.conflict(
                    "assembly", assembly.assembly_code or assembly.id, "blocked",
                    "asset_code_too_long",
                    f"length={len(proposed_asset_code)};max_length={asset_code_max_length}",
                )
            )
        metadata = self.reference_metadata(assembly)
        role_relations = defaultdict(list)
        for relation in relations:
            role = REFERENCE_ROLE_MAP.get(self.normalized_role(relation.file_role))
            if role is None:
                conflicts.append(
                    self.conflict(
                        "data_file", relation.file.file_code, "review",
                        "file_role_not_allowed_by_reference_profile",
                        f"relation_id={relation.id};role={relation.file_role}",
                    )
                )
                continue
            role_relations[role].append(relation)

        membership_rows = []
        permission_rows = []
        for role in profile.file_role_rules:
            group = sorted(
                role_relations.get(role, []),
                key=lambda relation: (relation.file.file_code, relation.id),
            )
            for position, relation in enumerate(group):
                row_issues = []
                if len(assembly_ids_by_file[relation.file_id]) > 1:
                    row_issues.append("file_has_multiple_assembly_contexts")
                row_issues.extend(
                    self.split_values(checksum_by_file[relation.file_id]["issues"])
                )
                permission_row = self.permission_row(
                    candidate_key, relation.file, selected_dataset
                )
                permission_rows.append(permission_row)
                row_issues.extend(self.split_values(permission_row["issues"]))
                membership_rows.append(
                    {
                        "candidate_key": candidate_key,
                        "data_file_id": relation.file_id,
                        "file_code": relation.file.file_code,
                        "evidence_relation_ids": relation.id,
                        "proposed_file_role": role,
                        "file_role_class": profile.file_role_rules[role].role_class,
                        "proposed_position": position,
                        "proposed_is_primary": int(relation.is_primary),
                        "mapping_status": self.status_for_issues(row_issues),
                        "issues": ",".join(self.unique(row_issues)),
                    }
                )

        duplicate_file_ids = [
            file_id
            for file_id, count in Counter(
                row["data_file_id"] for row in membership_rows
            ).items()
            if count > 1
        ]
        if duplicate_file_ids:
            issues.append(("blocked", "file_has_multiple_asset_roles"))
        for role, group in role_relations.items():
            if sum(relation.is_primary for relation in group) > 1:
                issues.append(("review", f"multiple_primary_files:{role}"))

        try:
            registry.validate_asset_contract(
                profile.data_type_key,
                profile.profile_key,
                metadata=metadata,
                file_roles=[row["proposed_file_role"] for row in membership_rows],
                context_counts={"assembly": 1},
            )
        except DataAssetRegistryError as exc:
            issues.append(("blocked", "profile_contract_invalid"))
            conflicts.append(
                self.conflict(
                    "candidate", candidate_key, "blocked",
                    "profile_contract_invalid", str(exc),
                )
            )

        for row in membership_rows:
            if row["mapping_status"] == "blocked":
                issues.append(("blocked", "blocked_file_membership"))
            elif row["mapping_status"] == "review":
                issues.append(("review", "file_membership_requires_review"))

        project = selected_dataset.project if selected_dataset is not None else None
        mapping_action = "create"
        existing_asset = existing_assets.get(proposed_asset_code)
        if existing_asset is not None:
            if self.existing_asset_matches(existing_asset, project, profile):
                mapping_action = "existing_core_match"
                issues.append(("review", "existing_relations_require_review"))
            else:
                mapping_action = "existing_conflict"
                issues.append(("blocked", "existing_asset_conflict"))

        status = self.status_for_severity(issues)
        for row in membership_rows:
            if status == "blocked" and row["mapping_status"] != "blocked":
                row["mapping_status"] = "blocked"
                row["issues"] = self.append_issue(row["issues"], "asset_mapping_blocked")
        context = {
            "candidate_key": candidate_key,
            "context_type": "assembly",
            "context_id": assembly.id,
            "context_code": assembly.assembly_code or assembly.name,
            "evidence_source": "FileRelation(assembly)",
            "mapping_status": "blocked" if status == "blocked" else "ready",
            "issues": "asset_mapping_blocked" if status == "blocked" else "",
        }
        asset = {
            "candidate_key": candidate_key,
            "proposed_asset_code": proposed_asset_code,
            "mapping_action": mapping_action,
            "mapping_status": status,
            "evidence_source": "Assembly+FileRelation(assembly)",
            "supporting_dataset_codes": ",".join(sorted(supporting_codes)),
            "project_code": project.project_code if project else "",
            "proposed_name": assembly.display_name or assembly.assembly_name or assembly.name,
            "data_type_key": profile.data_type_key,
            "profile_key": profile.profile_key,
            "schema_version": profile.schema_version,
            "schema_digest": profile.schema_digest,
            "proposed_status": selected_dataset.status if selected_dataset else DataAsset.STATUS_DRAFT,
            "proposed_visibility": (
                selected_dataset.visibility if selected_dataset else DataAsset.VISIBILITY_PRIVATE
            ),
            "proposed_metadata": json.dumps(
                metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
            "version": (selected_dataset.version or "") if selected_dataset else "",
            "core_file_count": sum(
                row["file_role_class"] == "core" for row in membership_rows
            ),
            "auxiliary_file_count": sum(
                row["file_role_class"] == "auxiliary" for row in membership_rows
            ),
            "context_count": 1,
            "issues": ",".join(self.unique(issue for _, issue in issues)),
        }
        for severity, issue in self.unique(issues):
            conflicts.append(
                self.conflict("candidate", candidate_key, severity, issue, "")
            )
        return {
            "asset": asset,
            "memberships": membership_rows,
            "context": context,
            "permissions": permission_rows,
            "conflicts": conflicts,
            "represented_dataset_ids": {dataset.id for dataset in supporting_datasets},
        }

    def build_exclusions(
        self, datasets, dataset_links, relations, data_files, represented_dataset_ids
    ):
        direct_file_dataset_ids = {
            data_file.dataset_id for data_file in data_files if data_file.dataset_id
        }
        relation_dataset_ids = set()
        relation_accession_ids = set()
        for relation in relations:
            if relation.related_type not in {"dataset", "accession"}:
                continue
            try:
                related_id = int(relation.related_id)
            except (TypeError, ValueError):
                continue
            if relation.related_type == "dataset":
                relation_dataset_ids.add(related_id)
            else:
                relation_accession_ids.add(related_id)
        dataset_accession_ids = defaultdict(set)
        for link in dataset_links:
            dataset_accession_ids[link.dataset_id].add(link.accession_id)

        rows = []
        conflicts = []
        for dataset in datasets:
            if dataset.id in represented_dataset_ids:
                continue
            has_direct = dataset.id in direct_file_dataset_ids
            has_relation = dataset.id in relation_dataset_ids or bool(
                dataset_accession_ids[dataset.id].intersection(relation_accession_ids)
            )
            if dataset.dataset_type in {"transcriptome", "hic"} and not (
                has_direct or has_relation
            ):
                status = "excluded_not_asset"
                reason = "metadata_only_external_reference"
            elif not (has_direct or has_relation):
                status = "excluded_not_asset"
                reason = "no_core_payload_evidence"
            else:
                status = "review_required"
                reason = "no_professional_payload_candidate"
                conflicts.append(
                    self.conflict(
                        "dataset", dataset.dataset_code, "review", reason,
                        f"dataset_type={dataset.dataset_type}",
                    )
                )
            rows.append(
                {
                    "dataset_id": dataset.id,
                    "dataset_code": dataset.dataset_code,
                    "dataset_type": dataset.dataset_type,
                    "mapping_status": status,
                    "reason": reason,
                    "has_datafile_evidence": int(has_direct),
                    "has_file_relation_evidence": int(has_relation),
                }
            )
        return sorted(rows, key=lambda row: row["dataset_code"]), conflicts

    def permission_row(self, candidate_key, data_file, dataset):
        current_level, current_reason = resolve_datafile_access_level(data_file)
        asset_level = self.dataset_access_level(dataset)
        proposed_levels = [asset_level]
        if data_file.access_level != DataFile.ACCESS_LEVEL_INHERITED:
            proposed_levels.append(data_file.access_level)
        proposed_level = max(
            proposed_levels,
            key=lambda level: LEVEL_RANK.get(level, LEVEL_RANK[DataFile.ACCESS_LEVEL_PRIVATE]),
        )
        comparison = self.compare_access(current_level, proposed_level)
        issues = []
        if current_reason == "policy_integrity_error":
            issues.append("current_permission_integrity_error")
        if comparison == "widening":
            issues.append("permission_widening")
        elif comparison == "tightening":
            issues.append("permission_tightening")
        return {
            "candidate_key": candidate_key,
            "data_file_id": data_file.id,
            "file_code": data_file.file_code,
            "current_effective_access_level": current_level,
            "current_policy_reason": current_reason,
            "proposed_asset_access_level": asset_level,
            "proposed_effective_access_level": proposed_level,
            "permission_comparison": comparison,
            "mapping_status": self.status_for_issues(issues),
            "issues": ",".join(issues),
        }

    @staticmethod
    def unmapped_permission_row(data_file):
        current_level, current_reason = resolve_datafile_access_level(data_file)
        issues = []
        if current_reason == "policy_integrity_error":
            issues.append("current_permission_integrity_error")
        return {
            "candidate_key": "",
            "data_file_id": data_file.id,
            "file_code": data_file.file_code,
            "current_effective_access_level": current_level,
            "current_policy_reason": current_reason,
            "proposed_asset_access_level": "",
            "proposed_effective_access_level": "",
            "permission_comparison": "not_evaluated",
            "mapping_status": "blocked" if issues else "review",
            "issues": ",".join(issues or ["no_asset_candidate"]),
        }

    def audit_file(self, data_file):
        issues = []
        physical_status = "missing"
        size_status = "not_checked"
        checksum_status = "not_checked"
        path = Path(data_file.file_path) if data_file.file_path else None
        try:
            if path is not None and path.is_file():
                physical_status = "present"
                actual_size = path.stat().st_size
                if data_file.file_size is None:
                    size_status = "not_recorded"
                    issues.append("file_size_not_recorded")
                elif data_file.file_size == actual_size:
                    size_status = "verified"
                else:
                    size_status = "mismatch"
                    issues.append("file_size_mismatch")

                expected = (data_file.sha256 or "").strip().lower()
                if len(expected) == 64 and all(char in "0123456789abcdef" for char in expected):
                    checksum_status = "verified" if self.sha256(path) == expected else "mismatch"
                    if checksum_status == "mismatch":
                        issues.append("file_checksum_mismatch")
                else:
                    checksum_status = "not_recorded"
                    issues.append("file_checksum_unverified")
            else:
                issues.append("physical_file_missing")
        except OSError:
            physical_status = "unreadable"
            issues.append("physical_file_unreadable")

        if not data_file.is_current:
            issues.append("file_not_current")
        if data_file.publication_status != DataFile.PUBLICATION_RELEASED:
            issues.append("file_not_released")
        if data_file.published_at is None:
            issues.append("file_published_at_missing")
        return {
            "data_file_id": data_file.id,
            "file_code": data_file.file_code,
            "is_current": int(data_file.is_current),
            "publication_status": data_file.publication_status,
            "physical_status": physical_status,
            "size_status": size_status,
            "checksum_algorithm": "sha256",
            "checksum_status": checksum_status,
            "mapping_status": self.status_for_issues(issues),
            "issues": ",".join(self.unique(issues)),
        }

    @staticmethod
    def reference_metadata(assembly):
        metadata = {}
        if (assembly.assembly_method or "").strip():
            metadata["assembly_method"] = assembly.assembly_method.strip()
        if (assembly.sequencing_technology or "").strip():
            metadata["sequencing_platforms"] = [assembly.sequencing_technology.strip()]
        external_identifiers = {}
        for name, value in (
            ("assembly_accession", assembly.assembly_accession),
            ("bioproject", assembly.bio_project),
            ("standard_id", assembly.standard_id),
        ):
            if (value or "").strip():
                external_identifiers[name] = value.strip()
        if external_identifiers:
            metadata["external_identifiers"] = external_identifiers
        return metadata

    @staticmethod
    def existing_asset_matches(asset, project, profile):
        return all(
            (
                project is not None and asset.project_id == project.id,
                asset.data_type_key == profile.data_type_key,
                asset.profile_key == profile.profile_key,
                asset.schema_version == profile.schema_version,
                asset.schema_digest == profile.schema_digest,
            )
        )

    @staticmethod
    def dataset_access_level(dataset):
        if dataset is None or dataset.status != DataAsset.STATUS_RELEASED:
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
    def build_summary(reports):
        rows = []
        for name in (
            "assets", "memberships", "contexts", "exclusions",
            "conflicts", "permissions", "checksums",
        ):
            values = reports[name]
            rows.append({"metric": f"{name}_total", "value": len(values)})
            if values and "mapping_status" in values[0]:
                counts = Counter(row["mapping_status"] for row in values)
                for status, count in sorted(counts.items()):
                    rows.append({"metric": f"{name}_status:{status}", "value": count})
        issue_counts = Counter(row["issue"] for row in reports["conflicts"])
        for issue, count in sorted(issue_counts.items()):
            rows.append({"metric": f"conflict:{issue}", "value": count})
        exclusion_counts = Counter(row["reason"] for row in reports["exclusions"])
        for reason, count in sorted(exclusion_counts.items()):
            rows.append({"metric": f"exclusion:{reason}", "value": count})
        return rows

    @staticmethod
    def conflict(entity_type, entity_code, severity, issue, evidence):
        return {
            "entity_type": entity_type,
            "entity_code": entity_code,
            "severity": severity,
            "issue": issue,
            "evidence": evidence,
        }

    @staticmethod
    def sorted_unique_conflicts(rows):
        unique = {
            (
                str(row["entity_type"]), str(row["entity_code"]), row["severity"],
                row["issue"], row["evidence"],
            ): row
            for row in rows
        }
        return [unique[key] for key in sorted(unique)]

    @staticmethod
    def status_for_severity(issues):
        severities = {severity for severity, _ in issues}
        if "blocked" in severities:
            return "blocked"
        if "review" in severities:
            return "review"
        return "ready"

    @staticmethod
    def status_for_issues(issues):
        blocking = {
            "physical_file_missing", "physical_file_unreadable", "file_size_mismatch",
            "file_checksum_mismatch", "file_has_multiple_assembly_contexts",
            "current_permission_integrity_error", "permission_widening",
        }
        return "blocked" if blocking.intersection(issues) else ("review" if issues else "ready")

    @staticmethod
    def normalized_role(value):
        return (value or "").strip().lower()

    @staticmethod
    def unregistered_target_profile(role):
        if "archive" in role:
            return None
        return UNREGISTERED_ROLE_PROFILES.get(role)

    @staticmethod
    def split_values(value):
        return [item for item in (value or "").split(",") if item]

    @staticmethod
    def unique(values):
        return list(dict.fromkeys(values))

    @staticmethod
    def unique_models(values):
        return list({value.id: value for value in values}.values())

    @staticmethod
    def append_issue(existing, issue):
        return ",".join(Command.unique(Command.split_values(existing) + [issue]))

    @staticmethod
    def sha256(path):
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
