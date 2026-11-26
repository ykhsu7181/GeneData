"""ADR-005 unique write boundary for DataAsset draft content and lifecycle."""

import re
from collections import Counter
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.utils import timezone

from files.models import (
    AssetContextLink,
    AssetFileMembership,
    ContextEntity,
    DataAsset,
    DataAssetRelation,
    DataFile,
)
from files.services.core_audit_service import append_core_audit_event
from files.services.core_content_snapshot import asset_content_snapshot
from files.services.data_asset_lifecycle_policy import (
    LifecyclePolicyError,
    resolve_data_asset_transition,
)
from files.services.data_asset_registry_service import (
    DataAssetRegistryError,
    load_data_asset_registry,
)
from files.services.project_service import get_project_role, lock_project_for_core_write


class DataAssetServiceError(ValueError):
    """Raised when a requested DataAsset write violates domain rules."""


class DataAssetPermissionDenied(DataAssetServiceError):
    pass


class DataAssetConflictError(DataAssetServiceError):
    pass


@dataclass(frozen=True)
class AssetFileInput:
    data_file: object
    file_role: str
    position: int = 0
    is_primary: bool = False


@dataclass(frozen=True)
class AssetContextInput:
    context: object
    relation_type: str
    position: int = 0


@dataclass(frozen=True)
class AssetRelationInput:
    target_asset: object
    relation_type: str


def create_data_asset(
    *, asset_code, project, data_type_key, profile_key, created_by,
    metadata=None, file_memberships=(), context_links=(), asset_relations=(),
    name="", version=None, description="",
    visibility=DataAsset.VISIBILITY_PRIVATE, registry=None,
):
    """Create a legal, potentially incomplete draft without legacy relation writes."""
    asset_code = _required_text(asset_code, "asset_code")
    _require_create_permission(project, created_by)
    _validate_visibility(visibility)
    registry = registry or load_data_asset_registry()
    metadata = {} if metadata is None else metadata
    files = tuple(file_memberships)
    contexts = tuple(context_links)
    relations = tuple(asset_relations)
    try:
        profile = registry.resolve_current_asset_profile(data_type_key, profile_key)
        registry.validate_asset_profile_metadata(profile, metadata)
    except DataAssetRegistryError as exc:
        raise DataAssetServiceError(str(exc)) from exc
    if profile.deprecated:
        raise DataAssetServiceError("A deprecated DataAsset profile cannot be selected.")
    try:
        with transaction.atomic():
            lock_project_for_core_write(project.pk)
            _require_create_permission(project, created_by)
            relations = _lock_relation_inputs(relations)
            contexts = _lock_context_inputs(contexts)
            files = _lock_file_inputs(files)
            _validate_draft_contract(
                profile=profile, files=files, contexts=contexts, relations=relations,
                project=project, registry=registry, source_asset=None,
            )
            _reject_reused_profile_version(profile)
            asset = DataAsset.objects.create(
                asset_code=asset_code,
                name=name or "",
                project=project,
                data_type_key=profile.data_type_key,
                profile_key=profile.profile_key,
                schema_version=profile.schema_version,
                schema_digest=profile.schema_digest,
                version=version,
                visibility=visibility,
                metadata=metadata,
                description=description or "",
                created_by=created_by,
            )
            _replace_file_rows(asset, files, created_by)
            _replace_context_rows(asset, contexts, created_by, registry)
            _replace_relation_rows(asset, relations, created_by, registry)
            append_core_audit_event(
                project=project, actor=created_by, event_type="asset_created",
                asset=asset, to_value=DataAsset.STATUS_DRAFT,
                after_content=asset_content_snapshot(asset),
            )
            return asset
    except DataAssetServiceError:
        raise
    except IntegrityError as exc:
        raise DataAssetConflictError(
            "DataAsset creation violated a database invariant."
        ) from exc


