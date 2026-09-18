<template>
  <el-drawer
    :model-value="modelValue"
    :size="drawerSize"
    destroy-on-close
    modal-class="accession-drawer-modal"
    @update:model-value="$emit('update:modelValue', $event)"
    @closed="$emit('closed')"
  >
    <template #header>
      <h2 class="drawer-title">{{ title }}</h2>
    </template>

    <div v-if="items.length" class="drawer-list">
      <div v-for="item in items" :key="item.accession" class="drawer-row">
        <button type="button" class="drawer-accession" @click="$emit('select', item.accession)">
          <strong>{{ item.accession }}</strong>
          <span>{{ item.scientific_name || '—' }}</span>
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

export default {
  name: 'AccessionListDrawer',
  components: { Delete },
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
    const drawerSize = 'min(520px, 100%)';
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
    return { drawerSize, emptyText, formatRelativeTime, title };
  }
};
</script>

<style scoped>
.drawer-title { margin:0; color:#1455c8; font-size:20px; }
.drawer-list { border-top:1px solid #e3ebf5; }
.drawer-row { display:grid; grid-template-columns:minmax(0,1fr) 38px; align-items:center; border-bottom:1px solid #e3ebf5; }
.drawer-accession { display:grid; grid-template-columns:minmax(90px,.8fr) minmax(120px,1.25fr) minmax(70px,.7fr) minmax(80px,.8fr); gap:8px; align-items:center; min-height:48px; padding:0 8px; border:0; background:transparent; text-align:left; cursor:pointer; }
.drawer-accession:hover,.drawer-accession:focus-visible { background:#f3f8ff; outline:none; }
.drawer-accession strong,.drawer-accession span,.drawer-accession time { overflow:hidden; color:#5c7398; text-overflow:ellipsis; white-space:nowrap; font-size:12px; }
.drawer-accession strong { color:#0071e8; }
.drawer-remove { border:0; background:transparent; color:#d39a06; font-size:18px; cursor:pointer; }
.drawer-empty { padding:48px 0; color:#8291a8; text-align:center; }
.clear-button { display:block; margin:18px 0 0 auto; padding:8px 14px; border:1px solid #d7e2f1; border-radius:8px; background:#fff; color:#526b8f; cursor:pointer; }
@media (max-width:600px) {
  .drawer-accession { grid-template-columns:minmax(90px,.8fr) minmax(120px,1.2fr); }
  .drawer-accession span:last-of-type,.drawer-accession time { display:none; }
}
</style>
