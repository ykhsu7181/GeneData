from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FileTypeViewSet, GenomeFileViewSet,
    OrganismViewSet, FileCategoryViewSet,
    admin_login, admin_files_list, admin_delete_file,
    admin_batch_delete, admin_batch_download, admin_upload_file, admin_statistics,
    admin_rescan_files, admin_create_accession, admin_update_accession,
    admin_delete_accession, admin_data_management_list,
    admin_upload_data_file, admin_download_data_file, admin_delete_data_file,
    admin_batch_delete_accessions, admin_subpopulation_stats,
    accession_detail, download_datafile
)
from .query_views import (
    query_annotation_data,
    query_annotation_organisms,
    query_centromere,
    query_chromosome_length,
    query_chromosomes,
    query_codon_data,
    query_coreblocks,
    query_data_overview,
    query_data_overview_files,
    query_download_transcriptome,
    query_organisms,
    query_paginated_overview,
    query_paginated_transcriptome_overview,
    query_rna_data,
    query_sub_populations,
    query_supplementary_data,
    query_tes,
    query_variableblocks,
)


# 先定义自定义路径，避免与router冲突
urlpatterns = [
    path('accessions/<str:accession>/', accession_detail, name='accession-detail'),
    path('data-files/<int:file_id>/download/', download_datafile, name='datafile-download'),
    path('query/organisms/', query_organisms, name='query-organisms'),
    path('query/annotation-organisms/', query_annotation_organisms, name='query-annotation-organisms'),
    path('query/sub-populations/', query_sub_populations, name='query-sub-populations'),
    path('query/supplementary-data/', query_supplementary_data, name='query-supplementary-data'),
    path('query/data-overview/', query_data_overview, name='query-data-overview'),
    path('query/data-overview-files/', query_data_overview_files, name='query-data-overview-files'),
    path('query/paginated-overview/', query_paginated_overview, name='query-paginated-overview'),
    path('query/paginated-transcriptome-overview/', query_paginated_transcriptome_overview, name='query-paginated-transcriptome-overview'),
    path('query/download-transcriptome/', query_download_transcriptome, name='query-download-transcriptome'),
    path('query/annotation-data/', query_annotation_data, name='query-annotation-data'),
    path('query/chromosomes/', query_chromosomes, name='query-chromosomes'),
    path('query/chromosome-length/', query_chromosome_length, name='query-chromosome-length'),
    path('query/tes/', query_tes, name='query-tes'),
    path('query/centromere/', query_centromere, name='query-centromere'),
    path('query/core-blocks/', query_coreblocks, name='query-coreblocks'),
    path('query/variable-blocks/', query_variableblocks, name='query-variableblocks'),
    path('query/rna-data/', query_rna_data, name='query-rna-data'),
    path('query/codon-data/', query_codon_data, name='query-codon-data'),
    path('codonw/analysis/', GenomeFileViewSet.as_view({'post': 'codonw_analysis'}), name='codonw-analysis'),
    path('codonw/status/<str:task_id>/', GenomeFileViewSet.as_view({'get': 'codonw_status'}), name='codonw-status'),
    path('codonw/history/', GenomeFileViewSet.as_view({'get': 'codonw_history'}), name='codonw-history'),
    path('codonw/download/<str:task_id>/', GenomeFileViewSet.as_view({'get': 'codonw_download'}), name='codonw-download'),
    path('codonw/delete/<str:task_id>/', GenomeFileViewSet.as_view({'delete': 'codonw_delete'}), name='codonw-delete'),
    path('codonw/results/<str:task_id>/', GenomeFileViewSet.as_view({'get': 'codonw_results'}), name='codonw-results'),
    path('codonw/result-upload/', GenomeFileViewSet.as_view({'post': 'codonw_result_upload'}), name='codonw-result-upload'),
    path('download-transcriptome/', GenomeFileViewSet.as_view({'get': 'download_transcriptome'}), name='download-transcriptome'),
    path('transcriptome-types/', GenomeFileViewSet.as_view({'get': 'transcriptome_types'}), name='transcriptome-types'),
    path('genome-files/get_chromosomes/', GenomeFileViewSet.as_view({'get': 'get_chromosomes'}), name='get-chromosomes'),
    path('genome-files/get_tes/', GenomeFileViewSet.as_view({'get': 'get_tes'}), name='get-tes'),
    path('genome-files/get_centromere/', GenomeFileViewSet.as_view({'get': 'get_centromere'}), name='get-centromere'),
    path('genome-files/get_coreblocks/', GenomeFileViewSet.as_view({'get': 'get_coreblocks'}), name='get-coreblocks'),
    path('genome-files/get_variableblocks/', GenomeFileViewSet.as_view({'get': 'get_variableblocks'}), name='get-variableblocks'),
    path('genome-files/get_rna_data/', GenomeFileViewSet.as_view({'get': 'get_rna_data'}), name='get-rna-data'),
    path('genome-files/paginated_transcriptome_overview/', GenomeFileViewSet.as_view({'get': 'paginated_transcriptome_overview'}), name='paginated-transcriptome-overview'),
    path('genome-files/get_codon_data/', GenomeFileViewSet.as_view({'get': 'get_codon_data'}), name='get-codon-data'),
    path('genome-files/get_annotation_data/', GenomeFileViewSet.as_view({'get': 'get_annotation_data'}), name='get-annotation-data'),
    path('genome-files/supplementary_data/', GenomeFileViewSet.as_view({'get': 'supplementary_data'}), name='supplementary-data'),
    path('genome-files/paginated_overview/', GenomeFileViewSet.as_view({'get': 'paginated_overview'}), name='paginated-overview'),
    path('genome-files/all_files/', GenomeFileViewSet.as_view({'get': 'all_files'}), name='all-files'),
    path('genome-files/sub_populations/', GenomeFileViewSet.as_view({'get': 'sub_populations'}), name='sub-populations'),

    # 管理后台API路由
    path('login/', admin_login, name='admin-login'),
    path('files/', admin_files_list, name='admin-files-list'),
    path('files/<int:file_id>/delete/', admin_delete_file, name='admin-delete-file'),
    path('files/batch-delete/', admin_batch_delete, name='admin-batch-delete'),
    path('files/batch-download/', admin_batch_download, name='admin-batch-download'),
    path('files/upload/', admin_upload_file, name='admin-upload-file'),
    path('statistics/', admin_statistics, name='admin-statistics'),
    path('subpopulation-stats/', admin_subpopulation_stats, name='admin-subpopulation-stats'),
    path('rescan/', admin_rescan_files, name='admin-rescan-files'),

    # 数据表格管理API
    path('data-management/list/', admin_data_management_list, name='admin-data-management-list'),
    path('data-management/accession/', admin_create_accession, name='admin-create-accession'),
    path('data-management/accession/<str:accession>/update/', admin_update_accession, name='admin-update-accession'),
    path('data-management/accession/<str:accession>/delete/', admin_delete_accession, name='admin-delete-accession'),
    path('data-management/batch-delete/', admin_batch_delete_accessions, name='admin-batch-delete-accessions'),

    # 文件管理API
    path('data-management/upload-file/', admin_upload_data_file, name='admin-upload-data-file'),
    path('data-management/download-file/<str:accession>/<str:file_type>/', admin_download_data_file, name='admin-download-data-file'),
    path('data-management/delete-file/<str:accession>/<str:file_type>/', admin_delete_data_file, name='admin-delete-data-file'),
]

router = DefaultRouter()
router.register('file-types', FileTypeViewSet)
router.register('genome-files', GenomeFileViewSet)
router.register('organisms', OrganismViewSet)
router.register('file-categories', FileCategoryViewSet)

# 将router的URLs添加到现有的urlpatterns
urlpatterns += [
    path('', include(router.urls)),
]
