<template>
  <div class="version-table-shell">
    <table class="version-table assembly-version-table">
      <thead>
        <tr>
          <th>{{ $t('page.accessionDetail.columns.assemblyVersion') }}</th>
          <th>{{ $t('page.accessionDetail.columns.assemblyCode') }}</th>
          <th>{{ $t('page.accessionDetail.columns.databaseAccession') }}</th>
          <th>BioProject</th>
          <th>Reference</th>
          <th v-if="showActions">{{ $t('common.actions') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in rows" :key="item.id">
          <td>
            <span v-if="mode === 'revision' && isCurrent(item)">{{ assemblyLabel(item) }}</span>
            <button v-else class="assembly-name-action" type="button" @click="selectAssembly(item)">
              {{ assemblyLabel(item) }}
            </button>
            <span v-if="isCurrent(item)" class="current-badge">{{ currentLabel }}</span>
          </td>
          <td>{{ item.assembly_code || '-' }}</td>
          <td>{{ item.assembly_accession || item.standard_id || '-' }}</td>
          <td>{{ item.bio_project || '-' }}</td>
          <td>{{ item.reference || '-' }}</td>
          <td v-if="showActions">
            <button
              v-if="mode !== 'revision' || !isCurrent(item)"
              class="version-table-action"
              type="button"
              @click="selectAssembly(item)"
            >
              {{ resolvedActionLabel }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="showActions ? 6 : 5" class="empty-table-cell">{{ resolvedEmptyText }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script>
export default {
  name: 'AssemblyVersionTable',
  props: {
    rows: { type: Array, default: () => [] },
    currentAssemblyId: { type: [Number, String], default: null },
    mode: {
      type: String,
      default: 'accession',
      validator: (value) => ['accession', 'revision'].includes(value)
    },
    showActions: { type: Boolean, default: true },
    actionLabel: { type: String, default: '' },
    currentLabel: { type: String, default: '' },
    emptyText: { type: String, default: '' }
  },
  emits: ['select'],
  computed: {
    resolvedActionLabel() {
      return this.actionLabel || this.$t('page.accessionDetail.viewFiles');
    },
    resolvedEmptyText() {
      return this.emptyText || this.$t('page.accessionDetail.empty.assemblies');
    }
  },
  methods: {
    assemblyLabel(item) {
      return item.display_name || item.assembly_name || item.name || '-';
    },
    isCurrent(item) {
      return this.currentAssemblyId !== null
        && String(item.id) === String(this.currentAssemblyId);
    },
    selectAssembly(item) {
      this.$emit('select', item);
    }
  }
};
</script>

<style scoped>
.version-table-shell { overflow-x:auto; border:1px solid #e2e9f4; border-radius:10px; }
.version-table { width:100%; min-width:720px; border-collapse:collapse; }
.version-table th,.version-table td { padding:12px; border-bottom:1px solid #e8edf5; text-align:left; font-size:12px; }
.version-table th { background:#f1f6fd; color:#4b607e; white-space:nowrap; }
.version-table td { color:#1c3359; }
.version-table tbody tr:last-child td { border-bottom:0; }
.version-table-action { height:34px; padding:0 12px; border:1px solid #c9dcfb; border-radius:8px; background:#fff; color:#1760e8; font-size:12px; font-weight:700; cursor:pointer; }
.assembly-name-action { padding:0; border:0; color:#1760e8; background:transparent; font:inherit; font-weight:700; cursor:pointer; text-align:left; }
.assembly-name-action:hover,.assembly-name-action:focus-visible { text-decoration:underline; }
.current-badge { display:inline-block; margin-left:8px; padding:3px 7px; border-radius:6px; background:#e7f1ff; color:#1760e8; font-size:10px; font-weight:800; }
.empty-table-cell { text-align:center !important; color:#8795ab !important; }
</style>
