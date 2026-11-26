from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from files.services.data_asset_registry_service import (
    ContextProfileNotFound,
    DataAssetMetadataError,
    DataAssetProfileNotFound,
    DataAssetRegistryError,
    load_data_asset_registry,
)


class DataAssetRegistryServiceTests(SimpleTestCase):
    LEGACY_DIGESTS = {
        ("image", "microscopy_image_set", "2.0.0"):
            "60ff369a7020c555237a7dbe201f2a5aecb1c816cee8e6f97aaca679b8903b85",
        ("sequence", "reference_genome", "2.0.0"):
            "f17ad183e42b3aa5bb05d0439e3f1579833501c30374459a65e2883be2e0fb9f",
        ("table", "research_table", "2.0.0"):
            "3d1c55d57910354b2e52d98bfd2a6d02b0503960a2684d26ec12cf2bf8958c9e",
    }

    def test_packaged_registry_loads_all_registry_kinds(self):
        registry = load_data_asset_registry()

        self.assertEqual(registry.registry_version, "3")
        self.assertEqual(
            registry.profile_keys,
            (
                ("image", "microscopy_image_set"),
                ("sequence", "reference_genome"),
                ("table", "research_table"),
            ),
        )
        self.assertEqual(
            registry.context_profile_keys,
            (
                ("experiment", "basic_experiment"),
                ("sample", "basic_sample"),
                ("subject", "basic_subject"),
            ),
        )
        self.assertIn("uses_reference", registry.relation_keys)
        self.assertIn("biosample", registry.namespace_keys)

    def test_legacy_profile_digests_remain_stable_and_exactly_resolvable(self):
        registry = load_data_asset_registry()

        for key, digest in self.LEGACY_DIGESTS.items():
            with self.subTest(key=key):
                profile = registry.resolve_exact_asset_profile(*key, digest)
                self.assertEqual(profile.schema_digest, digest)
        reference = registry.get_profile("sequence", "reference_genome")
        self.assertEqual(reference.schema_version, "2.0.0")
        self.assertEqual(reference.context_rules["assembly"].minimum, 1)

    def test_target_profile_is_registered_without_becoming_current_early(self):
        registry = load_data_asset_registry()
        target = registry.resolve_exact_asset_profile(
            "sequence",
            "reference_genome",
            "3.0.0",
            "faaaa4b727965afe3fd535a4d883e77a0005fa728489aec5eaffcf9c52ef802b",
        )

        self.assertEqual(target.profile_family, "reference_genome")
        self.assertNotIn("external_identifiers", target.metadata_schema["properties"])
        self.assertIn("supersedes", target.outgoing_relations)
        self.assertEqual(
            registry.get_profile("sequence", "reference_genome").schema_version,
            "2.0.0",
        )

    def test_exact_resolution_fails_closed_for_unknown_version_or_digest(self):
        registry = load_data_asset_registry()

        with self.assertRaises(DataAssetProfileNotFound):
            registry.resolve_exact_asset_profile(
                "sequence", "reference_genome", "99.0.0", "0" * 64
            )
        with self.assertRaisesRegex(DataAssetRegistryError, "digest mismatch"):
            registry.resolve_exact_asset_profile(
                "sequence", "reference_genome", "2.0.0", "0" * 64
            )
        with self.assertRaises(ContextProfileNotFound):
            registry.resolve_exact_context_profile(
                "sample", "missing", "1.0.0", "0" * 64
            )

    def test_metadata_file_roles_and_legacy_contexts_remain_validated(self):
        registry = load_data_asset_registry()

        registry.validate_asset_contract(
            "sequence",
            "reference_genome",
            metadata={},
            file_roles=["genome_fasta", "fasta_index"],
            context_counts={"assembly": 1},
        )
        with self.assertRaisesRegex(DataAssetMetadataError, "Additional properties"):
            registry.validate_metadata(
                "image", "microscopy_image_set", {"unknown": "value"}
            )
        with self.assertRaisesRegex(DataAssetRegistryError, "requires at least 1"):
            registry.validate_asset_contract(
                "sequence", "reference_genome", metadata={},
                file_roles=["fasta_index"], context_counts={"assembly": 1},
            )
        with self.assertRaisesRegex(DataAssetRegistryError, "not allowed"):
            registry.validate_asset_contract(
                "sequence", "reference_genome", metadata={},
                file_roles=["genome_fasta"], context_counts={"sample": 1},
            )

    def test_returned_metadata_schema_cannot_mutate_cached_contract(self):
        profile = load_data_asset_registry().get_profile("table", "research_table")
        original_digest = profile.schema_digest

        exposed_schema = profile.metadata_schema
        exposed_schema["additionalProperties"] = True

        self.assertEqual(profile.schema_digest, original_digest)
        self.assertFalse(profile.metadata_schema["additionalProperties"])

    def test_namespace_normalizes_and_validates_without_dynamic_code(self):
        registry = load_data_asset_registry()
        biosample = registry.resolve_current_namespace("biosample")

        self.assertEqual(biosample.normalize("  samn12345 "), "SAMN12345")
        with self.assertRaisesRegex(DataAssetRegistryError, "does not match"):
            biosample.normalize("not-a-biosample")
        self.assertIs(
            registry.resolve_exact_namespace(
                biosample.key, biosample.version, biosample.digest
            ),
            biosample,
        )

    def test_context_public_fields_and_relation_targets_are_registered(self):
        registry = load_data_asset_registry()
        sample = registry.resolve_current_context_profile("sample", "basic_sample")
        collected_from = registry.resolve_current_relation("collected_from")

        self.assertEqual(sample.public_metadata_fields, ("scientific_name", "tissue"))
        self.assertEqual(
            sample.outgoing_relations["collected_from"].allowed_target_profiles,
            ("subject/basic_subject",),
        )
        self.assertTrue(collected_from.acyclic)
        self.assertEqual(collected_from.cross_project_policy, "same_project")

    def test_dynamic_asset_and_context_types_need_no_python_enumeration(self):
        package = self._base_package()
        asset_data = package["asset_profiles.json"]
        asset_data["current_versions"] = {"proteomics/protein_abundance": "1.0.0"}
        asset_data["entries"][0].update(
            {
                "data_type_key": "proteomics",
                "profile_key": "protein_abundance",
                "context_link_rules": {
                    "source_sample": {
                        "allowed_target_profiles": ["biospecimen/core_biospecimen"],
                        "min": 0,
                        "max": None,
                    }
                },
            }
        )
        context_data = package["context_profiles.json"]
        context_data["current_versions"] = {"biospecimen/core_biospecimen": "1.0.0"}
        context_data["entries"][0].update(
            {"context_type_key": "biospecimen", "profile_key": "core_biospecimen"}
        )

        registry = self._load_temporary(package)

        self.assertEqual(
            registry.get_profile("proteomics", "protein_abundance").data_type_key,
            "proteomics",
        )
        self.assertEqual(
            registry.resolve_current_context_profile(
                "biospecimen", "core_biospecimen"
            ).context_type_key,
            "biospecimen",
        )

    def test_package_rejects_duplicate_version_invalid_current_and_unknown_fields(self):
        duplicate = self._base_package()
        duplicate["asset_profiles.json"]["entries"].append(
            deepcopy(duplicate["asset_profiles.json"]["entries"][0])
        )
        with self.assertRaisesRegex(DataAssetRegistryError, "Duplicate registry entry"):
            self._load_temporary(duplicate)

        missing_current = self._base_package()
        missing_current["asset_profiles.json"]["current_versions"][
            "table/generic_files"
        ] = "2.0.0"
        with self.assertRaisesRegex(DataAssetRegistryError, "does not exist"):
            self._load_temporary(missing_current)

        unknown = self._base_package()
        unknown["namespace_registry.json"]["entries"][0]["custom_code"] = "unsafe"
        with self.assertRaisesRegex(DataAssetRegistryError, "Unknown field"):
            self._load_temporary(unknown)

    def test_digest_changes_with_complete_extended_contract(self):
        base = self._base_package()
        baseline = self._load_temporary(base).get_profile("table", "generic_files")
        changed = deepcopy(base)
        changed["asset_profiles.json"]["entries"][0]["public_metadata_fields"] = [
            "label"
        ]
        changed["asset_profiles.json"]["entries"][0]["metadata_schema"][
            "properties"
        ] = {"label": {"type": "string"}}
        updated = self._load_temporary(changed).get_profile("table", "generic_files")

        self.assertNotEqual(baseline.schema_digest, updated.schema_digest)

    @staticmethod
    def _base_package():
        return {
            "asset_profiles.json": {
                "registry_version": "3",
                "current_versions": {"table/generic_files": "1.0.0"},
                "entries": [
                    {
                        "data_type_key": "table",
                        "profile_key": "generic_files",
                        "profile_family": "generic_files",
                        "schema_version": "1.0.0",
                        "deprecated": False,
                        "replacement": None,
                        "file_role_rules": {
                            "payload": {"class": "core", "min": 1, "max": None}
                        },
                        "context_rules": {},
                        "context_link_rules": {},
                        "outgoing_relations": {},
                        "public_metadata_fields": [],
                        "metadata_schema": {
                            "$schema": "https://json-schema.org/draft/2020-12/schema",
                            "type": "object",
                            "properties": {},
                            "additionalProperties": False,
                        },
                    }
                ],
            },
            "context_profiles.json": {
                "registry_version": "3",
                "current_versions": {"sample/basic_sample": "1.0.0"},
                "entries": [
                    {
                        "context_type_key": "sample",
                        "profile_key": "basic_sample",
                        "profile_family": "sample",
                        "schema_version": "1.0.0",
                        "deprecated": False,
                        "replacement": None,
                        "outgoing_relations": {},
                        "public_metadata_fields": [],
                        "metadata_schema": {
                            "$schema": "https://json-schema.org/draft/2020-12/schema",
                            "type": "object",
                            "properties": {},
                            "additionalProperties": False,
                        },
                    }
                ],
            },
            "relation_registry.json": {
                "registry_version": "3",
                "current_versions": {"source_sample": "1.0.0"},
                "entries": [
                    {
                        "key": "source_sample",
                        "version": "1.0.0",
                        "deprecated": False,
                        "replacement": None,
                        "source_kind": "data_asset",
                        "target_kind": "context",
                        "directed": True,
                        "self_link": "forbidden",
                        "acyclic": False,
                        "cross_project_policy": "same_project",
                        "same_profile_family": False,
                        "outgoing_max": None,
                        "incoming_max": None,
                    }
                ],
            },
            "namespace_registry.json": {
                "registry_version": "3",
                "current_versions": {"local_id": "1.0.0"},
                "entries": [
                    {
                        "key": "local_id",
                        "version": "1.0.0",
                        "name": "Local test identifier",
                        "deprecated": False,
                        "replacement": None,
                        "pattern": "^[A-Z0-9]+$",
                        "normalization": "strip_uppercase",
                        "resolver_url_template": "https://example.test/{value}",
                        "allowed_target_kinds": ["data_asset"],
                        "allowed_context_types": [],
                    }
                ],
            },
        }

    @staticmethod
    def _load_temporary(package):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for name, data in package.items():
                (root / name).write_text(json.dumps(data), encoding="utf-8")
            return load_data_asset_registry(root)
