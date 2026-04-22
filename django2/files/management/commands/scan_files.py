import os
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from files.models import FileType, GenomeFile, Organism, Accession

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scan manual files directory and sync file records.'

    def handle(self, *args, **options):
        directory = settings.MANUAL_FILES_DIR
        files_added = 0
        files_removed = 0

        if not os.path.exists(directory):
            self.stdout.write(self.style.ERROR(f'Manual files directory not found: {directory}'))
            return

        self.stdout.write(f'Scanning manual files in: {directory}')

        existing_files = set()
        for root, _, files in os.walk(directory):
            for filename in files:
                existing_files.add(os.path.join(root, filename))

        # Remove DB records whose file is missing on disk
        for file_obj in GenomeFile.objects.all():
            if file_obj.file_path not in existing_files:
                self.stdout.write(f'Removing missing file record: {file_obj.name}')
                file_obj.delete()
                files_removed += 1

        # Build extension map
        extension_map = {ft.extension: ft for ft in FileType.objects.all()}
        tissue_types = ['all', 'root', 'stem', 'leaf', 'panicles', 'shoot']
        valid_categories = {choice[0] for choice in GenomeFile.FILE_CATEGORY_CHOICES}

        def resolve_accession_assembly(organism_code):
            accession_obj = Accession.objects.filter(accession=organism_code).first()
            if not accession_obj:
                return None, None
            assembly_obj = accession_obj.default_assembly or accession_obj.assemblies.first()
            return accession_obj, assembly_obj

        def get_file_type(path, filename):
            parts = filename.split('.')
            extension = parts[-1] if len(parts) > 1 else ''
            if extension in ['gz', 'zip', 'bz2', 'xz'] and len(parts) > 2:
                extension = f"{parts[-2]}.{parts[-1]}"
            file_type = extension_map.get(extension)
            if not file_type:
                file_type = FileType.objects.create(
                    name=extension.upper() if extension else 'UNKNOWN',
                    extension=extension
                )
                extension_map[extension] = file_type
            return file_type

        for root, _, files in os.walk(directory):
            for filename in files:
                file_path = os.path.join(root, filename)

                parts = filename.split('.')
                if len(parts) < 3:
                    continue

                file_type = get_file_type(file_path, filename)

                category = None
                organism = None

                # transcriptome.<tissue>.<organism>.<ext>
                if parts[0] == 'transcriptome' and parts[1] in tissue_types and len(parts) >= 4:
                    category = f"transcriptome.{parts[1]}"
                    organism = parts[2]
                else:
                    category = parts[0]
                    organism = parts[1]

                if not category or not organism:
                    continue

                if category not in valid_categories:
                    continue

                try:
                    Organism.objects.get_or_create(code=organism, defaults={'name': organism})
                except Exception as e:
                    logger.warning(f'Failed to ensure organism {organism}: {e}')

                existing = GenomeFile.objects.filter(organism=organism, category=category).first()
                if existing:
                    updated = False
                    if existing.file_path != file_path:
                        existing.file_path = file_path
                        existing.name = filename
                        existing.size = os.path.getsize(file_path)
                        updated = True
                    if category == 'variableBlocks' and not existing.assembly:
                        accession_obj, assembly_obj = resolve_accession_assembly(organism)
                        if accession_obj:
                            existing.accession = accession_obj
                        if assembly_obj:
                            existing.assembly = assembly_obj
                        updated = True
                    if updated:
                        existing.save()
                        self.stdout.write(f'Updated file record: {filename}')
                    continue

                accession_obj = None
                assembly_obj = None
                if category == 'variableBlocks':
                    accession_obj, assembly_obj = resolve_accession_assembly(organism)

                GenomeFile.objects.create(
                    name=filename,
                    organism=organism,
                    category=category,
                    file_path=file_path,
                    file_type=file_type,
                    size=os.path.getsize(file_path),
                    accession=accession_obj,
                    assembly=assembly_obj,
                )
                files_added += 1

        self.stdout.write(self.style.SUCCESS(f'Added {files_added} files, removed {files_removed} missing records.'))
