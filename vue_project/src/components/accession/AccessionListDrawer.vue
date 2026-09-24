<template>
  <el-drawer
    :model-value="modelValue"
    :size="drawerSize"
    :direction="drawerDirection"
    :modal="mode !== 'cluster'"
    :lock-scroll="mode !== 'cluster'"
    class="accession-list-drawer"
    :class="{ 'cluster-drawer': mode === 'cluster' }"
    destroy-on-close
    modal-class="accession-drawer-modal"
    @update:model-value="$emit('update:modelValue', $event)"
    @closed="$emit('closed')"
  >
    <template #header>
      <h2 class="drawer-title">{{ title }}</h2>
    </template>

    <div v-if="items.length && mode === 'cluster'" class="cluster-table-wrap">
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

    <div v-else-if="items.length" class="drawer-list">
      <div v-for="item in items" :key="item.accession" class="drawer-row">
        <button type="button" class="drawer-accession" @click="$emit('select', item.accession)">
          <strong>{{ item.accession }}</strong>
          <SpeciesName :scientific-name="item.scientific_name" empty-text="—" />
          <span>{{ item.sub_population || '—' }}</span>
          <time v-if="mode === 'recent'" :datetime="item.viewed_at || undefined">
            {{ formatRelativeTime(item.viewed_at) }}
          </time>
        </button>
        <button
          v-if="mode !== 'cluster'"
          type="button"
          class="drawer-remove"
          :aria-label="$t('page.accessionPortal.removeItem', { accession: item.accession })"
          @click="$emit('remove', item.accession)"
        >
          <el-icon aria-hidden="true"><Delete /></el-icon>
        </button>
      </div>
    </div>
    <p v-else class="drawer-empty">{{ emptyText }}</p>

    <button
      v-if="mode === 'recent' && items.length"
      type="button"
      class="clear-button"
      @click="$emit('clear')"
    >
      {{ $t('page.accessionPortal.clearAll') }}
    </button>
  </el-drawer>
</template>

<script>
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { Delete } from '@element-plus/icons-vue';
import SpeciesName from '@/components/common/SpeciesName.vue';

export default {
  name: 'AccessionListDrawer',
  components: { Delete, SpeciesName },
  props: {
    modelValue: { type: Boolean, default: false },
    mode: { type: String, default: 'recent' },
    items: { type: Array, default: () => [] }
  },
  emits: ['update:modelValue', 'closed', 'select', 'remove', 'clear'],
  setup(props) {
    const { locale, t } = useI18n();
    const title = computed(() => ({
      recent: t('page.accessionPortal.recent'),
      favorites: t('page.accessionPortal.favorites'),
      cluster: t('page.accessionPortal.clusterAccessions')
    }[props.mode] || t('page.accessionPortal.title')));
    const emptyText = computed(() => (
      props.mode === 'favorites'
        ? t('page.accessionPortal.noFavorites')
        : props.mode === 'cluster'
          ? t('page.accessionPortal.noClusterAccessions')
          : t('page.accessionPortal.noRecent')
    ));
    const drawerDirection = 'rtl';
    const drawerSize = computed(() => (
      props.mode === 'cluster' ? 'min(560px, 33.333vw)' : 'min(520px, 100%)'
    ));
    const displayValue = value => (
      value === null || value === undefined || String(value).trim() === '' ? '' : value
    );
    const formatCoordinate = (value) => {
      if (value === null || value === undefined || String(value).trim() === '') return '';
      const number = Number(value);
      return Number.isFinite(number) ? number.toFixed(4) : '';
    };
    const formatRelativeTime = (value) => {
      if (!value) return '—';
      const timestamp = new Date(value).getTime();
      if (!Number.isFinite(timestamp)) return '—';
      const deltaSeconds = Math.round((timestamp - Date.now()) / 1000);
      const absoluteSeconds = Math.abs(deltaSeconds);
      let unit = 'second';
      let divisor = 1;
      if (absoluteSeconds >= 86400) { unit = 'day'; divisor = 86400; }
      else if (absoluteSeconds >= 3600) { unit = 'hour'; divisor = 3600; }
      else if (absoluteSeconds >= 60) { unit = 'minute'; divisor = 60; }
      return new Intl.RelativeTimeFormat(locale.value === 'zh' ? 'zh-CN' : 'en-US', {
        numeric: 'auto'
      }).format(Math.round(deltaSeconds / divisor), unit);
    };
    return {
      displayValue,
      drawerDirection,
      drawerSize,
      emptyText,
      formatCoordinate,
      formatRelativeTime,
      title
    };
  }
};
</script>

