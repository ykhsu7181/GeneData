"""ADR-005 write boundary for ContextEntity and context relations."""

from django.db import IntegrityError, transaction

from files.models import ContextEntity, ContextRelation, DataAsset
from files.services.core_content_snapshot import context_content_snapshot
from files.services.core_audit_service import append_core_audit_event
from files.services.data_asset_lifecycle_policy import (
    LifecyclePolicyError,
    resolve_context_transition,
)
from files.services.data_asset_registry_service import (
    DataAssetRegistryError,
    load_data_asset_registry,
)
from files.services.project_service import get_project_role, lock_project_for_core_write


class ContextServiceError(ValueError):
    pass


class ContextPermissionDenied(ContextServiceError):
    pass


class ContextConflictError(ContextServiceError):
    pass


def create_context(
    *, context_code, project, context_type_key, profile_key, actor,
    metadata=None, name="", description="", registry=None,
):
    _require_create_permission(project, actor)
    context_code = _required_text(context_code, "context_code")
    registry = registry or load_data_asset_registry()
    metadata = {} if metadata is None else metadata
    try:
        profile = registry.resolve_current_context_profile(context_type_key, profile_key)
        registry.validate_context_profile_metadata(profile, metadata)
    except DataAssetRegistryError as exc:
        raise ContextServiceError(str(exc)) from exc
    if profile.deprecated:
        raise ContextServiceError("A deprecated Context profile cannot be selected.")

    try:
        with transaction.atomic():
            lock_project_for_core_write(project.pk)
            _require_create_permission(project, actor)
            _reject_reused_profile_version(profile)
            context = ContextEntity.objects.create(
                context_code=context_code,
                name=name or "",
                project=project,
                context_type_key=profile.context_type_key,
                profile_key=profile.profile_key,
                schema_version=profile.schema_version,
                schema_digest=profile.schema_digest,
                metadata=metadata,
                description=description or "",
                created_by=actor,
            )
            append_core_audit_event(
                project=project,
                actor=actor,
                event_type="context_created",
                context=context,
                to_value=ContextEntity.STATUS_DRAFT,
                after_content=context_content_snapshot(context),
            )
            return context
    except IntegrityError as exc:
        raise ContextConflictError("Context creation violated a database invariant.") from exc


def update_context_draft(
    *, context, actor, metadata=None, name=None, description=None,
    context_type_key=None, profile_key=None, registry=None,
):
    registry = registry or load_data_asset_registry()
    with transaction.atomic():
        lock_project_for_core_write(context.project_id)
        locked = ContextEntity.objects.select_for_update().get(pk=context.pk)
        _require_edit_permission(locked, actor)
        if locked.status != ContextEntity.STATUS_DRAFT:
            raise ContextConflictError("Only a draft ContextEntity can be edited.")
        before = context_content_snapshot(locked)

        next_type = context_type_key or locked.context_type_key
        next_profile_key = profile_key or locked.profile_key
        next_metadata = locked.metadata if metadata is None else metadata
        try:
            if (next_type, next_profile_key) == (
                locked.context_type_key,
                locked.profile_key,
            ):
                profile = registry.resolve_exact_context_profile(
                    locked.context_type_key,
                    locked.profile_key,
                    locked.schema_version,
                    locked.schema_digest,
                )
            else:
                profile = registry.resolve_current_context_profile(next_type, next_profile_key)
                if profile.deprecated:
                    raise ContextServiceError("A deprecated Context profile cannot be selected.")
                _validate_existing_context_relations(locked, profile, registry)
                _validate_existing_external_identifiers(locked, profile, registry)
                _reject_reused_profile_version(profile)
            registry.validate_context_profile_metadata(profile, next_metadata)
        except DataAssetRegistryError as exc:
            raise ContextServiceError(str(exc)) from exc

        locked.context_type_key = profile.context_type_key
        locked.profile_key = profile.profile_key
        locked.schema_version = profile.schema_version
        locked.schema_digest = profile.schema_digest
        locked.metadata = next_metadata
        if name is not None:
            locked.name = name or ""
        if description is not None:
            locked.description = description or ""
        locked.save(update_fields=[
            "context_type_key", "profile_key", "schema_version", "schema_digest",
            "metadata", "name", "description", "updated_at",
        ])
        after = context_content_snapshot(locked)
        if before == after:
            raise ContextServiceError("The ContextEntity update has no effect.")
        append_core_audit_event(
            project=locked.project,
            actor=actor,
            event_type="context_updated",
            context=locked,
            before_content=before,
            after_content=after,
        )
        return locked


