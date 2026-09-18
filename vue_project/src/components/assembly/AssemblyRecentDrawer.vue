<template>
  <el-drawer
    :model-value="modelValue"
    :size="drawerSize"
    :aria-label="$t('page.assembly.viewAllRecent')"
    destroy-on-close
    modal-class="assembly-recent-drawer-modal"
    @update:model-value="$emit('update:modelValue', $event)"
    @closed="$emit('closed')"
  >
    <template #header>
      <h2 class="drawer-title">{{ $t('page.assembly.recent') }}</h2>
    </template>

    <div v-if="items.length" class="drawer-list" role="list">
      <div v-for="item in items" :key="item.id" class="drawer-row" role="listitem">
        <button
          type="button"
          class="drawer-assembly"
          :aria-label="$t('page.assembly.openAssembly', { assembly: displayValue(item.assembly) })"
          @click="$emit('select', item)"
        >
          <strong>{{ displayValue(item.accession) }}</strong>
          <span>{{ displayValue(item.assembly) }}</span>
          <span>{{ displayValue(item.assembly_accession) }}</span>
          <span><em>{{ displayValue(item.species) }}</em></span>
          <time :datetime="item.viewed_at || undefined">{{ formatRelativeTime(item.viewed_at) }}</time>
        </button>
        <button
          type="button"
          class="drawer-remove"
          :aria-label="$t('page.assembly.removeRecent', { assembly: item.assembly || item.id })"
          @click="$emit('remove', item.id)"
        >
          ×
        </button>
      </div>
    </div>
    <p v-else class="drawer-empty">{{ $t('page.assembly.noRecent') }}</p>

    <button
      v-if="items.length"
      type="button"
      class="clear-button"
      :aria-label="$t('page.assembly.clearAll')"
      @click="$emit('clear')"
    >
      {{ $t('page.assembly.clearAll') }}
    </button>
  </el-drawer>
</template>

<script>
import { useI18n } from 'vue-i18n';

const emptyMark = '—';

export default {
  name: 'AssemblyRecentDrawer',
  props: {
    modelValue: { type: Boolean, default: false },
    items: { type: Array, default: () => [] }
  },
  emits: ['update:modelValue', 'closed', 'select', 'remove', 'clear'],
  setup() {
    const { locale } = useI18n();
    const drawerSize = 'min(640px, 100%)';
    const displayValue = (value) => {
      const normalized = value === null || value === undefined ? '' : String(value).trim();
      return normalized || emptyMark;
    };
    const formatRelativeTime = (value) => {
      if (!value) return emptyMark;
      const timestamp = new Date(value).getTime();
      if (!Number.isFinite(timestamp)) return emptyMark;
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
    return { displayValue, drawerSize, formatRelativeTime };
  }
};
</script>

<style scoped>
.drawer-title { margin:0; color:#1455c8; font-size:20px; }
.drawer-list { border-top:1px solid #e3ebf5; }
.drawer-row { display:grid; grid-template-columns:minmax(0,1fr) 40px; align-items:center; border-bottom:1px solid #e3ebf5; }
.drawer-assembly { display:grid; grid-template-columns:minmax(82px,.75fr) minmax(110px,1fr) minmax(130px,1.2fr) minmax(110px,1fr) minmax(86px,.8fr); gap:8px; align-items:center; min-height:50px; padding:0 8px; border:0; background:transparent; text-align:left; cursor:pointer; }
.drawer-assembly:hover,.drawer-assembly:focus-visible { background:#f3f8ff; outline:none; }
.drawer-assembly strong,.drawer-assembly span,.drawer-assembly time { overflow:hidden; color:#5c7398; text-overflow:ellipsis; white-space:nowrap; font-size:12px; }
.drawer-assembly strong { color:#0071e8; }
.drawer-remove { border:0; background:transparent; color:#c65555; font-size:20px; cursor:pointer; }
.drawer-remove:hover,.drawer-remove:focus-visible { color:#9f2f2f; outline:none; }
.drawer-empty { padding:48px 0; color:#8291a8; text-align:center; }
.clear-button { display:block; margin:18px 0 0 auto; padding:8px 14px; border:1px solid #d7e2f1; border-radius:8px; background:#fff; color:#526b8f; cursor:pointer; }
.clear-button:hover,.clear-button:focus-visible { border-color:#9fbbe5; color:#1455c8; outline:none; }
@media (max-width:700px) {
  .drawer-assembly { grid-template-columns:minmax(88px,.8fr) minmax(110px,1fr); }
  .drawer-assembly span:nth-of-type(2),.drawer-assembly span:nth-of-type(3),.drawer-assembly time { display:none; }
}
</style>
