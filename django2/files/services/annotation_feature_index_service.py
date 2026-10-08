import hashlib
import os

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from files.models import AnnotationFeature, AnnotationFeatureIndex, FileRelation
from files.parsers.archive import iter_feature_file


class AnnotationIndexUnavailable(RuntimeError):
    def __init__(self, message, *, index_status='missing'):
        super().__init__(message)
        self.index_status = index_status


def select_annotation_source_file(annotation_id):
    relations = list(
        FileRelation.objects.select_related('file')
        .filter(
            related_type='annotation',
            related_id=str(annotation_id),
            file_role='annotation',
            file__is_current=True,
        )
        .order_by('-is_primary', 'id')
    )
    return relations[0].file if relations else None


def get_ready_annotation_index(annotation, service_file):
    try:
        feature_index = AnnotationFeatureIndex.objects.select_related('source_file').get(
            annotation=annotation
        )
    except AnnotationFeatureIndex.DoesNotExist as exc:
        raise AnnotationIndexUnavailable(
            'Annotation index has not been built', index_status='missing'
        ) from exc

    if feature_index.status != AnnotationFeatureIndex.STATUS_READY:
        raise AnnotationIndexUnavailable(
            f'Annotation index is {feature_index.status}', index_status=feature_index.status
        )
    if feature_index.source_file_id != service_file.get('file_id'):
        raise AnnotationIndexUnavailable(
            'Annotation source file changed; rebuild the index', index_status='stale'
        )
    try:
        stat = os.stat(service_file['file_path'])
    except (KeyError, OSError) as exc:
        raise AnnotationIndexUnavailable(
            'Annotation source file is unavailable', index_status='source_missing'
        ) from exc
    if (
        stat.st_size != feature_index.source_file_size
        or stat.st_mtime_ns != feature_index.source_file_mtime_ns
        or (feature_index.source_file_md5 or '') != (feature_index.source_file.md5 or '')
    ):
        raise AnnotationIndexUnavailable(
            'Annotation source file changed; rebuild the index', index_status='stale'
        )
    return feature_index


def annotation_cache_key(prefix, feature_index, *parts):
    normalized = ':'.join(str(part or '') for part in parts)
    digest = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:24]
    indexed_at = getattr(feature_index, 'indexed_at', None)
    index_version = indexed_at.timestamp() if indexed_at else 0
    return (
        f'annotation:{prefix}:{feature_index.pk}:{feature_index.source_file_mtime_ns}:'
        f'{feature_index.feature_count}:{index_version}:{digest}'
    )


def cached_value(key, factory, timeout):
    value = cache.get(key)
    if value is None:
        value = factory()
        cache.set(key, value, timeout)
    return value


def build_annotation_feature_index(annotation, *, force=False, batch_size=2000):
    source_file = select_annotation_source_file(annotation.id)
    if not source_file:
        raise AnnotationIndexUnavailable(
            'No current annotation FileRelation exists', index_status='source_missing'
        )
    try:
        source_stat = os.stat(source_file.file_path)
    except OSError as exc:
        raise AnnotationIndexUnavailable(
            'Annotation source file is unavailable', index_status='source_missing'
        ) from exc

    existing = AnnotationFeatureIndex.objects.filter(annotation=annotation).first()
    if (
        existing
        and not force
        and existing.status == AnnotationFeatureIndex.STATUS_READY
        and existing.source_file_id == source_file.id
        and existing.source_file_size == source_stat.st_size
        and existing.source_file_mtime_ns == source_stat.st_mtime_ns
        and (existing.source_file_md5 or '') == (source_file.md5 or '')
    ):
        return existing, False

    defaults = {
        'source_file': source_file,
        'source_file_size': source_stat.st_size,
        'source_file_mtime_ns': source_stat.st_mtime_ns,
        'source_file_md5': source_file.md5 or '',
        'status': AnnotationFeatureIndex.STATUS_BUILDING,
    }
    feature_index, _ = AnnotationFeatureIndex.objects.update_or_create(
        annotation=annotation, defaults=defaults
    )
    try:
        with transaction.atomic():
            feature_index = AnnotationFeatureIndex.objects.select_for_update().get(pk=feature_index.pk)
            feature_index.features.all().delete()
            chromosomes = set()
            feature_types = set()
            pending = []
            total = 0
            for row in iter_feature_file(source_file.file_path):
                chromosomes.add(row['seqid'])
                if row.get('feature'):
                    feature_types.add(row['feature'])
                pending.append(_feature_from_row(feature_index, row))
                if len(pending) >= batch_size:
                    AnnotationFeature.objects.bulk_create(pending, batch_size=batch_size)
                    total += len(pending)
                    pending = []
            if pending:
                AnnotationFeature.objects.bulk_create(pending, batch_size=batch_size)
                total += len(pending)

            feature_index.source_file = source_file
            feature_index.source_file_size = source_stat.st_size
            feature_index.source_file_mtime_ns = source_stat.st_mtime_ns
            feature_index.source_file_md5 = source_file.md5 or ''
            feature_index.feature_count = total
            feature_index.chromosomes = sorted(chromosomes)
            feature_index.feature_types = sorted(feature_types)
            feature_index.status = AnnotationFeatureIndex.STATUS_READY
            feature_index.error_message = ''
            feature_index.indexed_at = timezone.now()
            feature_index.save()
    except Exception as exc:
        AnnotationFeatureIndex.objects.filter(pk=feature_index.pk).update(
            status=AnnotationFeatureIndex.STATUS_FAILED,
            error_message=str(exc)[:4000],
        )
        raise
    return feature_index, True


def _feature_from_row(feature_index, row):
    return AnnotationFeature(
        feature_index=feature_index,
        source_line=row.get('line_number', 0),
        seqid=row['seqid'],
        source=row.get('source'),
        feature=row.get('feature'),
        start=row['start'],
        end=row['end'],
        length=row['length'],
        score=row.get('score'),
        strand=row.get('strand'),
        phase=row.get('phase'),
        attributes=row.get('attributes') or {},
        sequence_ontology=row.get('sequence_ontology'),
        name=row.get('name'),
    )


def serialize_feature(feature):
    return {
        'seqid': feature.seqid,
        'source': feature.source,
        'feature': feature.feature,
        'start': feature.start,
        'end': feature.end,
        'length': feature.length,
        'score': feature.score,
        'strand': feature.strand,
        'phase': feature.phase,
        'attributes': feature.attributes,
        'line_number': feature.source_line,
        'sequence_ontology': feature.sequence_ontology,
        'name': feature.name,
    }