def transition_context(*, context, actor, action, reason="", registry=None):
    registry = registry or load_data_asset_registry()
    with transaction.atomic():
        lock_project_for_core_write(context.project_id)
        locked = ContextEntity.objects.select_for_update().get(pk=context.pk)
        role = _require_project_role(locked.project, actor)
        try:
            rule = resolve_context_transition(action, locked.status, role)
        except LifecyclePolicyError as exc:
            raise ContextPermissionDenied(str(exc)) from exc
        if rule.reason_required and not str(reason or "").strip():
            raise ContextServiceError("A reason is required for this transition.")
        if action == "activate":
            _lock_contexts(
                locked.outgoing_context_relations.values_list(
                    "target_context_id", flat=True
                )
            )
            _validate_context_complete(locked, registry)
        elif action == "archive":
            _reject_context_archive_when_referenced(locked)
        previous = locked.status
        locked.status = rule.target
        locked.save(update_fields=["status", "updated_at"])
        append_core_audit_event(
            project=locked.project,
            actor=actor,
            event_type="context_activated" if action == "activate" else "context_archived",
            context=locked,
            from_value=previous,
            to_value=rule.target,
            reason=reason,
        )
        return locked


def create_context_relation(
    *, source_context, target_context, relation_type, actor, registry=None,
):
    registry = registry or load_data_asset_registry()
    with transaction.atomic():
        lock_project_for_core_write(source_context.project_id)
        locked_contexts = _lock_contexts({source_context.pk, target_context.pk})
        source = locked_contexts[source_context.pk]
        target = locked_contexts[target_context.pk]
        _require_edit_permission(source, actor)
        if source.status != ContextEntity.STATUS_DRAFT:
            raise ContextConflictError("Context relations can only be changed while the source is draft.")
        rule = _validate_context_relation_write(
            source, target, relation_type, registry
        )
        before = context_content_snapshot(source)
        try:
            relation = ContextRelation.objects.create(
                source_context=source,
                target_context=target,
                relation_type=rule.key,
                relation_rule_version=rule.version,
                relation_rule_digest=rule.digest,
                created_by=actor,
            )
        except IntegrityError as exc:
            raise ContextConflictError("The Context relation already exists or conflicts.") from exc
        _append_context_content_change(source, actor, before=before)
        return relation


def replace_context_relation(*, relation, target_context, actor, registry=None):
    registry = registry or load_data_asset_registry()
    with transaction.atomic():
        lock_project_for_core_write(relation.source_context.project_id)
        locked = ContextRelation.objects.select_for_update().select_related(
            "source_context"
        ).get(pk=relation.pk)
        locked_contexts = _lock_contexts(
            {locked.source_context_id, target_context.pk}
        )
        source = locked_contexts[locked.source_context_id]
        target = locked_contexts[target_context.pk]
        _require_edit_permission(source, actor)
        if source.status != ContextEntity.STATUS_DRAFT:
            raise ContextConflictError(
                "Context relations can only be changed while the source is draft."
            )
        before = context_content_snapshot(source)
        rule = _validate_context_relation_write(
            source,
            target,
            locked.relation_type,
            registry,
            exclude_relation_id=locked.pk,
        )
        locked.target_context = target
        locked.relation_rule_version = rule.version
        locked.relation_rule_digest = rule.digest
        try:
            locked.save(update_fields=[
                "target_context", "relation_rule_version", "relation_rule_digest"
            ])
        except IntegrityError as exc:
            raise ContextConflictError(
                "The replacement Context relation already exists or conflicts."
            ) from exc
        _append_context_content_change(source, actor, before=before)
        return locked


