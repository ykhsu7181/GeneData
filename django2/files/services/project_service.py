from dataclasses import dataclass
from typing import Optional

from django.db import IntegrityError, transaction

from files.models import Project, ProjectMembership


class ProjectServiceError(ValueError):
    pass


class ProjectPermissionDenied(ProjectServiceError):
    pass


class ProjectMembershipConflict(ProjectServiceError):
    pass


class LastProjectOwnerError(ProjectServiceError):
    pass


@dataclass(frozen=True)
class ProjectActionPolicy:
    permitted_roles: frozenset


ACTION_POLICIES = {
    "view": ProjectActionPolicy(frozenset({"owner", "manager", "contributor", "viewer"})),
    "edit_content": ProjectActionPolicy(frozenset({"owner", "manager", "contributor"})),
    "manage_members": ProjectActionPolicy(frozenset({"owner", "manager"})),
    "manage_owners": ProjectActionPolicy(frozenset({"owner"})),
}


def create_project(*, creator, project_code: str, **project_fields) -> Project:
    if creator is None or creator.pk is None or not creator.is_active:
        raise ProjectPermissionDenied("An active persisted creator is required.")
    if not project_code:
        raise ProjectServiceError("project_code is required.")

    with transaction.atomic():
        project = Project.objects.create(project_code=project_code, **project_fields)
        ProjectMembership.objects.create(
            project=project,
            user=creator,
            role=ProjectMembership.ROLE_OWNER,
            created_by=creator,
        )
    return project


def get_project_role(*, project: Project, user) -> Optional[str]:
    if user is None or user.pk is None or not user.is_active:
        return None
    return (
        ProjectMembership.objects.filter(project=project, user=user)
        .values_list("role", flat=True)
        .first()
    )


def can_project_action(*, project: Project, user, action: str) -> bool:
    policy = ACTION_POLICIES.get(action)
    if policy is None:
        return False
    return get_project_role(project=project, user=user) in policy.permitted_roles


def _locked_actor_role(*, project: Project, actor) -> str:
    if actor is None or actor.pk is None or not actor.is_active:
        raise ProjectPermissionDenied("An active project member is required.")
    role = (
        ProjectMembership.objects.select_for_update()
        .filter(project=project, user=actor)
        .values_list("role", flat=True)
        .first()
    )
    if role not in {ProjectMembership.ROLE_OWNER, ProjectMembership.ROLE_MANAGER}:
        raise ProjectPermissionDenied("Project member management is not permitted.")
    return role


def _validate_role(role: str) -> None:
    if role not in dict(ProjectMembership.ROLE_CHOICES):
        raise ProjectServiceError("Unknown project role.")


def add_project_member(*, project: Project, actor, user, role: str) -> ProjectMembership:
    _validate_role(role)
    if user is None or user.pk is None or not user.is_active:
        raise ProjectServiceError("An active persisted member is required.")

    with transaction.atomic():
        Project.objects.select_for_update().get(pk=project.pk)
        actor_role = _locked_actor_role(project=project, actor=actor)
        if role == ProjectMembership.ROLE_OWNER and actor_role != ProjectMembership.ROLE_OWNER:
            raise ProjectPermissionDenied("Only an owner can grant the owner role.")
        try:
            return ProjectMembership.objects.create(
                project=project,
                user=user,
                role=role,
                created_by=actor,
            )
        except IntegrityError as exc:
            raise ProjectMembershipConflict("The user is already a project member.") from exc


def change_project_member_role(*, project: Project, actor, user, role: str) -> ProjectMembership:
    _validate_role(role)
    with transaction.atomic():
        Project.objects.select_for_update().get(pk=project.pk)
        actor_role = _locked_actor_role(project=project, actor=actor)
        membership = ProjectMembership.objects.select_for_update().get(
            project=project,
            user=user,
        )
        if (
            membership.role == ProjectMembership.ROLE_OWNER
            or role == ProjectMembership.ROLE_OWNER
        ) and actor_role != ProjectMembership.ROLE_OWNER:
            raise ProjectPermissionDenied("Only an owner can change owner membership.")
        if membership.role == ProjectMembership.ROLE_OWNER and role != ProjectMembership.ROLE_OWNER:
            owner_count = ProjectMembership.objects.filter(
                project=project,
                role=ProjectMembership.ROLE_OWNER,
            ).count()
            if owner_count <= 1:
                raise LastProjectOwnerError("A project must retain at least one owner.")
        membership.role = role
        membership.save(update_fields=["role", "updated_at"])
        return membership


def remove_project_member(*, project: Project, actor, user) -> None:
    with transaction.atomic():
        Project.objects.select_for_update().get(pk=project.pk)
        actor_role = _locked_actor_role(project=project, actor=actor)
        membership = ProjectMembership.objects.select_for_update().get(
            project=project,
            user=user,
        )
        if membership.role == ProjectMembership.ROLE_OWNER:
            if actor_role != ProjectMembership.ROLE_OWNER:
                raise ProjectPermissionDenied("Only an owner can remove an owner.")
            owner_count = ProjectMembership.objects.filter(
                project=project,
                role=ProjectMembership.ROLE_OWNER,
            ).count()
            if owner_count <= 1:
                raise LastProjectOwnerError("A project must retain at least one owner.")
        membership.delete()
