<template>
  <aside
    v-if="modelValue"
    class="cluster-panel"
    role="dialog"
    :aria-label="$t('page.accessionPortal.clusterAccessions')"
  >
    <header class="cluster-panel-header">
      <h2>{{ $t('page.accessionPortal.clusterAccessions') }}</h2>
      <button
        type="button"
        class="cluster-panel-close"
        :aria-label="$t('common.close')"
        @click="$emit('update:modelValue', false)"
      >
        <span aria-hidden="true">×</span>
      </button>
    </header>

    <div class="cluster-table-wrap" tabindex="0">
      <table class="cluster-table">
        <thead>
          <tr>
            <th scope="col">Accession</th>
            <th scope="col">{{ $t('page.accessionPortal.drawerColumns.species') }}</th>
            <th scope="col">{{ $t('page.accessionPortal.drawerColumns.longitude') }}</th>
            <th scope="col">{{ $t('page.accessionPortal.drawerColumns.latitude') }}</th>
            <th scope="col">{{ $t('page.accessionPortal.drawerColumns.country') }}</th>
            <th scope="col">{{ $t('page.accessionPortal.drawerColumns.region') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.accession">
            <td>
              <button type="button" class="cluster-accession" @click="$emit('select', item.accession)">
                {{ displayValue(item.accession) }}
              </button>
            </td>
            <td><em>{{ displayValue(item.scientific_name) }}</em></td>
            <td>{{ formatCoordinate(item.longitude) }}</td>
            <td>{{ formatCoordinate(item.latitude) }}</td>
            <td>{{ displayValue(item.country) }}</td>
            <td>{{ displayValue(item.region) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </aside>
</template>

<script>
export default {
  name: 'AccessionClusterPanel',
  props: {
    modelValue: { type: Boolean, default: false },
    items: { type: Array, default: () => [] }
  },
  emits: ['update:modelValue', 'select'],
  setup() {
    const displayValue = value => (
      value === null || value === undefined || String(value).trim() === '' ? '' : value
    );
    const formatCoordinate = (value) => {
      if (value === null || value === undefined || String(value).trim() === '') return '';
      const number = Number(value);
      return Number.isFinite(number) ? number.toFixed(4) : '';
    };
    return { displayValue, formatCoordinate };
  }
};
</script>

<style scoped>
.cluster-panel {
  position:absolute;
  top:12px;
  right:12px;
  z-index:5;
  display:flex;
  flex-direction:column;
  width:min(560px, 33.333%);
  max-height:calc(100% - 24px);
  overflow:hidden;
  border:1px solid #cddff2;
  border-radius:10px;
  background:rgba(255,255,255,.98);
  box-shadow:0 12px 32px rgba(24,62,108,.2);
}
.cluster-panel-header { display:flex; flex:0 0 auto; align-items:center; justify-content:space-between; gap:8px; padding:7px 9px; border-bottom:1px solid #dce7f3; }
.cluster-panel-header h2 { margin:0; color:#1455c8; font-size:14px; }
.cluster-panel-close { display:grid; width:26px; height:26px; padding:0; place-items:center; border:0; border-radius:6px; color:#34465e; background:transparent; font-size:20px; line-height:1; cursor:pointer; }
.cluster-panel-close:hover,.cluster-panel-close:focus-visible { color:#086cde; background:#eef5ff; outline:2px solid #75aef1; outline-offset:1px; }
.cluster-table-wrap { min-height:0; overflow:auto; overscroll-behavior:contain; }
.cluster-table { width:100%; min-width:500px; border-collapse:collapse; table-layout:fixed; }
.cluster-table th,.cluster-table td { padding:7px 6px; border-right:1px solid #e3ebf5; border-bottom:1px solid #e3ebf5; color:#526b91; text-align:left; font-size:11px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.cluster-table th { position:sticky; top:0; z-index:1; color:#173d7c; background:#edf5ff; font-weight:700; }
.cluster-table th:nth-child(1) { width:76px; }
.cluster-table th:nth-child(2) { width:108px; }
.cluster-table th:nth-child(3),.cluster-table th:nth-child(4) { width:70px; }
.cluster-table th:nth-child(5),.cluster-table th:nth-child(6) { width:82px; }
.cluster-table th:last-child,.cluster-table td:last-child { border-right:0; }
.cluster-table tbody tr:last-child td { border-bottom:0; }
.cluster-table tbody tr:hover { background:#f7fbff; }
.cluster-table em { color:#385c88; }
.cluster-accession { padding:0; border:0; color:#0071e8; background:transparent; font:inherit; font-weight:700; cursor:pointer; }
.cluster-accession:hover,.cluster-accession:focus-visible { text-decoration:underline; text-underline-offset:3px; outline:none; }
@media (max-width:700px) {
  .cluster-panel { top:8px; right:8px; width:33.333%; max-height:calc(100% - 16px); }
  .cluster-panel-header { padding:6px; }
  .cluster-panel-header h2 { font-size:12px; }
}
</style>