def update_data_asset_draft(
    *, asset, actor, metadata=None, file_memberships=None, context_links=None,
    asset_relations=None, name=None, version=None, description=None,
    visibility=None, data_type_key=None, profile_key=None, registry=None,
):
    registry = registry or load_data_asset_registry()
    provided_files = None if file_memberships is None else tuple(file_memberships)
    provided_contexts = None if context_links is None else tuple(context_links)
    provided_relations = None if asset_relations is None else tuple(asset_relations)
    with transaction.atomic():
        lock_project_for_core_write(asset.project_id)
        asset_ids = {asset.pk}
        if provided_relations is not None:
            asset_ids.update(item.target_asset.pk for item in provided_relations)
        locked_assets = _lock_data_assets(asset_ids)
        locked = locked_assets[asset.pk]
        _require_edit_permission(locked, actor)
        if locked.status != DataAsset.STATUS_DRAFT:
            raise DataAssetConflictError("Only a draft DataAsset can be edited.")
        before = asset_content_snapshot(locked)
        next_type = data_type_key or locked.data_type_key
        next_profile_key = profile_key or locked.profile_key
        next_metadata = locked.metadata if metadata is None else metadata
        try:
            if (next_type, next_profile_key) == (locked.data_type_key, locked.profile_key):
                profile = registry.resolve_exact_asset_profile(
                    locked.data_type_key, locked.profile_key,
                    locked.schema_version, locked.schema_digest,
                )
            else:
                profile = registry.resolve_current_asset_profile(next_type, next_profile_key)
                if profile.deprecated:
                    raise DataAssetServiceError(
                        "A deprecated DataAsset profile cannot be selected."
                    )
                _reject_reused_profile_version(profile)
            registry.validate_asset_profile_metadata(profile, next_metadata)
        except DataAssetRegistryError as exc:
            raise DataAssetServiceError(str(exc)) from exc
        contexts = (
            _lock_context_inputs(provided_contexts)
            if provided_contexts is not None else _current_context_inputs(locked)
        )
        files = (
            _lock_file_inputs(provided_files)
            if provided_files is not None else _current_file_inputs(locked)
        )
        relations = (
            tuple(
                AssetRelationInput(locked_assets[item.target_asset.pk], item.relation_type)
                for item in provided_relations
            )
            if provided_relations is not None else _current_relation_inputs(locked)
        )
        _validate_draft_contract(
            profile=profile, files=files, contexts=contexts, relations=relations,
            project=locked.project, registry=registry, source_asset=locked,
        )
        locked.data_type_key = profile.data_type_key
        locked.profile_key = profile.profile_key
        locked.schema_version = profile.schema_version
        locked.schema_digest = profile.schema_digest
        locked.metadata = next_metadata
        if name is not None:
            locked.name = name or ""
        if version is not None:
            locked.version = version
        if description is not None:
            locked.description = description or ""
        if visibility is not None:
            _validate_visibility(visibility)
            locked.visibility = visibility
        locked.save(update_fields=[
            "data_type_key", "profile_key", "schema_version", "schema_digest",
            "metadata", "name", "version", "description", "visibility", "updated_at",
        ])
        if file_memberships is not None:
            _replace_file_rows(locked, files, actor)
        if context_links is not None:
            _replace_context_rows(locked, contexts, actor, registry)
        if asset_relations is not None:
            _replace_relation_rows(locked, relations, actor, registry)
        after = asset_content_snapshot(locked)
        if before == after:
            raise DataAssetServiceError("The DataAsset update has no effect.")
        append_core_audit_event(
            project=locked.project, actor=actor, event_type="asset_updated",
            asset=locked, before_content=before, after_content=after,
        )
        return locked


def transition_data_asset(*, asset, actor, action, reason="", registry=None):
    registry = registry or load_data_asset_registry()
    with transaction.atomic():
        lock_project_for_core_write(asset.project_id)
        target_ids = DataAssetRelation.objects.filter(
            source_asset_id=asset.pk
        ).values_list("target_asset_id", flat=True)
        locked_assets = _lock_data_assets({asset.pk, *target_ids})
        locked = locked_assets[asset.pk]
        _lock_non_asset_dependencies(locked)
        role = _require_project_role(locked.project, actor)
        try:
            rule = resolve_data_asset_transition(action, locked.status, role)
        except LifecyclePolicyError as exc:
            raise DataAssetPermissionDenied(str(exc)) from exc
        if rule.reason_required and not str(reason or "").strip():
            raise DataAssetServiceError("A reason is required for this transition.")
        if rule.validation_level in {"complete", "release"}:
            _validate_complete_asset(locked, registry, releasing=action == "release")
        if action == "archive":
            _reject_archive_when_referenced(locked)
        previous = locked.status
        locked.status = rule.target
        fields = ["status", "updated_at"]
        if action == "release":
            locked.published_at = timezone.now()
            fields.append("published_at")
        locked.save(update_fields=fields)
        append_core_audit_event(
            project=locked.project, actor=actor,
            event_type={
                "submit": "asset_submitted", "return": "asset_returned",
                "approve": "asset_approved", "withdraw_approval": "asset_approval_withdrawn",
                "release": "asset_released", "archive": "asset_archived",
            }[action],
            asset=locked, from_value=previous, to_value=rule.target, reason=reason,
        )
        return locked


