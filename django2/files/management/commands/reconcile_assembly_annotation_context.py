"""Reconcile default Assembly and Annotation context from existing new-only relations.

The command deliberately does not create files or infer relationships from paths.  It
only promotes an unambiguous, curated Assembly/Annotation already present in the
database, and reports every uncertain case for manual review.
"""

import csv
import os
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction

from files.models import Accession, Annotation, Assembly, FileRelation
from files.services.genome_list_service import GENOME_FILE_ROLES


def _timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _is_placeholder_assembly(assembly):
    return assembly.name == "default" and not assembly.assembly_code


def _is_annotation_role(file_role):
    role = (file_role or "").lower()
    return role == "annotation" or role.startswith("annotation_") or role.endswith("_annotation")


class Command(BaseCommand):
    help = (
        "Safely select unambiguous curated Assembly/Annotation defaults from "
        "existing DataFile + FileRelation context."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--output-dir", default=".")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]
        output_dir = options["output_dir"]
        os.makedirs(output_dir, exist_ok=True)

        stats = {
            "dry_run": dry_run,
            "scanned_accession_count": 0,
            "selected_curated_assembly_count": 0,
            "updated_default_assembly_count": 0,
            "selected_annotation_count": 0,
            "updated_default_annotation_count": 0,
            "unchanged_count": 0,
            "review_required_count": 0,
        }
        details = []

        accessions = Accession.objects.prefetch_related("assemblies__annotations").order_by("id")
        if limit:
            accessions = accessions[:limit]

        for accession in accessions:
            stats["scanned_accession_count"] += 1
            result = self._reconcile_accession(accession, dry_run=dry_run)
            if result["status"] == "unchanged":
                stats["unchanged_count"] += 1
            elif result["status"] == "review_required":
                stats["review_required_count"] += 1
            if result["selected_assembly"]:
                stats["selected_curated_assembly_count"] += 1
            if result["assembly_changed"]:
                stats["updated_default_assembly_count"] += 1
            if result["selected_annotation"]:
                stats["selected_annotation_count"] += 1
            if result["annotation_changed"]:
                stats["updated_default_annotation_count"] += 1
            details.append(result)

        stamp = _timestamp()
        log_path = os.path.join(output_dir, f"reconcile_assembly_annotation_context_log_{stamp}.txt")
        details_path = os.path.join(output_dir, f"reconcile_assembly_annotation_context_details_{stamp}.tsv")
        self._write_log(log_path, stats)
        self._write_details(details_path, details)

        for key, value in stats.items():
            self.stdout.write(f"{key}={value}")
        self.stdout.write(f"log={log_path}")
        self.stdout.write(f"details={details_path}")

    def _reconcile_accession(self, accession, *, dry_run):
        assemblies = list(accession.assemblies.all().order_by("id"))
        current_default = next((item for item in assemblies if item.is_default), None)
        curated = [item for item in assemblies if not _is_placeholder_assembly(item)]

        result = {
            "accession_id": accession.id,
            "accession": accession.accession,
            "current_default_assembly": self._assembly_label(current_default),
            "selected_assembly": "",
            "current_default_annotation": "",
            "selected_annotation": "",
            "assembly_changed": False,
            "annotation_changed": False,
            "status": "unchanged",
            "reason": "",
            "suggested_action": "",
        }

        if not assemblies:
            result.update(
                status="review_required",
                reason="no Assembly exists for accession",
                suggested_action="Import an Assembly manifest or reconcile a verified genome relation.",
            )
            return result

        candidates = [assembly for assembly in curated if self._has_genome_relation(assembly)]
        if not candidates and len(curated) == 1:
            # A manifest Assembly can be the canonical context even before its file
            # relation is imported; keep it visible but require file-link review.
            candidates = curated

        if len(candidates) != 1:
            if not curated and self._has_genome_relation(current_default):
                result.update(
                    status="review_required",
                    reason="only generated default Assembly has a genome relation",
                    suggested_action="Import or curate the real Assembly metadata before hiding the default Assembly.",
                )
            else:
                result.update(
                    status="review_required",
                    reason=f"ambiguous curated Assembly candidates: {len(candidates)}",
                    suggested_action="Choose one canonical Assembly and ensure its genome FileRelation is verified.",
                )
            return result

        selected_assembly = candidates[0]
        result["selected_assembly"] = self._assembly_label(selected_assembly)
        result["assembly_changed"] = selected_assembly.id != getattr(current_default, "id", None)

        annotations = list(selected_assembly.annotations.all().order_by("id"))
        current_annotation = next((item for item in annotations if item.is_default), None)
        result["current_default_annotation"] = self._annotation_label(current_annotation)
        annotation_candidates = [item for item in annotations if self._has_annotation_relation(item)]
        if not annotation_candidates and len(annotations) == 1:
            annotation_candidates = annotations

        if len(annotation_candidates) > 1:
            result.update(
                status="review_required",
                reason="ambiguous Annotation candidates for selected Assembly",
                suggested_action="Choose one canonical Annotation and verify its annotation FileRelation.",
            )
            return result

        selected_annotation = annotation_candidates[0] if annotation_candidates else None
        if selected_annotation:
            result["selected_annotation"] = self._annotation_label(selected_annotation)
            result["annotation_changed"] = selected_annotation.id != getattr(current_annotation, "id", None)

        if not selected_annotation and annotations:
            result.update(
                status="review_required_count",
                reason="Annotation exists but no verified annotation FileRelation is available",
                suggested_action="Link the annotation DataFile through FileRelation, then run this command again.",
            )
            return result

        if result["assembly_changed"] or result["annotation_changed"]:
            if not dry_run:
                with transaction.atomic():
                    if result["assembly_changed"]:
                        accession.assemblies.filter(is_default=True).exclude(id=selected_assembly.id).update(is_default=False)
                        Assembly.objects.filter(id=selected_assembly.id).update(is_default=True)
                    if selected_annotation and result["annotation_changed"]:
                        selected_assembly.annotations.filter(is_default=True).exclude(id=selected_annotation.id).update(is_default=False)
                        Annotation.objects.filter(id=selected_annotation.id).update(is_default=True)
            result.update(
                status="updated",
                reason="unambiguous curated context selected",
                suggested_action="No further action required.",
            )
        else:
            result.update(reason="current context is already canonical", suggested_action="No action required.")
        return result

    def _has_genome_relation(self, assembly):
        return FileRelation.objects.filter(
            related_type="assembly",
            related_id=str(assembly.id),
            file_role__in=GENOME_FILE_ROLES,
        ).exists()

    def _has_annotation_relation(self, annotation):
        roles = FileRelation.objects.filter(
            related_type="annotation",
            related_id=str(annotation.id),
        ).values_list("file_role", flat=True)
        return any(_is_annotation_role(role) for role in roles)

    @staticmethod
    def _assembly_label(assembly):
        if not assembly:
            return ""
        return assembly.assembly_code or assembly.assembly_name or assembly.name

    @staticmethod
    def _annotation_label(annotation):
        if not annotation:
            return ""
        return annotation.annotation_code or annotation.annotation_name or annotation.name

    @staticmethod
    def _write_log(path, stats):
        with open(path, "w", encoding="utf-8", newline="") as handle:
            for key, value in stats.items():
                handle.write(f"{key}: {value}\n")

    @staticmethod
    def _write_details(path, rows):
        fields = [
            "accession_id",
            "accession",
            "current_default_assembly",
            "selected_assembly",
            "current_default_annotation",
            "selected_annotation",
            "assembly_changed",
            "annotation_changed",
            "status",
            "reason",
            "suggested_action",
        ]
        with open(path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)
