from django.core.management.base import BaseCommand, CommandError

from files.models import FileRelation
from files.services.fasta_index_service import build_and_link_fasta_index


class Command(BaseCommand):
    help = 'Build and register .fai sidecar files for current genome FASTA relations.'

    def add_arguments(self, parser):
        parser.add_argument('--data-file-id', action='append', type=int, dest='data_file_ids')

    def handle(self, *args, **options):
        queryset = (
            FileRelation.objects.select_related('file')
            .filter(file_role__in=('genome_fasta', 'genome'), file__is_current=True)
            .order_by('id')
        )
        if options['data_file_ids']:
            queryset = queryset.filter(file_id__in=options['data_file_ids'])
        relation_groups = {}
        for relation in queryset:
            relation_groups.setdefault(relation.file_id, []).append(relation)
        built = failed = 0
        for relations in relation_groups.values():
            relation = relations[0]
            try:
                index_file, sequence_count = build_and_link_fasta_index(
                    genome_file=relation.file,
                    related_type=relation.related_type,
                    related_id=relation.related_id,
                    related_code=relation.related_code,
                )
                for extra_relation in relations[1:]:
                    FileRelation.objects.update_or_create(
                        file=index_file,
                        related_type=extra_relation.related_type,
                        related_id=str(extra_relation.related_id),
                        file_role='genome_index',
                        defaults={
                            'related_code': extra_relation.related_code,
                            'is_primary': False,
                            'description': f'Index for genome DataFile {relation.file_id}',
                        },
                    )
            except Exception as exc:
                failed += 1
                self.stderr.write(f'file={relation.file_id} failed: {exc}')
                continue
            built += 1
            self.stdout.write(
                f'file={relation.file_id} index={index_file.id} sequences={sequence_count}'
            )
        if options['data_file_ids'] and not relation_groups:
            raise CommandError('No current genome FASTA relation matched --data-file-id')
        self.stdout.write(self.style.SUCCESS(f'FASTA indexes: built={built} failed={failed}'))