def remove_context_relation(*, relation, actor):
    with transaction.atomic():
        lock_project_for_core_write(relation.source_context.project_id)
        locked = ContextRelation.objects.select_for_update().select_related("source_context").get(
            pk=relation.pk
        )
        source = ContextEntity.objects.select_for_update().get(pk=locked.source_context_id)
        _require_edit_permission(source, actor)
        if source.status != ContextEntity.STATUS_DRAFT:
            raise ContextConflictError("Context relations can only be changed while the source is draft.")
        before = context_content_snapshot(source)
        locked.delete()
        _append_context_content_change(source, actor, before=before)


def _validate_context_relation_write(
    source, target, relation_type, registry, *, exclude_relation_id=None,
):
    if source.project_id != target.project_id:
        raise ContextPermissionDenied("Context relations must remain in one Project.")
    if source.pk == target.pk:
        raise ContextServiceError("A ContextEntity cannot relate to itself.")
    if target.status == ContextEntity.STATUS_ARCHIVED:
        raise ContextConflictError(
            "An archived ContextEntity cannot be the target of a new relation."
        )
    try:
        profile = registry.resolve_exact_context_profile(
            source.context_type_key, source.profile_key,
            source.schema_version, source.schema_digest,
        )
        rule = registry.resolve_current_relation(relation_type)
        profile_rule = profile.outgoing_relations[relation_type]
        target_profile = registry.resolve_exact_context_profile(
            target.context_type_key, target.profile_key,
            target.schema_version, target.schema_digest,
        )
    except (DataAssetRegistryError, KeyError) as exc:
        raise ContextServiceError(
            "The Context relation is not allowed by its Profile."
        ) from exc
    if (rule.source_kind, rule.target_kind) != ("context", "context"):
        raise ContextServiceError("The relation does not connect ContextEntity objects.")
    if _profile_ref(target_profile) not in profile_rule.allowed_target_profiles:
        raise ContextServiceError("The target Context profile is not allowed.")
    outgoing = ContextRelation.objects.filter(
        source_context=source, relation_type=relation_type
    )
    incoming = ContextRelation.objects.filter(
        target_context=target, relation_type=relation_type
    )
    if exclude_relation_id is not None:
        outgoing = outgoing.exclude(pk=exclude_relation_id)
        incoming = incoming.exclude(pk=exclude_relation_id)
    _enforce_maximum(outgoing.count(), profile_rule.maximum)
    _enforce_maximum(outgoing.count(), rule.outgoing_max)
    _enforce_maximum(incoming.count(), rule.incoming_max)
    if rule.acyclic and _context_path_exists(target.pk, source.pk, relation_type):
        raise ContextConflictError("The Context relation would create a cycle.")
    return rule


def _append_context_content_change(context, actor, before):
    after = context_content_snapshot(context)
    append_core_audit_event(
        project=context.project,
        actor=actor,
        event_type="context_updated",
        context=context,
        before_content=before,
        after_content=after,
    )


def _validate_context_complete(context, registry):
    try:
        profile = registry.resolve_exact_context_profile(
            context.context_type_key, context.profile_key,
            context.schema_version, context.schema_digest,
        )
        registry.validate_context_profile_metadata(profile, context.metadata)
    except DataAssetRegistryError as exc:
        raise ContextServiceError(str(exc)) from exc
    counts = {
        key: context.outgoing_context_relations.filter(relation_type=key).count()
        for key in profile.outgoing_relations
    }
    for key, rule in profile.outgoing_relations.items():
        if counts[key] < rule.minimum:
            raise ContextServiceError(f"Context relation {key} requires at least {rule.minimum}.")
    if context.outgoing_context_relations.exclude(
        target_context__status=ContextEntity.STATUS_ACTIVE
    ).exists():
        raise ContextServiceError(
            "ContextEntity activation requires active relation targets."
        )


