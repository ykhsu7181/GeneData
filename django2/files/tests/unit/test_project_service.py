import threading

from django.contrib.auth import get_user_model
from django.db import IntegrityError, close_old_connections, transaction
from django.test import TestCase, TransactionTestCase

from files.models import Project, ProjectMembership
from files.services.project_service import (
    LastProjectOwnerError,
    ProjectMembershipConflict,
    ProjectPermissionDenied,
    add_project_member,
    can_project_action,
    change_project_member_role,
    create_project,
    get_project_role,
    remove_project_member,
)


class ProjectServiceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(username="project-owner")
        self.manager = user_model.objects.create_user(username="project-manager")
        self.contributor = user_model.objects.create_user(username="project-contributor")
        self.viewer = user_model.objects.create_user(username="project-viewer")
        self.other_owner = user_model.objects.create_user(username="project-owner-2")
        self.project = create_project(
            creator=self.owner,
            project_code="PROJECT_SERVICE_TEST",
            owner="legacy-value-must-not-authorize",
        )

    def test_create_project_atomically_registers_creator_as_owner(self):
        self.assertEqual(get_project_role(project=self.project, user=self.owner), "owner")
        self.assertEqual(self.project.memberships.count(), 1)

    def test_role_matrix_uses_membership_not_legacy_owner_string(self):
        add_project_member(project=self.project, actor=self.owner, user=self.manager, role="manager")
        add_project_member(project=self.project, actor=self.owner, user=self.contributor, role="contributor")
        add_project_member(project=self.project, actor=self.manager, user=self.viewer, role="viewer")

        self.assertTrue(can_project_action(project=self.project, user=self.owner, action="manage_owners"))
        self.assertTrue(can_project_action(project=self.project, user=self.manager, action="manage_members"))
        self.assertTrue(can_project_action(project=self.project, user=self.contributor, action="edit_content"))
        self.assertFalse(can_project_action(project=self.project, user=self.viewer, action="edit_content"))
        self.assertFalse(can_project_action(project=self.project, user=self.viewer, action="unknown"))

    def test_manager_cannot_grant_change_or_remove_owner(self):
        add_project_member(project=self.project, actor=self.owner, user=self.manager, role="manager")
        add_project_member(project=self.project, actor=self.owner, user=self.other_owner, role="owner")

        with self.assertRaises(ProjectPermissionDenied):
            add_project_member(project=self.project, actor=self.manager, user=self.viewer, role="owner")
        with self.assertRaises(ProjectPermissionDenied):
            change_project_member_role(
                project=self.project, actor=self.manager, user=self.other_owner, role="viewer"
            )
        with self.assertRaises(ProjectPermissionDenied):
            remove_project_member(project=self.project, actor=self.manager, user=self.other_owner)

    def test_last_owner_cannot_be_demoted_or_removed(self):
        with self.assertRaises(LastProjectOwnerError):
            change_project_member_role(
                project=self.project, actor=self.owner, user=self.owner, role="manager"
            )
        with self.assertRaises(LastProjectOwnerError):
            remove_project_member(project=self.project, actor=self.owner, user=self.owner)

    def test_second_owner_allows_first_owner_removal(self):
        add_project_member(
            project=self.project,
            actor=self.owner,
            user=self.other_owner,
            role="owner",
        )
        remove_project_member(project=self.project, actor=self.owner, user=self.owner)
        self.assertEqual(get_project_role(project=self.project, user=self.other_owner), "owner")

    def test_duplicate_membership_has_stable_conflict(self):
        add_project_member(project=self.project, actor=self.owner, user=self.viewer, role="viewer")
        with self.assertRaises(ProjectMembershipConflict):
            add_project_member(project=self.project, actor=self.owner, user=self.viewer, role="viewer")
        self.assertEqual(
            ProjectMembership.objects.filter(project=self.project, user=self.viewer).count(),
            1,
        )

    def test_database_rejects_unknown_role_and_duplicate_user(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProjectMembership.objects.create(
                project=self.project,
                user=self.viewer,
                role="administrator",
            )
        ProjectMembership.objects.create(project=self.project, user=self.viewer, role="viewer")
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProjectMembership.objects.create(project=self.project, user=self.viewer, role="viewer")

    def test_inactive_user_is_not_authorized(self):
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        self.assertIsNone(get_project_role(project=self.project, user=self.owner))
        self.assertFalse(can_project_action(project=self.project, user=self.owner, action="view"))


class ProjectOwnerConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_concurrent_owner_removals_retain_one_owner(self):
        user_model = get_user_model()
        first = user_model.objects.create_user(username="concurrent-owner-1")
        second = user_model.objects.create_user(username="concurrent-owner-2")
        project = create_project(creator=first, project_code="PROJECT_OWNER_RACE")
        add_project_member(project=project, actor=first, user=second, role="owner")
        barrier = threading.Barrier(2)
        outcomes = []
        outcome_lock = threading.Lock()

        def remove_self(user_id):
            close_old_connections()
            try:
                actor = user_model.objects.get(pk=user_id)
                thread_project = Project.objects.get(pk=project.pk)
                barrier.wait(timeout=5)
                remove_project_member(
                    project=thread_project,
                    actor=actor,
                    user=actor,
                )
                outcome = "removed"
            except LastProjectOwnerError:
                outcome = "protected"
            finally:
                close_old_connections()
            with outcome_lock:
                outcomes.append(outcome)

        threads = [
            threading.Thread(target=remove_self, args=(first.pk,)),
            threading.Thread(target=remove_self, args=(second.pk,)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertCountEqual(outcomes, ["removed", "protected"])
        self.assertEqual(
            ProjectMembership.objects.filter(project=project, role="owner").count(),
            1,
        )