def add_asset_relation(*, asset, target_asset, relation_type, actor, registry=None):
    with transaction.atomic():
        lock_project_for_core_write(asset.project_id)
        source = DataAsset.objects.get(pk=asset.pk)
        target = DataAsset.objects.get(pk=target_asset.pk)
        current = _current_relation_inputs(source)
        current.append(AssetRelationInput(target_asset=target, relation_type=relation_type))
        return update_data_asset_draft(
            asset=source, actor=actor, asset_relations=current, registry=registry
        ).outgoing_asset_relations.get(target_asset=target, relation_type=relation_type)


def remove_asset_relation(*, relation, actor, registry=None):
    with transaction.atomic():
        lock_project_for_core_write(relation.source_asset.project_id)
        source = DataAsset.objects.get(pk=relation.source_asset_id)
        locked_relation = DataAssetRelation.objects.select_for_update().get(pk=relation.pk)
        remaining = [
            item for item in _current_relation_inputs(source)
            if not (
                item.target_asset.pk == locked_relation.target_asset_id
                and item.relation_type == locked_relation.relation_type
            )
        ]
        update_data_asset_draft(
            asset=source, actor=actor, asset_relations=remaining, registry=registry
        )


def add_asset_context_link(*, asset, context, relation_type, actor, position=0, registry=None):
    with transaction.atomic():
        lock_project_for_core_write(asset.project_id)
        source = DataAsset.objects.get(pk=asset.pk)
        locked_context = ContextEntity.objects.get(pk=context.pk)
        current = _current_context_inputs(source)
        current.append(AssetContextInput(
            context=locked_context, relation_type=relation_type, position=position
        ))
        return update_data_asset_draft(
            asset=source, actor=actor, context_links=current, registry=registry
        ).context_links.get(context=locked_context, relation_type=relation_type)


def remove_asset_context_link(*, link, actor, registry=None):
    with transaction.atomic():
        lock_project_for_core_write(link.asset.project_id)
        source = DataAsset.objects.get(pk=link.asset_id)
        locked_link = AssetContextLink.objects.select_for_update().get(pk=link.pk)
        remaining = [
            item for item in _current_context_inputs(source)
            if not (
                item.context.pk == locked_link.context_id
                and item.relation_type == locked_link.relation_type
            )
        ]
        update_data_asset_draft(
            asset=source, actor=actor, context_links=remaining, registry=registry
        )


def _validate_draft_contract(*, profile, files, contexts, relations, project, registry, source_asset):
    _validate_file_inputs(files)
    _validate_context_inputs(contexts)
    _validate_relation_inputs(relations)
    _validate_counts(Counter(item.file_role for item in files), profile.file_role_rules, False, "file role")
    context_counts = Counter(item.relation_type for item in contexts)
    relation_counts = Counter(item.relation_type for item in relations)
    _validate_counts(context_counts, profile.context_link_rules, False, "Context link")
    _validate_counts(relation_counts, profile.outgoing_relations, False, "asset relation")
    for relation_type, count in {**context_counts, **relation_counts}.items():
        global_rule = registry.resolve_current_relation(relation_type)
        if global_rule.outgoing_max is not None and count > global_rule.outgoing_max:
            raise DataAssetServiceError(
                f"Relation {relation_type} allows at most {global_rule.outgoing_max}."
            )
    for item in contexts:
        _validate_context_link(profile, item, project, registry)
    for item in relations:
        _validate_asset_relation(profile, item, project, registry, source_asset)


