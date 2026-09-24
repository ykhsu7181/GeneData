from django.core.management.base import BaseCommand, CommandError

from files.models import Annotation, FileRelation
from files.services.annotation_feature_index_service import (
    AnnotationIndexUnavailable,
    build_annotation_feature_index,
)


class Command(BaseCommand):
    help = 'Build persistent AnnotationFeature indexes from current annotation FileRelations.'

    def add_arguments(self, parser):
        parser.add_argument('--annotation-id', action='append', type=int, dest='annotation_ids')
        parser.add_argument('--force', action='store_true')
        parser.add_argument('--batch-size', type=int, default=2000)

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        if batch_size < 1:
            raise CommandError('--batch-size must be positive')
        related_ids = []
        for related_id in FileRelation.objects.filter(
            related_type='annotation',
            file_role='annotation',
            file__is_current=True,
        ).values_list('related_id', flat=True):
            try:
                related_ids.append(int(related_id))
            except (TypeError, ValueError):
                continue
        queryset = Annotation.objects.filter(id__in=related_ids).order_by('id')
        if options['annotation_ids']:
            queryset = Annotation.objects.filter(id__in=options['annotation_ids']).order_by('id')
        built = skipped = failed = 0
        for annotation in queryset.iterator():
            try:
                feature_index, changed = build_annotation_feature_index(
                    annotation, force=options['force'], batch_size=batch_size
                )
            except AnnotationIndexUnavailable as exc:
                failed += 1
                self.stderr.write(f'annotation={annotation.id} skipped: {exc}')
                continue
            except Exception as exc:
                failed += 1
                self.stderr.write(f'annotation={annotation.id} failed: {exc}')
                continue
            if changed:
                built += 1
                self.stdout.write(
                    f'annotation={annotation.id} indexed features={feature_index.feature_count}'
                )
            else:
                skipped += 1
        self.stdout.write(self.style.SUCCESS(
            f'annotation indexes: built={built} unchanged={skipped} failed={failed}'
        ))