def _validate_existing_context_relations(context, profile, registry):
    for relation in context.outgoing_context_relations.select_related("target_context"):
        try:
            profile_rule = profile.outgoing_relations[relation.relation_type]
            target = relation.target_context
            target_profile = registry.resolve_exact_context_profile(
                target.context_type_key, target.profile_key,
                target.schema_version, target.schema_digest,
            )
        except (KeyError, DataAssetRegistryError) as exc:
            raise ContextServiceError("Existing Context relations are invalid for the new Profile.") from exc
        if _profile_ref(target_profile) not in profile_rule.allowed_target_profiles:
            raise ContextServiceError("Existing Context target is invalid for the new Profile.")


def _validate_existing_external_identifiers(context, profile, registry):
    for identifier in context.external_identifiers.all():
        try:
            namespace = registry.resolve_exact_namespace(
                identifier.namespace_key,
                identifier.namespace_version,
                identifier.namespace_digest,
            )
        except DataAssetRegistryError as exc:
            raise ContextServiceError(
                "An existing external identifier has an unknown Namespace contract."
            ) from exc
        if (
            namespace.allowed_context_types
            and profile.context_type_key not in namespace.allowed_context_types
        ):
            raise ContextServiceError(
                "Existing external identifiers are invalid for the new Context Profile."
            )


def _reject_context_archive_when_referenced(context):
    frozen = [DataAsset.STATUS_SUBMITTED, DataAsset.STATUS_APPROVED, DataAsset.STATUS_RELEASED]
    if context.asset_links.filter(asset__status__in=frozen).exists():
        raise ContextConflictError("A ContextEntity referenced by a frozen asset cannot be archived.")


def _context_path_exists(start_id, wanted_id, relation_type):
    pending = [start_id]
    visited = set()
    while pending:
        current = pending.pop()
        if current == wanted_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        pending.extend(
            ContextRelation.objects.filter(
                source_context_id=current, relation_type=relation_type
            ).values_list("target_context_id", flat=True)
        )
    return False


def _lock_contexts(context_ids):
    ids = sorted(set(context_ids))
    rows = ContextEntity.objects.select_for_update().filter(pk__in=ids).order_by("pk")
    locked = {row.pk: row for row in rows}
    if set(locked) != set(ids):
        raise ContextServiceError("A related ContextEntity no longer exists.")
    return locked


def _require_create_permission(project, actor):
    role = _require_project_role(project, actor)
    if role not in {"owner", "manager", "contributor"}:
        raise ContextPermissionDenied("The project role cannot create ContextEntity records.")


def _require_edit_permission(context, actor):
    role = _require_project_role(context.project, actor)
    if role in {"owner", "manager"}:
        return
    if role == "contributor" and context.created_by_id == actor.pk:
        return
    raise ContextPermissionDenied("The ContextEntity cannot be edited by this project member.")


def _require_project_role(project, actor):
    role = get_project_role(project=project, user=actor)
    if role is None:
        raise ContextPermissionDenied("An active Project membership is required.")
    return role


def _reject_reused_profile_version(profile):
    conflict = ContextEntity.objects.select_for_update().filter(
        context_type_key=profile.context_type_key,
        profile_key=profile.profile_key,
        schema_version=profile.schema_version,
    ).exclude(schema_digest=profile.schema_digest).exists()
    if conflict:
        raise ContextConflictError("The Context profile version has a conflicting digest.")


def _profile_ref(profile):
    key = getattr(profile, "context_type_key", getattr(profile, "data_type_key", None))
    return f"{key}/{profile.profile_key}"


def _enforce_maximum(current, maximum):
    if maximum is not None and current >= maximum:
        raise ContextConflictError(f"The relation maximum of {maximum} has been reached.")


def _required_text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ContextServiceError(f"{field} must be a non-empty string.")
    return value.strip()