def _validate_complete_asset(asset, registry, *, releasing):
    try:
        profile = registry.resolve_exact_asset_profile(
            asset.data_type_key, asset.profile_key, asset.schema_version, asset.schema_digest
        )
        registry.validate_asset_profile_metadata(profile, asset.metadata)
    except DataAssetRegistryError as exc:
        raise DataAssetServiceError(str(exc)) from exc
    files = _current_file_inputs(asset)
    contexts = _current_context_inputs(asset)
    relations = _current_relation_inputs(asset)
    _validate_draft_contract(
        profile=profile, files=files, contexts=contexts, relations=relations,
        project=asset.project, registry=registry, source_asset=asset,
    )
    _validate_counts(Counter(item.file_role for item in files), profile.file_role_rules, True, "file role")
    _validate_counts(Counter(item.relation_type for item in contexts), profile.context_link_rules, True, "Context link")
    _validate_counts(Counter(item.relation_type for item in relations), profile.outgoing_relations, True, "asset relation")
    for item in files:
        data_file = item.data_file
        if data_file.availability_status != DataFile.AVAILABILITY_AVAILABLE:
            raise DataAssetServiceError("Every DataAsset file must be physically available.")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", str(data_file.sha256 or "")):
            raise DataAssetServiceError("Every DataAsset file must have a SHA-256 checksum.")
    for item in contexts:
        if item.context.status != ContextEntity.STATUS_ACTIVE:
            raise DataAssetServiceError("Every required ContextEntity must be active.")
    for item in relations:
        if item.relation_type != "uses_reference":
            continue
        target = item.target_asset
        if target.project_id != asset.project_id:
            if target.status != DataAsset.STATUS_RELEASED or target.visibility != DataAsset.VISIBILITY_PUBLIC:
                raise DataAssetPermissionDenied("A cross-Project reference is not available.")
        elif releasing:
            if target.status != DataAsset.STATUS_RELEASED:
                raise DataAssetServiceError("Release requires released reference assets.")
        elif target.status not in {DataAsset.STATUS_APPROVED, DataAsset.STATUS_RELEASED}:
            raise DataAssetServiceError("Submission requires an approved reference asset.")


def _validate_context_link(profile, item, project, registry):
    context = ContextEntity.objects.get(pk=item.context.pk)
    if context.project_id != project.pk:
        raise DataAssetPermissionDenied("Asset and ContextEntity must belong to one Project.")
    if context.status == ContextEntity.STATUS_ARCHIVED:
        raise DataAssetConflictError(
            "An archived ContextEntity cannot be the target of a new asset link."
        )
    try:
        profile_rule = profile.context_link_rules[item.relation_type]
        relation_rule = registry.resolve_current_relation(item.relation_type)
        target_profile = registry.resolve_exact_context_profile(
            context.context_type_key, context.profile_key,
            context.schema_version, context.schema_digest,
        )
    except (KeyError, DataAssetRegistryError) as exc:
        raise DataAssetServiceError("The Context link is not allowed by the asset Profile.") from exc
    if (relation_rule.source_kind, relation_rule.target_kind) != ("data_asset", "context"):
        raise DataAssetServiceError("The relation does not connect an asset to ContextEntity.")
    if _profile_ref(target_profile) not in profile_rule.allowed_target_profiles:
        raise DataAssetServiceError("The target Context profile is not allowed.")


def _validate_asset_relation(profile, item, project, registry, source_asset):
    target = item.target_asset
    if source_asset is not None and target.pk == source_asset.pk:
        raise DataAssetServiceError("A DataAsset cannot relate to itself.")
    try:
        profile_rule = profile.outgoing_relations[item.relation_type]
        relation_rule = registry.resolve_current_relation(item.relation_type)
        target_profile = registry.resolve_exact_asset_profile(
            target.data_type_key, target.profile_key,
            target.schema_version, target.schema_digest,
        )
    except (KeyError, DataAssetRegistryError) as exc:
        raise DataAssetServiceError("The asset relation is not allowed by the Profile.") from exc
    if (relation_rule.source_kind, relation_rule.target_kind) != ("data_asset", "data_asset"):
        raise DataAssetServiceError("The relation does not connect DataAsset records.")
    if _profile_ref(target_profile) not in profile_rule.allowed_target_profiles:
        raise DataAssetServiceError("The target DataAsset profile is not allowed.")
    if relation_rule.same_profile_family and profile.profile_family != target_profile.profile_family:
        raise DataAssetServiceError("The relation requires one Profile family.")
    if target.project_id != project.pk:
        if relation_rule.cross_project_policy != "public_released_only":
            raise DataAssetPermissionDenied("The relation cannot cross Projects.")
        if target.status != DataAsset.STATUS_RELEASED or target.visibility != DataAsset.VISIBILITY_PUBLIC:
            raise DataAssetPermissionDenied("The cross-Project target is not public and released.")
    if relation_rule.incoming_max is not None:
        incoming = target.incoming_asset_relations.filter(relation_type=item.relation_type)
        if source_asset is not None:
            incoming = incoming.exclude(source_asset=source_asset)
        if incoming.count() >= relation_rule.incoming_max:
            raise DataAssetConflictError("The target relation maximum has been reached.")
    if relation_rule.acyclic and source_asset is not None:
        if _asset_path_exists(target.pk, source_asset.pk, item.relation_type):
            raise DataAssetConflictError("The asset relation would create a cycle.")


