"""ADR-005 write boundary for controlled external identifiers."""

from django.db import IntegrityError, transaction

from files.models import ContextEntity, DataAsset, ExternalIdentifier, Project
from files.services.core_audit_service import append_core_audit_event
from files.services.core_content_snapshot import asset_content_snapshot, context_content_snapshot
from files.services.data_asset_registry_service import (
    DataAssetRegistryError,
    load_data_asset_registry,
)
from files.services.project_service import get_project_role, lock_project_for_core_write


class ExternalIdentifierServiceError(ValueError):
    pass


class ExternalIdentifierPermissionDenied(ExternalIdentifierServiceError):
    pass


class ExternalIdentifierConflict(ExternalIdentifierServiceError):
    pass


def add_external_identifier(
    *, namespace_key, display_value, actor, project=None, asset=None, context=None,
    registry=None,
):
    target_kind, target, owning_project = _resolve_target(
        project=project, asset=asset, context=context
    )
    _require_target_edit(target_kind, target, owning_project, actor)
    registry = registry or load_data_asset_registry()
    try:
        namespace = registry.resolve_current_namespace(namespace_key)
        normalized = namespace.normalize(display_value)
    except DataAssetRegistryError as exc:
        raise ExternalIdentifierServiceError(str(exc)) from exc
    if namespace.deprecated:
        raise ExternalIdentifierServiceError("A deprecated namespace cannot be selected.")
    if target_kind not in namespace.allowed_target_kinds:
        raise ExternalIdentifierServiceError("The namespace does not allow this target kind.")
    if target_kind == "context" and namespace.allowed_context_types:
        if target.context_type_key not in namespace.allowed_context_types:
            raise ExternalIdentifierServiceError(
                "The namespace does not allow this Context type."
            )

    with transaction.atomic():
        lock_project_for_core_write(owning_project.pk)
        locked_target = _lock_target(target_kind, target)
        _require_target_edit(target_kind, locked_target, owning_project, actor)
        before = _target_snapshot(target_kind, locked_target)
        try:
            identifier = ExternalIdentifier.objects.create(
                namespace_key=namespace.key,
                namespace_version=namespace.version,
                namespace_digest=namespace.digest,
                normalized_value=normalized,
                display_value=str(display_value).strip(),
                project=locked_target if target_kind == "project" else None,
                asset=locked_target if target_kind == "data_asset" else None,
                context=locked_target if target_kind == "context" else None,
                created_by=actor,
            )
        except IntegrityError as exc:
            raise ExternalIdentifierConflict(
                "The normalized external identifier is already registered."
            ) from exc
        _audit_target_change(target_kind, locked_target, actor, before)
        return identifier


def remove_external_identifier(*, identifier, actor):
    target_kind, target, owning_project = _resolve_target(
        project=identifier.project, asset=identifier.asset, context=identifier.context
    )
    with transaction.atomic():
        lock_project_for_core_write(owning_project.pk)
        locked_target = _lock_target(target_kind, target)
        locked = ExternalIdentifier.objects.select_for_update().select_related(
            "project", "asset", "context"
        ).get(pk=identifier.pk)
        locked_kind, locked_target_from_row, locked_project = _resolve_target(
            project=locked.project, asset=locked.asset, context=locked.context
        )
        if (
            locked_kind != target_kind
            or locked_target_from_row.pk != locked_target.pk
            or locked_project.pk != owning_project.pk
        ):
            raise ExternalIdentifierConflict("The external identifier target changed.")
        _require_target_edit(target_kind, locked_target, owning_project, actor)
        before = _target_snapshot(target_kind, locked_target)
        locked.delete()
        _audit_target_change(target_kind, locked_target, actor, before)


def _resolve_target(*, project, asset, context):
    targets = [("project", project), ("data_asset", asset), ("context", context)]
    present = [(kind, target) for kind, target in targets if target is not None]
    if len(present) != 1 or present[0][1].pk is None:
        raise ExternalIdentifierServiceError("Exactly one persisted target is required.")
    kind, target = present[0]
    owning_project = target if kind == "project" else target.project
    return kind, target, owning_project


def _require_target_edit(kind, target, project, actor):
    role = get_project_role(project=project, user=actor)
    if role is None:
        raise ExternalIdentifierPermissionDenied("An active Project membership is required.")
    if kind == "project":
        if role not in {"owner", "manager"}:
            raise ExternalIdentifierPermissionDenied(
                "Only a Project owner or manager can manage Project identifiers."
            )
        return
    if target.status != "draft":
        raise ExternalIdentifierPermissionDenied(
            "External identifiers can only be changed while the target is draft."
        )
    if role in {"owner", "manager"}:
        return
    if role == "contributor" and target.created_by_id == actor.pk:
        return
    raise ExternalIdentifierPermissionDenied("The target cannot be edited by this member.")


def _lock_target(kind, target):
    if kind == "project":
        return Project.objects.select_for_update().get(pk=target.pk)
    if kind == "data_asset":
        return DataAsset.objects.select_for_update().get(pk=target.pk)
    return ContextEntity.objects.select_for_update().get(pk=target.pk)


def _target_snapshot(kind, target):
    if kind == "data_asset":
        return asset_content_snapshot(target)
    if kind == "context":
        return context_content_snapshot(target)
    return None


def _audit_target_change(kind, target, actor, before):
    if kind == "project":
        return
    if kind == "data_asset":
        append_core_audit_event(
            project=target.project,
            actor=actor,
            event_type="asset_updated",
            asset=target,
            before_content=before,
            after_content=asset_content_snapshot(target),
        )
    else:
        append_core_audit_event(
            project=target.project,
            actor=actor,
            event_type="context_updated",
            context=target,
            before_content=before,
            after_content=context_content_snapshot(target),
        )
