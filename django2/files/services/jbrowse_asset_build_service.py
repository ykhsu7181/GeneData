"""Build and register DataAsset-owned JBrowse auxiliary files and caches."""

from contextlib import contextmanager
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings

from files.services.annotation_asset_feature_index_service import (
    build_annotation_asset_feature_index,
)
from files.services.data_asset_auxiliary_service import (
    register_generated_auxiliary_file,
    require_data_asset_maintenance_permission,
)
from files.services.fasta_index_core import build_fasta_index
from files.services.jbrowse_asset_service import (
    resolve_jbrowse_asset_context,
    resolve_jbrowse_reference_asset,
)
from files.services.reference_name_core import build_reference_name_payload


class JBrowseAssetBuildError(RuntimeError):
    pass


def build_reference_fasta_index(
    reference_asset_or_code, *, user=None, registry=None, roots=None, output_root=None
):
    asset, fasta, _ = resolve_jbrowse_reference_asset(
        reference_asset_or_code, user=user, registry=registry, roots=roots
    )
    target = _asset_dir(asset, output_root) / "reference.fasta.fai"
    with _restore_target_on_error(target):
        _, entries = build_fasta_index(fasta.file_path, str(target))
        data_file = register_generated_auxiliary_file(
            asset=asset, actor=user, file_role="fasta_index", path=target, registry=registry
        )
    return data_file, len(entries)


def build_annotation_tabix_index(
    annotation_asset_or_code,
    *,
    user=None,
    registry=None,
    roots=None,
    output_root=None,
    tabix_command=None,
):
    context = resolve_jbrowse_asset_context(
        annotation_asset_or_code, user=user, registry=registry, roots=roots
    )
    source = context.annotation_gff
    if not source.file_path.lower().endswith((".gff.gz", ".gff3.gz")):
        raise JBrowseAssetBuildError("annotation_gff must already be bgzip-compressed")
    command = shutil.which(
        str(tabix_command or getattr(settings, "GENEDATA_TABIX_COMMAND", "tabix"))
    )
    if not command:
        raise JBrowseAssetBuildError("tabix command is unavailable")
    target = _asset_dir(context.annotation_asset, output_root) / "annotation.gff3.gz.tbi"
    with _restore_target_on_error(target):
        with tempfile.TemporaryDirectory(prefix=".tabix-", dir=str(target.parent)) as workspace:
            staged_gff = Path(workspace) / "annotation.gff3.gz"
            shutil.copyfile(source.file_path, staged_gff)
            completed = subprocess.run(
                [command, "-f", "-p", "gff", str(staged_gff)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            staged_tbi = Path(f"{staged_gff}.tbi")
            if completed.returncode or not staged_tbi.is_file() or staged_tbi.stat().st_size == 0:
                detail = completed.stderr.decode("utf-8", errors="replace").strip()
                raise JBrowseAssetBuildError(f"tabix failed: {detail}")
            os.replace(staged_tbi, target)
        return register_generated_auxiliary_file(
            asset=context.annotation_asset,
            actor=user,
            file_role="tabix_index",
            path=target,
            registry=registry,
        )


def build_annotation_feature_index_for_asset(
    annotation_asset_or_code, *, user=None, registry=None, roots=None, force=False,
    batch_size=2000,
):
    context = resolve_jbrowse_asset_context(
        annotation_asset_or_code, user=user, registry=registry, roots=roots
    )
    return build_annotation_asset_feature_index(
        context.annotation_asset,
        user=user,
        registry=registry,
        roots=roots,
        force=force,
        batch_size=batch_size,
    )


def build_reference_name_cache(
    annotation_asset_or_code, *, user=None, registry=None, roots=None, output_root=None
):
    context, payload = inspect_reference_name_cache(
        annotation_asset_or_code,
        user=user,
        registry=registry,
        roots=roots,
    )
    require_data_asset_maintenance_permission(asset=context.annotation_asset, actor=user)
    target = _asset_dir(context.annotation_asset, output_root) / "refname-aliases.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, target)
    return target, payload


def inspect_reference_name_cache(
    annotation_asset_or_code, *, user=None, registry=None, roots=None
):
    """Validate refName inputs and build the cache payload without writing it."""
    context = resolve_jbrowse_asset_context(
        annotation_asset_or_code,
        user=user,
        registry=registry,
        roots=roots,
        require_indexes=False,
    )
    _, genome_fasta, fasta_index = resolve_jbrowse_reference_asset(
        context.reference_asset,
        user=user,
        registry=registry,
        roots=roots,
        require_index=True,
    )
    payload = build_reference_name_payload(genome_fasta, fasta_index)
    payload.update({
        "annotation_asset_code": context.annotation_asset.asset_code,
        "reference_asset_code": context.reference_asset.asset_code,
        "fasta_file_id": genome_fasta.id,
        "fasta_index_file_id": fasta_index.id,
    })
    return context, payload


def _asset_dir(asset, output_root):
    configured = output_root or getattr(settings, "GENEDATA_JBROWSE_DATA_DIR", None)
    if not configured:
        configured = Path(settings.GENEDATA_DERIVED_DATA_DIR) / "jbrowse"
    derived_root = Path(settings.GENEDATA_DERIVED_DATA_DIR).resolve()
    configured_root = Path(configured).resolve()
    asset_dir = (configured_root / "assets" / asset.asset_code).resolve()
    if not _is_relative_to(configured_root, derived_root) or not _is_relative_to(
        asset_dir, derived_root
    ):
        raise JBrowseAssetBuildError("JBrowse output must stay under the derived data root")
    return asset_dir


def _is_relative_to(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


@contextmanager
def _restore_target_on_error(target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        raise JBrowseAssetBuildError("Generated target must not be a symbolic link")
    backup = None
    if target.exists():
        descriptor, backup_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
        os.close(descriptor)
        backup = Path(backup_name)
        shutil.copy2(target, backup)
    try:
        yield
    except Exception:
        if target.exists():
            target.unlink()
        if backup is not None:
            os.replace(backup, target)
        raise
    else:
        if backup is not None and backup.exists():
            backup.unlink()