def _replace_file_rows(asset, items, actor):
    asset.file_memberships.all().delete()
    AssetFileMembership.objects.bulk_create([
        AssetFileMembership(
            asset=asset, data_file=item.data_file, file_role=item.file_role,
            position=item.position, is_primary=item.is_primary,
            primary_slot=1 if item.is_primary else None, created_by=actor,
        ) for item in items
    ])


def _replace_context_rows(asset, items, actor, registry):
    asset.context_links.all().delete()
    rows = []
    for item in items:
        rule = registry.resolve_current_relation(item.relation_type)
        rows.append(AssetContextLink(
            asset=asset, context=item.context, relation_type=rule.key,
            relation_rule_version=rule.version, relation_rule_digest=rule.digest,
            position=item.position, created_by=actor,
        ))
    AssetContextLink.objects.bulk_create(rows)


def _replace_relation_rows(asset, items, actor, registry):
    asset.outgoing_asset_relations.all().delete()
    rows = []
    for item in items:
        rule = registry.resolve_current_relation(item.relation_type)
        rows.append(DataAssetRelation(
            source_asset=asset, target_asset=item.target_asset, relation_type=rule.key,
            relation_rule_version=rule.version, relation_rule_digest=rule.digest,
            created_by=actor,
        ))
    DataAssetRelation.objects.bulk_create(rows)


def _lock_data_assets(asset_ids):
    ids = sorted(set(asset_ids))
    rows = DataAsset.objects.select_for_update().filter(pk__in=ids).order_by("pk")
    locked = {row.pk: row for row in rows}
    if set(locked) != set(ids):
        raise DataAssetServiceError("A related DataAsset no longer exists.")
    return locked


def _lock_contexts(context_ids):
    ids = sorted(set(context_ids))
    rows = ContextEntity.objects.select_for_update().filter(pk__in=ids).order_by("pk")
    locked = {row.pk: row for row in rows}
    if set(locked) != set(ids):
        raise DataAssetServiceError("A related ContextEntity no longer exists.")
    return locked


def _lock_data_files(file_ids):
    ids = sorted(set(file_ids))
    rows = DataFile.objects.select_for_update().filter(pk__in=ids).order_by("pk")
    locked = {row.pk: row for row in rows}
    if set(locked) != set(ids):
        raise DataAssetServiceError("A related DataFile no longer exists.")
    return locked


def _lock_file_inputs(items):
    items = tuple(items)
    locked = _lock_data_files(item.data_file.pk for item in items)
    return tuple(
        AssetFileInput(
            locked[item.data_file.pk], item.file_role, item.position, item.is_primary
        )
        for item in items
    )


def _lock_context_inputs(items):
    items = tuple(items)
    locked = _lock_contexts(item.context.pk for item in items)
    return tuple(
        AssetContextInput(locked[item.context.pk], item.relation_type, item.position)
        for item in items
    )


def _lock_relation_inputs(items):
    items = tuple(items)
    locked = _lock_data_assets(item.target_asset.pk for item in items)
    return tuple(
        AssetRelationInput(locked[item.target_asset.pk], item.relation_type)
        for item in items
    )


def _lock_non_asset_dependencies(asset):
    _lock_contexts(
        asset.context_links.values_list("context_id", flat=True)
    )
    _lock_data_files(
        asset.file_memberships.values_list("data_file_id", flat=True)
    )


def _current_file_inputs(asset):
    return [AssetFileInput(row.data_file, row.file_role, row.position, row.is_primary)
            for row in asset.file_memberships.select_related("data_file")]


def _current_context_inputs(asset):
    return [AssetContextInput(row.context, row.relation_type, row.position)
            for row in asset.context_links.select_related("context")]


def _current_relation_inputs(asset):
    return [AssetRelationInput(row.target_asset, row.relation_type)
            for row in asset.outgoing_asset_relations.select_related("target_asset")]


def _validate_file_inputs(items):
    seen_files, seen_positions, primary_roles = set(), set(), set()
    for item in items:
        if not isinstance(item, AssetFileInput) or item.data_file is None or item.data_file.pk is None:
            raise DataAssetServiceError("file_memberships must contain saved DataFile inputs.")
        if isinstance(item.position, bool) or not isinstance(item.position, int) or item.position < 0:
            raise DataAssetServiceError("DataAsset file position must be a non-negative integer.")
        if item.data_file.pk in seen_files:
            raise DataAssetServiceError("A DataFile may appear only once in one DataAsset.")
        if (item.file_role, item.position) in seen_positions:
            raise DataAssetServiceError("Duplicate file role and position.")
        if item.is_primary and item.file_role in primary_roles:
            raise DataAssetServiceError("Only one primary file is allowed per role.")
        seen_files.add(item.data_file.pk)
        seen_positions.add((item.file_role, item.position))
        if item.is_primary:
            primary_roles.add(item.file_role)


