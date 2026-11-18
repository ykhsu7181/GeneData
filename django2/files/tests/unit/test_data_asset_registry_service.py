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
    def test_packaged_registry_supports_three_general_data_categories(self):
        registry = load_data_asset_registry()

        self.assertEqual(
            registry.profile_keys,
            (
                ("genome", "reference_genome"),
                ("microscopy", "image_set"),
                ("tabular", "research_table"),
            ),
        )
        for key in registry.profile_keys:
            profile = registry.get_profile(*key)
            self.assertRegex(profile.schema_digest, r"^[0-9a-f]{64}$")

    def test_metadata_and_file_roles_are_validated_by_profile(self):
        registry = load_data_asset_registry()

        profile = registry.validate_metadata(
            "microscopy",
            "image_set",
            {"instrument": "confocal-1", "pixel_size": {"value": 0.5, "unit": "um"}},
        )

        self.assertEqual(profile.schema_version, "1.0.0")
        registry.validate_file_role("microscopy", "image_set", "primary_image")
        with self.assertRaisesRegex(DataAssetMetadataError, "Additional properties"):
            registry.validate_metadata("microscopy", "image_set", {"unknown": "value"})
        with self.assertRaisesRegex(DataAssetRegistryError, "Unknown file role"):
            registry.validate_file_role("microscopy", "image_set", "genome_fasta")

    def test_unknown_profile_and_non_object_metadata_fail_closed(self):
        registry = load_data_asset_registry()

        with self.assertRaises(DataAssetProfileNotFound):
            registry.get_profile("unknown", "unknown")
        with self.assertRaisesRegex(DataAssetMetadataError, "JSON object"):
            registry.validate_metadata("genome", "reference_genome", [])

    def test_registry_rejects_duplicate_profiles_and_invalid_schema(self):
        duplicate = self._base_registry()
        duplicate["profiles"].append(dict(duplicate["profiles"][0]))
        with self.assertRaisesRegex(DataAssetRegistryError, "Duplicate DataAsset profile"):
            self._load_temporary(duplicate)

        invalid_schema = self._base_registry()
        invalid_schema["profiles"][0]["metadata_schema"] = {"type": "not-a-json-type"}
        with self.assertRaisesRegex(DataAssetRegistryError, "Invalid JSON Schema"):
            self._load_temporary(invalid_schema)

    def test_new_profile_is_loaded_without_a_model_or_code_branch(self):
        registry_data = self._base_registry()
        registry_data["profiles"].append(
            {
                "data_type_key": "proteomics",
                "profile_key": "protein_abundance",
                "schema_version": "1.0.0",
                "deprecated": False,
                "replacement": None,
                "file_roles": ["primary_table"],
                "metadata_schema": {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "type": "object",
                    "properties": {"quantification": {"type": "string"}},
                    "additionalProperties": False,
                },
            }
        )

        registry = self._load_temporary(registry_data)

        registry.validate_metadata(
            "proteomics", "protein_abundance", {"quantification": "LFQ"}
        )
        registry.validate_file_role("proteomics", "protein_abundance", "primary_table")

    @staticmethod
    def _base_registry():
        return {
            "registry_version": "1",
            "profiles": [
                {
                    "data_type_key": "generic",
                    "profile_key": "generic_files",
                    "schema_version": "1.0.0",
                    "deprecated": False,
                    "replacement": None,
                    "file_roles": ["primary_data"],
                    "metadata_schema": {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "type": "object",
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
