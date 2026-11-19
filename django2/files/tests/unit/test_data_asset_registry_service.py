from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from files.services.data_asset_registry_service import (
    DataAssetMetadataError,
    DataAssetProfileNotFound,
    DataAssetRegistryError,
    load_data_asset_registry,
)


class DataAssetRegistryServiceTests(SimpleTestCase):
    def test_packaged_registry_uses_v2_stable_categories(self):
        registry = load_data_asset_registry()

        self.assertEqual(registry.registry_version, "2")
        self.assertEqual(
            registry.profile_keys,
            (
                ("image", "microscopy_image_set"),
                ("sequence", "reference_genome"),
                ("table", "research_table"),
            ),
        )
        reference = registry.get_profile("sequence", "reference_genome")
        self.assertEqual(reference.schema_version, "2.0.0")
        self.assertEqual(reference.file_role_rules["genome_fasta"].role_class, "core")
        self.assertEqual(reference.context_rules["assembly"].minimum, 1)
        self.assertRegex(reference.schema_digest, r"^[0-9a-f]{64}$")

    def test_metadata_and_file_roles_are_validated_by_profile(self):
        registry = load_data_asset_registry()

        registry.validate_metadata(
            "image",
            "microscopy_image_set",
            {"instrument": "confocal-1", "pixel_size": {"value": 0.5, "unit": "um"}},
        )
        registry.validate_file_role("image", "microscopy_image_set", "primary_image")
        with self.assertRaisesRegex(DataAssetMetadataError, "Additional properties"):
            registry.validate_metadata(
                "image", "microscopy_image_set", {"unknown": "value"}
            )
        with self.assertRaisesRegex(DataAssetRegistryError, "Unknown file role"):
            registry.validate_file_role(
                "image", "microscopy_image_set", "genome_fasta"
            )

    def test_returned_metadata_schema_cannot_mutate_cached_contract(self):
        registry = load_data_asset_registry()
        profile = registry.get_profile("table", "research_table")
        original_digest = profile.schema_digest

        exposed_schema = profile.metadata_schema
        exposed_schema["additionalProperties"] = True

        self.assertEqual(profile.schema_digest, original_digest)
        self.assertFalse(profile.metadata_schema["additionalProperties"])
        with self.assertRaisesRegex(DataAssetMetadataError, "Additional properties"):
            registry.validate_metadata(
                "table",
                "research_table",
                {"unexpected": True},
            )

    def test_canonical_contract_enforces_file_and_context_cardinality(self):
        registry = load_data_asset_registry()

        registry.validate_asset_contract(
            "sequence",
            "reference_genome",
            metadata={},
            file_roles=["genome_fasta", "fasta_index"],
            context_counts={"assembly": 1},
        )
        invalid_cases = (
            ([], {"assembly": 1}, "requires at least 1"),
            (["fasta_index"], {"assembly": 1}, "requires at least 1"),
            (["genome_fasta", "genome_fasta"], {"assembly": 1}, "at most 1"),
            (["genome_fasta"], {}, "Context assembly requires"),
            (["genome_fasta"], {"sample": 1}, "not allowed"),
        )
        for file_roles, context_counts, message in invalid_cases:
            with self.subTest(file_roles=file_roles, context_counts=context_counts):
                with self.assertRaisesRegex(DataAssetRegistryError, message):
                    registry.validate_asset_contract(
                        "sequence",
                        "reference_genome",
                        metadata={},
                        file_roles=file_roles,
                        context_counts=context_counts,
                    )

    def test_unbounded_core_role_supports_multiple_files_without_code_branch(self):
        registry = self._load_temporary(self._base_registry())

        registry.validate_asset_contract(
            "table",
            "generic_files",
            metadata={},
            file_roles=["payload", "payload"],
            context_counts={},
        )

    def test_old_profile_keys_and_non_object_metadata_fail_closed(self):
        registry = load_data_asset_registry()

        for old_key in (
            ("genome", "reference_genome"),
            ("microscopy", "image_set"),
            ("tabular", "research_table"),
        ):
            with self.subTest(old_key=old_key):
                with self.assertRaises(DataAssetProfileNotFound):
                    registry.get_profile(*old_key)
        with self.assertRaisesRegex(DataAssetMetadataError, "JSON object"):
            registry.validate_metadata("sequence", "reference_genome", [])

    def test_registry_rejects_duplicate_profiles_and_invalid_schema(self):
        duplicate = self._base_registry()
        duplicate["profiles"].append(dict(duplicate["profiles"][0]))
        with self.assertRaisesRegex(DataAssetRegistryError, "Duplicate DataAsset profile"):
            self._load_temporary(duplicate)

        invalid_schema = self._base_registry()
        invalid_schema["profiles"][0]["metadata_schema"] = {"type": "not-a-json-type"}
        with self.assertRaisesRegex(DataAssetRegistryError, "Invalid JSON Schema"):
            self._load_temporary(invalid_schema)

    def test_registry_rejects_invalid_v2_rules(self):
        invalid_registries = []

        invalid_class = self._base_registry()
        invalid_class["profiles"][0]["file_role_rules"]["payload"]["class"] = "main"
        invalid_registries.append(invalid_class)

        boolean_min = self._base_registry()
        boolean_min["profiles"][0]["file_role_rules"]["payload"]["min"] = True
        invalid_registries.append(boolean_min)

        reversed_range = self._base_registry()
        reversed_range["profiles"][0]["file_role_rules"]["payload"].update(
            {"min": 2, "max": 1}
        )
        invalid_registries.append(reversed_range)

        no_required_core = self._base_registry()
        no_required_core["profiles"][0]["file_role_rules"]["payload"].update(
            {"class": "auxiliary", "min": 0}
        )
        invalid_registries.append(no_required_core)

        unknown_context = self._base_registry()
        unknown_context["profiles"][0]["context_rules"] = {
            "organism": {"min": 0, "max": 1}
        }
        invalid_registries.append(unknown_context)

        invalid_context_range = self._base_registry()
        invalid_context_range["profiles"][0]["context_rules"] = {
            "sample": {"min": 2, "max": 1}
        }
        invalid_registries.append(invalid_context_range)

        legacy_field = self._base_registry()
        legacy_field["profiles"][0]["file_roles"] = ["payload"]
        invalid_registries.append(legacy_field)

        unsupported_data_type = self._base_registry()
        unsupported_data_type["profiles"][0]["data_type_key"] = "proteomics"
        invalid_registries.append(unsupported_data_type)

        for index, registry_data in enumerate(invalid_registries):
            with self.subTest(index=index):
                with self.assertRaises(DataAssetRegistryError):
                    self._load_temporary(registry_data)

    def test_digest_covers_the_complete_profile_contract(self):
        registries = []
        base = self._base_registry()
        registries.append(base)

        metadata_change = deepcopy(base)
        metadata_change["profiles"][0]["metadata_schema"]["properties"] = {
            "label": {"type": "string"}
        }
        registries.append(metadata_change)

        file_rule_change = deepcopy(base)
        file_rule_change["profiles"][0]["file_role_rules"]["payload"]["max"] = 2
        registries.append(file_rule_change)

        context_rule_change = deepcopy(base)
        context_rule_change["profiles"][0]["context_rules"] = {
            "sample": {"min": 0, "max": None}
        }
        registries.append(context_rule_change)

        version_change = deepcopy(base)
        version_change["profiles"][0]["schema_version"] = "2.0.1"
        registries.append(version_change)

        type_change = deepcopy(base)
        type_change["profiles"][0]["data_type_key"] = "matrix"
        registries.append(type_change)

        profile_change = deepcopy(base)
        profile_change["profiles"][0]["profile_key"] = "generic_payload"
        registries.append(profile_change)

        loaded = (self._load_temporary(data) for data in registries)
        digests = {
            registry.get_profile(*registry.profile_keys[0]).schema_digest
            for registry in loaded
        }
        self.assertEqual(len(digests), len(registries))

    def test_new_profile_is_loaded_without_a_model_or_code_branch(self):
        registry_data = self._base_registry()
        registry_data["profiles"].append(
            {
                "data_type_key": "matrix",
                "profile_key": "protein_abundance",
                "schema_version": "1.0.0",
                "deprecated": False,
                "replacement": None,
                "file_role_rules": {
                    "abundance_matrix": {"class": "core", "min": 1, "max": 1}
                },
                "context_rules": {"sample": {"min": 0, "max": None}},
                "metadata_schema": {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "type": "object",
                    "properties": {"quantification": {"type": "string"}},
                    "additionalProperties": False,
                },
            }
        )

        registry = self._load_temporary(registry_data)
        registry.validate_asset_contract(
            "matrix",
            "protein_abundance",
            metadata={"quantification": "LFQ"},
            file_roles=["abundance_matrix"],
            context_counts={"sample": 2},
        )

    @staticmethod
    def _base_registry():
        return {
            "registry_version": "2",
            "profiles": [
                {
                    "data_type_key": "table",
                    "profile_key": "generic_files",
                    "schema_version": "1.0.0",
                    "deprecated": False,
                    "replacement": None,
                    "file_role_rules": {
                        "payload": {"class": "core", "min": 1, "max": None}
                    },
                    "context_rules": {},
                    "metadata_schema": {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False,
                    },
                }
            ],
        }

    @staticmethod
    def _load_temporary(registry_data):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            path.write_text(json.dumps(registry_data), encoding="utf-8")
            return load_data_asset_registry(path)
