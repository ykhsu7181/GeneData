# Unified Accession Page Design

## Goal

Replace the existing Accession card page and Accession detail table page with one desktop Accession page matching the approved mockup.

## Route Compatibility

- `/accession-card?accession=<code>` renders the unified page.
- `/accession-detail?accession=<code>` renders the same component.
- Neither route redirects.
- The page does not render a back-to-list action.

## Page Structure

1. Breadcrumb and title `Accession · <code>`.
2. Species and subpopulation tags.
3. Six summary cards: sample count, dataset count, file count, total size, assembly count, annotation count.
4. Main content:
   - Basic information, including description.
   - Assembly / 组装版本 table.
   - Annotation / 注释版本 table.
   - Related files from DataFile + FileRelation.
5. Right column:
   - Relationship overview reusing the existing Accession Structure graph and interactions.
   - Quick section navigation.
   - Data readiness status.
   - Creation and update information.

## Data Rules

- Accession, Assembly, Annotation, Sample, Dataset, DataFile and FileRelation remain the authoritative sources.
- File inventory includes relations attached to the accession and its assemblies and annotations.
- DataFile is deduplicated by ID for file count and total size.
- Dataset and Project information is derived from the related DataFile dataset links.
- No GenomeFile or organism fallback is introduced.
- File downloads use `datafile_download_url`.
- Missing values render as `-`; empty sections render compatible empty rows.

## API Extension

Extend `GET /gd/api/files/accessions/<accession>/` without changing existing fields. Add:

- accession species information;
- `summary.sample_count`, `dataset_count`, `total_size`, `total_size_display`;
- `projects`, `datasets`;
- enriched `files` with file type, dataset and relation object labels;
- `data_status`;
- creation/update metadata.

## Component Boundary

- `AccessionDetailTableView.vue` becomes the unified page component.
- The existing Accession Structure calculation remains in this component.
- `AccessionCard.vue` is no longer routed to but may remain temporarily as an archived source file.
- Both routes lazy-load `AccessionDetailTableView.vue`.

## Verification

- Backend tests verify aggregation, deduplication and DataFile-only downloads.
- Frontend static tests verify both routes share one component and required sections exist.
- Existing accession integration tests, Django checks, migration check and frontend production build remain green.