<style scoped>
.drawer-title { margin:0; color:#1455c8; font-size:20px; }
.cluster-table-wrap { max-height:100%; overflow:auto; border:1px solid #dce7f3; border-radius:8px; }
.cluster-table { width:100%; min-width:620px; border-collapse:collapse; table-layout:fixed; }
.cluster-table th,.cluster-table td { padding:11px 12px; border-right:1px solid #e3ebf5; border-bottom:1px solid #e3ebf5; color:#526b91; text-align:left; font-size:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.cluster-table th { position:sticky; top:0; z-index:1; background:#edf5ff; color:#173d7c; font-weight:700; }
.cluster-table th:nth-child(1) { width:90px; }
.cluster-table th:nth-child(2) { width:140px; }
.cluster-table th:nth-child(3),.cluster-table th:nth-child(4) { width:90px; }
.cluster-table th:nth-child(5),.cluster-table th:nth-child(6) { width:105px; }
.cluster-table th:last-child,.cluster-table td:last-child { border-right:0; }
.cluster-table tbody tr:last-child td { border-bottom:0; }
.cluster-table tbody tr:hover { background:#f7fbff; }
.cluster-table em { color:#385c88; }
.cluster-accession { padding:0; border:0; background:transparent; color:#0071e8; font:inherit; font-weight:700; cursor:pointer; }
.cluster-accession:hover,.cluster-accession:focus-visible { text-decoration:underline; text-underline-offset:3px; outline:none; }
.drawer-list { border-top:1px solid #e3ebf5; }
.drawer-row { display:grid; grid-template-columns:minmax(0,1fr) 38px; align-items:center; border-bottom:1px solid #e3ebf5; }
.drawer-accession { display:grid; grid-template-columns:minmax(90px,.8fr) minmax(120px,1.25fr) minmax(70px,.7fr) minmax(80px,.8fr); gap:8px; align-items:center; min-height:48px; padding:0 8px; border:0; background:transparent; text-align:left; cursor:pointer; }
.drawer-accession:hover,.drawer-accession:focus-visible { background:#f3f8ff; outline:none; }
.drawer-accession strong,.drawer-accession span,.drawer-accession time { overflow:hidden; color:#5c7398; text-overflow:ellipsis; white-space:nowrap; font-size:12px; }
.drawer-accession strong { color:#0071e8; }
.drawer-remove { border:0; background:transparent; color:#d39a06; font-size:18px; cursor:pointer; }
.drawer-empty { padding:48px 0; color:#8291a8; text-align:center; }
.clear-button { display:block; margin:18px 0 0 auto; padding:8px 14px; border:1px solid #d7e2f1; border-radius:8px; background:#fff; color:#526b8f; cursor:pointer; }
:global(.cluster-drawer .el-drawer__header) { margin-bottom:10px; padding:16px 16px 8px; }
:global(.cluster-drawer .el-drawer__body) { min-height:0; padding:8px 16px 16px; overflow:hidden; }
@media (max-width:600px) {
  .drawer-accession { grid-template-columns:minmax(90px,.8fr) minmax(120px,1.2fr); }
  .drawer-accession span:last-of-type,.drawer-accession time { display:none; }
}
</style>
