<template>
  <el-drawer
    :model-value="modelValue"
    :title="title"
    size="min(760px, 94vw)"
    class="related-files-drawer"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div v-if="loading" class="drawer-state">
      <el-skeleton :rows="8" animated />
    </div>
    <div v-else-if="errorMessage" class="drawer-state">
      <el-empty :description="errorMessage">
        <button class="drawer-action" type="button" @click="$emit('retry')">
          {{ $t('page.assemblyDetail.retry') }}
        </button>
      </el-empty>
    </div>
    <div v-else class="drawer-table-shell">
      <table class="drawer-table">
        <thead>
          <tr>
            <th>{{ $t('common.fileName') }}</th>
            <th>{{ $t('common.fileRole') }}</th>
            <th>{{ $t('page.accessionDetail.columns.relatedType') }}</th>
            <th>{{ $t('common.fileType') }}</th>
            <th>{{ $t('page.accessionDetail.columns.size') }}</th>
            <th>{{ $t('common.download') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in files" :key="item.id">
            <td class="file-name">{{ item.file_name || '-' }}</td>
            <td><span class="role-chip">{{ item.file_role || '-' }}</span></td>
            <td>{{ item.related_type || '-' }}</td>
            <td>{{ item.file_type || '-' }}</td>
            <td>{{ item.size_display || '-' }}</td>
            <td>
              <button class="drawer-action" type="button" @click="$emit('download', item)">
                {{ $t('common.download') }}
              </button>
            </td>
          </tr>
          <tr v-if="!files.length">
            <td colspan="6" class="empty-table-cell">{{ $t('page.assemblyDetail.emptyRelatedFiles') }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </el-drawer>
</template>

<script>
export default {
  name: 'RelatedFilesDrawer',
  props: {
    modelValue: { type: Boolean, default: false },
    title: { type: String, default: '' },
    loading: { type: Boolean, default: false },
    errorMessage: { type: String, default: '' },
    files: { type: Array, default: () => [] }
  },
  emits: ['update:modelValue', 'download', 'retry']
};
</script>

<style scoped>
.drawer-state { padding:18px 0; }
.drawer-table-shell { overflow-x:auto; border:1px solid #e2e9f4; border-radius:10px; }
.drawer-table { width:100%; min-width:680px; border-collapse:collapse; }
.drawer-table th,.drawer-table td { padding:11px 12px; border-bottom:1px solid #e8edf5; text-align:left; font-size:12px; }
.drawer-table th { color:#4b607e; background:#f6f9fd; white-space:nowrap; }
.drawer-table td { color:#1c3359; }
.drawer-table tbody tr:last-child td { border-bottom:0; }
.file-name { max-width:220px; overflow-wrap:anywhere; }
.role-chip { display:inline-block; padding:4px 8px; border-radius:999px; color:#6044bd; background:#f0ecff; font-size:11px; }
.drawer-action { padding:6px 10px; border:1px solid #c9dcfb; border-radius:7px; color:#1760e8; background:#fff; font-size:12px; font-weight:700; cursor:pointer; }
.empty-table-cell { padding:28px !important; color:#8795ab !important; text-align:center !important; }
</style>
