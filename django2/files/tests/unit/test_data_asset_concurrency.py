import threading
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import close_old_connections, transaction
from django.test import TransactionTestCase, skipUnlessDBFeature

import files.services.data_asset_service as data_asset_service_module
import files.services.context_service as context_service_module
from files.models import ContextEntity, DataAsset, DataAssetRelation, ExternalIdentifier
from files.services.context_service import (
    ContextConflictError,
    create_context,
    transition_context,
)
from files.services.data_asset_service import (
    AssetContextInput,
    AssetFileInput,
    DataAssetServiceError,
    add_asset_relation,
    create_data_asset,
    transition_data_asset,
    update_data_asset_draft,
)
from files.services.external_identifier_service import (
    ExternalIdentifierConflict,
    add_external_identifier,
)
from files.services.project_service import add_project_member, create_project
from files.models import DataFile


@skipUnlessDBFeature("has_select_for_update")
class DataAssetConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        users = get_user_model().objects
        self.owner = users.create_user(username="d2-owner")
        self.manager = users.create_user(username="d2-manager")
        self.contributor = users.create_user(username="d2-contributor")
        self.project = create_project(creator=self.owner, project_code="D2_PROJECT")
        add_project_member(
            project=self.project,
            actor=self.owner,
            user=self.manager,
            role="manager",
            reason="D2 lifecycle reviewer",
        )
        add_project_member(
            project=self.project,
            actor=self.owner,
            user=self.contributor,
            role="contributor",
        )

    def run_concurrently(self, operations):
        barrier = threading.Barrier(len(operations))
        outcomes = []
        outcome_lock = threading.Lock()

        def run(operation):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                operation()
                outcome = "ok"
            except Exception as exc:  # The exact domain failure is asserted by each test.
                outcome = exc
            finally:
                close_old_connections()
            with outcome_lock:
                outcomes.append(outcome)

        threads = [threading.Thread(target=run, args=(operation,)) for operation in operations]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        return outcomes

    def run_with_project_lock_contention(self, holder_operation, contender_operation):
        """Prove the contender reaches the project lock while the holder owns it."""
        holder_locked = threading.Event()
        contender_attempted = threading.Event()
        release_holder = threading.Event()
        outcomes = []
        outcome_lock = threading.Lock()
        original_lock = data_asset_service_module.lock_project_for_core_write

        def observed_lock(project_id):
            if threading.current_thread().name == "d2-contender":
                contender_attempted.set()
            return original_lock(project_id)

        def record(operation, *, hold_project=False):
            close_old_connections()
            try:
                if hold_project:
                    with transaction.atomic():
                        original_lock(self.project.pk)
                        holder_locked.set()
                        if not release_holder.wait(timeout=10):
                            raise AssertionError("Timed out before releasing the project lock.")
                        operation()
                else:
                    operation()
                outcome = "ok"
            except Exception as exc:
                outcome = exc
            finally:
                close_old_connections()
            with outcome_lock:
                outcomes.append(outcome)

        with patch.object(
            data_asset_service_module, "lock_project_for_core_write", side_effect=observed_lock
        ), patch.object(
            context_service_module, "lock_project_for_core_write", side_effect=observed_lock
        ):
            holder = threading.Thread(
                target=record,
                kwargs={"operation": holder_operation, "hold_project": True},
                name="d2-holder",
            )
            contender = threading.Thread(
                target=record,
                kwargs={"operation": contender_operation},
                name="d2-contender",
            )
            holder.start()
            self.assertTrue(holder_locked.wait(timeout=10))
            contender.start()
            try:
                self.assertTrue(contender_attempted.wait(timeout=10))
                self.assertTrue(contender.is_alive())
            finally:
                release_holder.set()
            holder.join(timeout=20)
            contender.join(timeout=20)

        self.assertFalse(holder.is_alive())
        self.assertFalse(contender.is_alive())
        return outcomes

    def create_reference(self, code):
        return create_data_asset(
            asset_code=code,
            project=self.project,
            data_type_key="sequence",
            profile_key="reference_genome",
            created_by=self.owner,
        )

    def test_concurrent_disjoint_supersedes_edges_cannot_create_cycle(self):
        first = self.create_reference("D2_CYCLE_A")
        second = self.create_reference("D2_CYCLE_B")
        third = self.create_reference("D2_CYCLE_C")
        fourth = self.create_reference("D2_CYCLE_D")
        add_asset_relation(
            asset=second, target_asset=third,
            relation_type="supersedes", actor=self.owner,
        )
        add_asset_relation(
            asset=fourth, target_asset=first,
            relation_type="supersedes", actor=self.owner,
        )

        def add_first_to_second():
            add_asset_relation(
                asset=DataAsset.objects.get(pk=first.pk),
                target_asset=DataAsset.objects.get(pk=second.pk),
                relation_type="supersedes",
                actor=get_user_model().objects.get(pk=self.owner.pk),
            )

        def add_third_to_fourth():
            add_asset_relation(
                asset=DataAsset.objects.get(pk=third.pk),
                target_asset=DataAsset.objects.get(pk=fourth.pk),
                relation_type="supersedes",
                actor=get_user_model().objects.get(pk=self.owner.pk),
            )

        outcomes = self.run_with_project_lock_contention(
            add_first_to_second, add_third_to_fourth
        )
        self.assertEqual(outcomes.count("ok"), 1)
        self.assertEqual(sum(isinstance(item, DataAssetServiceError) for item in outcomes), 1)
        self.assertEqual(DataAssetRelation.objects.filter(relation_type="supersedes").count(), 3)

    def test_concurrent_supersedes_edges_respect_incoming_maximum(self):
        old = self.create_reference("D2_OLD")
        first = self.create_reference("D2_NEW_A")
        second = self.create_reference("D2_NEW_B")

        def add_successor(source_id):
            def operation():
                add_asset_relation(
                    asset=DataAsset.objects.get(pk=source_id),
                    target_asset=DataAsset.objects.get(pk=old.pk),
                    relation_type="supersedes",
                    actor=get_user_model().objects.get(pk=self.owner.pk),
                )
            return operation

        outcomes = self.run_with_project_lock_contention(
            add_successor(first.pk), add_successor(second.pk)
        )
        self.assertEqual(outcomes.count("ok"), 1)
        self.assertEqual(sum(isinstance(item, DataAssetServiceError) for item in outcomes), 1)
        self.assertEqual(
            DataAssetRelation.objects.filter(
                target_asset=old, relation_type="supersedes"
            ).count(),
            1,
        )

    def test_transition_and_reverse_relation_write_use_one_lock_order(self):
        lower = self.create_reference("D2_LOCK_LOW")
        genome_file = DataFile.objects.create(
            file_code="D2_LOCK_FILE",
            file_name="genome.fasta",
            file_path="/not-used/d2-lock.fasta",
            file_size=10,
            sha256="a" * 64,
            availability_status=DataFile.AVAILABILITY_AVAILABLE,
        )
        higher = create_data_asset(
            asset_code="D2_LOCK_HIGH",
            project=self.project,
            data_type_key="sequence",
            profile_key="reference_genome",
            created_by=self.owner,
            file_memberships=[AssetFileInput(genome_file, "genome_fasta")],
        )
        self.assertLess(lower.pk, higher.pk)
        add_asset_relation(
            asset=higher,
            target_asset=lower,
            relation_type="supersedes",
            actor=self.owner,
        )

        def submit_higher():
            transition_data_asset(
                asset=DataAsset.objects.get(pk=higher.pk),
                actor=get_user_model().objects.get(pk=self.owner.pk),
                action="submit",
            )

        def add_reverse_relation():
            add_asset_relation(
                asset=DataAsset.objects.get(pk=lower.pk),
                target_asset=DataAsset.objects.get(pk=higher.pk),
                relation_type="supersedes",
                actor=get_user_model().objects.get(pk=self.owner.pk),
            )

        outcomes = self.run_with_project_lock_contention(
            submit_higher, add_reverse_relation
        )
        self.assertEqual(outcomes.count("ok"), 1)
        self.assertEqual(sum(isinstance(item, DataAssetServiceError) for item in outcomes), 1)
        higher.refresh_from_db()
        self.assertEqual(higher.status, DataAsset.STATUS_SUBMITTED)
        self.assertFalse(
            DataAssetRelation.objects.filter(
                source_asset=lower,
                target_asset=higher,
                relation_type="supersedes",
            ).exists()
        )

    def test_concurrent_submit_and_context_archive_leave_valid_state(self):
        context = create_context(
            context_code="D2_SAMPLE",
            project=self.project,
            context_type_key="sample",
            profile_key="basic_sample",
            actor=self.owner,
        )
        transition_context(context=context, actor=self.manager, action="activate")
        data_file = DataFile.objects.create(
            file_code="D2_READS",
            file_name="reads.fastq.gz",
            file_path="/not-used/d2-reads.fastq.gz",
            file_size=10,
            sha256="d" * 64,
            availability_status=DataFile.AVAILABILITY_AVAILABLE,
        )
        asset = create_data_asset(
            asset_code="D2_READ_ASSET",
            project=self.project,
            data_type_key="sequence",
            profile_key="raw_read_collection",
            created_by=self.contributor,
            file_memberships=[AssetFileInput(data_file, "read_fastq")],
            context_links=[AssetContextInput(context, "source_sample")],
        )

        def submit():
            transition_data_asset(
                asset=DataAsset.objects.get(pk=asset.pk),
                actor=get_user_model().objects.get(pk=self.contributor.pk),
                action="submit",
            )

        def archive():
            transition_context(
                context=ContextEntity.objects.get(pk=context.pk),
                actor=get_user_model().objects.get(pk=self.owner.pk),
                action="archive",
                reason="D2 concurrent retirement",
            )

        outcomes = self.run_with_project_lock_contention(archive, submit)
        self.assertEqual(outcomes.count("ok"), 1)
        self.assertEqual(
            sum(isinstance(item, (DataAssetServiceError, ContextConflictError)) for item in outcomes),
            1,
            outcomes,
        )
        asset.refresh_from_db()
        context.refresh_from_db()
        self.assertEqual(
            (asset.status, context.status),
            (DataAsset.STATUS_DRAFT, ContextEntity.STATUS_ARCHIVED),
        )

    def test_concurrent_normalized_external_identifier_is_unique(self):
        first = create_context(
            context_code="D2_IDENTIFIER_A", project=self.project,
            context_type_key="sample", profile_key="basic_sample", actor=self.owner,
        )
        second = create_context(
            context_code="D2_IDENTIFIER_B", project=self.project,
            context_type_key="sample", profile_key="basic_sample", actor=self.owner,
        )

        def register(context_id, display_value):
            def operation():
                add_external_identifier(
                    namespace_key="biosample",
                    display_value=display_value,
                    context=ContextEntity.objects.get(pk=context_id),
                    actor=get_user_model().objects.get(pk=self.owner.pk),
                )
            return operation

        outcomes = self.run_concurrently([
            register(first.pk, " samn7654321 "),
            register(second.pk, "SAMN7654321"),
        ])
        self.assertEqual(outcomes.count("ok"), 1)
        self.assertEqual(sum(isinstance(item, ExternalIdentifierConflict) for item in outcomes), 1)
        self.assertEqual(
            ExternalIdentifier.objects.filter(normalized_value="SAMN7654321").count(), 1
        )

    def test_concurrent_edit_and_submit_cannot_edit_frozen_asset(self):
        context = create_context(
            context_code="D2_EDIT_SAMPLE", project=self.project,
            context_type_key="sample", profile_key="basic_sample", actor=self.owner,
        )
        transition_context(context=context, actor=self.manager, action="activate")
        data_file = DataFile.objects.create(
            file_code="D2_EDIT_FILE", file_name="reads.fastq.gz",
            file_path="/not-used/d2-edit.fastq.gz", file_size=10,
            sha256="e" * 64, availability_status=DataFile.AVAILABILITY_AVAILABLE,
        )
        asset = create_data_asset(
            asset_code="D2_EDIT_ASSET", project=self.project,
            data_type_key="sequence", profile_key="raw_read_collection",
            created_by=self.contributor,
            file_memberships=[AssetFileInput(data_file, "read_fastq")],
            context_links=[AssetContextInput(context, "source_sample")],
        )

        def edit():
            update_data_asset_draft(
                asset=DataAsset.objects.get(pk=asset.pk),
                actor=get_user_model().objects.get(pk=self.contributor.pk),
                name="Concurrent edit",
            )

        def submit():
            transition_data_asset(
                asset=DataAsset.objects.get(pk=asset.pk),
                actor=get_user_model().objects.get(pk=self.contributor.pk),
                action="submit",
            )

        outcomes = self.run_with_project_lock_contention(submit, edit)
        self.assertEqual(outcomes.count("ok"), 1)
        self.assertEqual(sum(isinstance(item, DataAssetServiceError) for item in outcomes), 1)
        asset.refresh_from_db()
        self.assertEqual(asset.status, DataAsset.STATUS_SUBMITTED)
        self.assertEqual(asset.name, "")

    def test_concurrent_approve_and_return_have_one_winner(self):
        context = create_context(
            context_code="D2_REVIEW_SAMPLE", project=self.project,
            context_type_key="sample", profile_key="basic_sample", actor=self.owner,
        )
        transition_context(context=context, actor=self.manager, action="activate")
        data_file = DataFile.objects.create(
            file_code="D2_REVIEW_FILE", file_name="reads.fastq.gz",
            file_path="/not-used/d2-review.fastq.gz", file_size=10,
            sha256="f" * 64, availability_status=DataFile.AVAILABILITY_AVAILABLE,
        )
        asset = create_data_asset(
            asset_code="D2_REVIEW_ASSET", project=self.project,
            data_type_key="sequence", profile_key="raw_read_collection",
            created_by=self.contributor,
            file_memberships=[AssetFileInput(data_file, "read_fastq")],
            context_links=[AssetContextInput(context, "source_sample")],
        )
        transition_data_asset(asset=asset, actor=self.contributor, action="submit")

        def approve():
            transition_data_asset(
                asset=DataAsset.objects.get(pk=asset.pk),
                actor=get_user_model().objects.get(pk=self.manager.pk),
                action="approve",
            )

        def return_to_draft():
            transition_data_asset(
                asset=DataAsset.objects.get(pk=asset.pk),
                actor=get_user_model().objects.get(pk=self.manager.pk),
                action="return",
                reason="D2 concurrent review correction",
            )

        outcomes = self.run_with_project_lock_contention(approve, return_to_draft)
        self.assertEqual(outcomes.count("ok"), 1)
        self.assertEqual(sum(isinstance(item, DataAssetServiceError) for item in outcomes), 1)
        asset.refresh_from_db()
        self.assertEqual(asset.status, DataAsset.STATUS_APPROVED)

    def test_concurrent_release_and_reference_archive_preserve_dependency(self):
        reference_file = DataFile.objects.create(
            file_code="D2_REFERENCE_FILE", file_name="genome.fasta",
            file_path="/not-used/d2-reference.fasta", file_size=10,
            sha256="1" * 64, availability_status=DataFile.AVAILABILITY_AVAILABLE,
        )
        reference = create_data_asset(
            asset_code="D2_REFERENCE", project=self.project,
            data_type_key="sequence", profile_key="reference_genome",
            created_by=self.owner,
            file_memberships=[AssetFileInput(reference_file, "genome_fasta")],
        )
        transition_data_asset(asset=reference, actor=self.owner, action="submit")
        transition_data_asset(asset=reference, actor=self.manager, action="approve")
        transition_data_asset(asset=reference, actor=self.owner, action="release")

        table_file = DataFile.objects.create(
            file_code="D2_TABLE_FILE", file_name="result.tsv",
            file_path="/not-used/d2-result.tsv", file_size=10,
            sha256="2" * 64, availability_status=DataFile.AVAILABILITY_AVAILABLE,
        )
        dependent = create_data_asset(
            asset_code="D2_DEPENDENT", project=self.project,
            data_type_key="table", profile_key="research_table",
            created_by=self.owner,
            file_memberships=[AssetFileInput(table_file, "primary_table")],
        )
        add_asset_relation(
            asset=dependent, target_asset=reference,
            relation_type="uses_reference", actor=self.owner,
        )
        transition_data_asset(asset=dependent, actor=self.owner, action="submit")
        transition_data_asset(asset=dependent, actor=self.manager, action="approve")

        def release_dependent():
            transition_data_asset(
                asset=DataAsset.objects.get(pk=dependent.pk),
                actor=get_user_model().objects.get(pk=self.owner.pk),
                action="release",
            )

        def archive_reference():
            transition_data_asset(
                asset=DataAsset.objects.get(pk=reference.pk),
                actor=get_user_model().objects.get(pk=self.owner.pk),
                action="archive",
                reason="D2 concurrent reference retirement",
            )

        outcomes = self.run_with_project_lock_contention(
            release_dependent, archive_reference
        )
        self.assertEqual(outcomes.count("ok"), 1)
        self.assertEqual(sum(isinstance(item, DataAssetServiceError) for item in outcomes), 1)
        dependent.refresh_from_db()
        reference.refresh_from_db()
        self.assertEqual(dependent.status, DataAsset.STATUS_RELEASED)
        self.assertEqual(reference.status, DataAsset.STATUS_RELEASED)