def _validate_context_inputs(items):
    seen, positions = set(), set()
    for item in items:
        if not isinstance(item, AssetContextInput) or item.context is None or item.context.pk is None:
            raise DataAssetServiceError("context_links must contain saved ContextEntity inputs.")
        if isinstance(item.position, bool) or not isinstance(item.position, int) or item.position < 0:
            raise DataAssetServiceError("Context link position must be a non-negative integer.")
        key = (item.context.pk, item.relation_type)
        if key in seen or (item.relation_type, item.position) in positions:
            raise DataAssetServiceError("Duplicate Context link or position.")
        seen.add(key)
        positions.add((item.relation_type, item.position))


def _validate_relation_inputs(items):
    seen = set()
    for item in items:
        if not isinstance(item, AssetRelationInput) or item.target_asset is None or item.target_asset.pk is None:
            raise DataAssetServiceError("asset_relations must contain saved DataAsset inputs.")
        key = (item.target_asset.pk, item.relation_type)
        if key in seen:
            raise DataAssetServiceError("Duplicate DataAsset relation.")
        seen.add(key)


def _validate_counts(counts, rules, require_minimum, label):
    unknown = set(counts) - set(rules)
    if unknown:
        raise DataAssetServiceError(f"Unknown {label}: {sorted(unknown)[0]}.")
    for key, rule in rules.items():
        count = counts.get(key, 0)
        if require_minimum and count < rule.minimum:
            raise DataAssetServiceError(f"{label} {key} requires at least {rule.minimum}.")
        if rule.maximum is not None and count > rule.maximum:
            raise DataAssetServiceError(f"{label} {key} allows at most {rule.maximum}.")


def _asset_path_exists(start_id, wanted_id, relation_type):
    pending, visited = [start_id], set()
    while pending:
        current = pending.pop()
        if current == wanted_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        pending.extend(DataAssetRelation.objects.filter(
            source_asset_id=current, relation_type=relation_type
        ).values_list("target_asset_id", flat=True))
    return False


def _reject_archive_when_referenced(asset):
    frozen = [DataAsset.STATUS_SUBMITTED, DataAsset.STATUS_APPROVED, DataAsset.STATUS_RELEASED]
    if asset.incoming_asset_relations.filter(
        relation_type="uses_reference", source_asset__status__in=frozen
    ).exists():
        raise DataAssetConflictError("A referenced DataAsset cannot be archived.")


def _require_create_permission(project, actor):
    if project is None or project.pk is None:
        raise DataAssetServiceError("project must be a saved Project.")
    role = _require_project_role(project, actor)
    if role not in {"owner", "manager", "contributor"}:
        raise DataAssetPermissionDenied("The project role cannot create DataAsset records.")


def _require_edit_permission(asset, actor):
    role = _require_project_role(asset.project, actor)
    if role in {"owner", "manager"}:
        return
    if role == "contributor" and asset.created_by_id == actor.pk:
        return
    raise DataAssetPermissionDenied("The DataAsset cannot be edited by this project member.")


def _require_project_role(project, actor):
    role = get_project_role(project=project, user=actor)
    if role is None:
        raise DataAssetPermissionDenied("An active Project membership is required.")
    return role


def _reject_reused_profile_version(profile):
    conflict = DataAsset.objects.select_for_update().filter(
        data_type_key=profile.data_type_key, profile_key=profile.profile_key,
        schema_version=profile.schema_version,
    ).exclude(schema_digest=profile.schema_digest).exists()
    if conflict:
        raise DataAssetConflictError("The DataAsset Profile version has a conflicting digest.")


def _validate_visibility(value):
    if value not in dict(DataAsset.VISIBILITY_CHOICES):
        raise DataAssetServiceError(f"Unsupported DataAsset visibility: {value}.")


def _profile_ref(profile):
    key = getattr(profile, "data_type_key", getattr(profile, "context_type_key", None))
    return f"{key}/{profile.profile_key}"


def _required_text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise DataAssetServiceError(f"{field} must be a non-empty string.")
    return value.strip()
