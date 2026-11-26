"""Canonical, non-secret content used only for CoreAuditEvent digests."""


def context_content_snapshot(context):
    return {
        "context_code": context.context_code,
        "profile": [
            context.context_type_key,
            context.profile_key,
            context.schema_version,
            context.schema_digest,
        ],
        "name": context.name,
        "description": context.description,
        "metadata": context.metadata,
        "relations": list(
            context.outgoing_context_relations.order_by(
                "relation_type", "target_context_id"
            ).values_list("relation_type", "target_context_id")
        ),
        "external_identifiers": list(
            context.external_identifiers.order_by(
                "namespace_key", "normalized_value"
            ).values_list("namespace_key", "normalized_value")
        ),
    }


def asset_content_snapshot(asset):
    return {
        "asset_code": asset.asset_code,
        "profile": [
            asset.data_type_key,
            asset.profile_key,
            asset.schema_version,
            asset.schema_digest,
        ],
        "name": asset.name,
        "version": asset.version,
        "visibility": asset.visibility,
        "description": asset.description,
        "metadata": asset.metadata,
        "files": list(
            asset.file_memberships.order_by("file_role", "position", "data_file_id").values_list(
                "data_file_id", "file_role", "position", "is_primary"
            )
        ),
        "asset_relations": list(
            asset.outgoing_asset_relations.order_by(
                "relation_type", "target_asset_id"
            ).values_list("relation_type", "target_asset_id")
        ),
        "context_links": list(
            asset.context_links.order_by("relation_type", "position", "context_id").values_list(
                "relation_type", "context_id", "position"
            )
        ),
        "external_identifiers": list(
            asset.external_identifiers.order_by(
                "namespace_key", "normalized_value"
            ).values_list("namespace_key", "normalized_value")
        ),
    }
