<template>
  <div class="version-table-shell">
    <table class="version-table annotation-version-table">
      <thead>
        <tr>
          <th>{{ $t('page.accessionDetail.columns.annotationVersion') }}</th>
          <th>{{ $t('page.accessionDetail.columns.annotationCode') }}</th>
          <th>{{ $t('page.accessionDetail.columns.sourceMethod') }}</th>
          <th v-if="showAssembly">{{ $t('page.accessionDetail.columns.relatedAssembly') }}</th>
          <th v-if="showDefault">{{ defaultColumnLabel }}</th>
          <th v-if="showActions">{{ $t('common.actions') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in rows" :key="item.id">
          <td>
            <button
              v-if="enableNavigation"
              class="annotation-version-link"
              type="button"
              @click="$emit('view-annotation', item)"
            >
              {{ item.display_name || item.annotation_name || item.name || '-' }}
            </button>
            <span v-else>{{ item.display_name || item.annotation_name || item.name || '-' }}</span>
          </td>
          <td>{{ item.standard_id || item.annotation_code || '-' }}</td>
          <td>{{ item.source_name || item.source_database || '-' }}</td>
          <td v-if="showAssembly">{{ item.assembly_name || '-' }}</td>
          <td v-if="showDefault">
            <span :class="['default-badge', item.is_default ? 'is-default' : '']">
              {{ item.is_default ? defaultYesLabel : defaultNoLabel }}
            </span>
          </td>
          <td v-if="showActions">
            <button class="version-table-action" type="button" @click="$emit('view-files', item)">
              {{ resolvedActionLabel }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columnCount" class="empty-table-cell">{{ resolvedEmptyText }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script>
export default {
  name: 'AnnotationVersionTable',
  props: {
    rows: { type: Array, default: () => [] },
    showAssembly: { type: Boolean, default: true },
    showDefault: { type: Boolean, default: false },
    showActions: { type: Boolean, default: true },
    enableNavigation: { type: Boolean, default: false },
    actionLabel: { type: String, default: '' },
    emptyText: { type: String, default: '' },
    defaultColumnLabel: { type: String, default: '' },
    defaultYesLabel: { type: String, default: '' },
    defaultNoLabel: { type: String, default: '' }
  },
  emits: ['view-files', 'view-annotation'],
  computed: {
    columnCount() {
      return 3 + Number(this.showAssembly) + Number(this.showDefault) + Number(this.showActions);
    },
    resolvedActionLabel() {
      return this.actionLabel || this.$t('page.accessionDetail.viewFiles');
    },
    resolvedEmptyText() {
      return this.emptyText || this.$t('page.accessionDetail.empty.annotations');
    }
  }
};
</script>

<style scoped>
.version-table-shell { overflow-x:auto; border:1px solid #e2e9f4; border-radius:10px; }
.version-table { width:100%; min-width:680px; border-collapse:collapse; }
.version-table th,.version-table td { padding:12px; border-bottom:1px solid #e8edf5; text-align:left; font-size:12px; }
.version-table th { background:#f1f6fd; color:#4b607e; white-space:nowrap; }
.version-table td { color:#1c3359; }
.version-table tbody tr:last-child td { border-bottom:0; }
.annotation-version-link { padding:0; border:0; background:transparent; color:#1760e8; font:inherit; font-weight:700; text-align:left; cursor:pointer; }
.annotation-version-link:hover { text-decoration:underline; }
.annotation-version-link:focus-visible { outline:2px solid #409eff; outline-offset:3px; border-radius:2px; }
.version-table-action { height:34px; padding:0 12px; border:1px solid #c9dcfb; border-radius:8px; background:#fff; color:#1760e8; font-size:12px; font-weight:700; cursor:pointer; }
.default-badge { display:inline-block; min-width:24px; padding:3px 7px; border-radius:6px; background:#eef2f7; color:#718096; text-align:center; font-size:10px; font-weight:800; }
.default-badge.is-default { background:#dff6e5; color:#25813f; }
.empty-table-cell { text-align:center !important; color:#8795ab !important; }
</style>
