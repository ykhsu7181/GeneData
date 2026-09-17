<template>
  <article class="shortcut-card" aria-labelledby="recent-title">
    <header class="card-heading">
      <h2 id="recent-title"><span aria-hidden="true">◷</span>{{ $t('page.accessionPortal.recent') }}</h2>
      <button v-if="items.length" type="button" @click="$emit('view-all', $event.currentTarget)">
        {{ $t('page.accessionPortal.viewAll') }} →
      </button>
    </header>

    <div v-if="items.length" class="recent-list">
      <button
        v-for="item in items.slice(0, 5)"
        :key="item.accession"
        type="button"
        class="recent-row"
        @click="$emit('select', item.accession)"
      >
        <strong :title="item.accession">{{ item.accession }}</strong>
        <span :title="item.scientific_name || ''">{{ item.scientific_name || '—' }}</span>
        <span :title="item.sub_population || ''">{{ item.sub_population || '—' }}</span>
        <time :datetime="item.viewed_at || undefined">{{ formatRelativeTime(item.viewed_at) }}</time>
      </button>
    </div>
    <p v-else class="empty-copy">{{ $t('page.accessionPortal.noRecent') }}</p>
  </article>
</template>

<script>
import { useI18n } from 'vue-i18n';

export default {
  name: 'RecentAccessions',
  props: {
    items: { type: Array, default: () => [] }
  },
  emits: ['select', 'view-all'],
  setup() {
    const { locale } = useI18n();
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
      const amount = Math.round(deltaSeconds / divisor);
      return new Intl.RelativeTimeFormat(locale.value === 'zh' ? 'zh-CN' : 'en-US', {
        numeric: 'auto'
      }).format(amount, unit);
    };
    return { formatRelativeTime };
  }
};
</script>

<style scoped>
.shortcut-card { min-height:238px; padding:15px 16px; border:1px solid rgba(202,220,240,.9); border-radius:12px; background:rgba(255,255,255,.97); box-shadow:0 10px 28px rgba(49,93,147,.06); }
.card-heading { display:flex; align-items:center; justify-content:space-between; gap:14px; margin-bottom:9px; }
.card-heading h2 { display:flex; align-items:center; gap:9px; margin:0; color:#086cde; font-size:18px; }
.card-heading h2 span { color:#153f79; font-size:25px; }
.card-heading button { padding:4px; border:0; background:transparent; color:#0874e9; font-size:12px; font-weight:700; cursor:pointer; }
.recent-list { border-top:1px solid #e3ebf5; }
.recent-row { display:grid; grid-template-columns:minmax(72px,.8fr) minmax(110px,1.25fr) minmax(55px,.65fr) minmax(78px,.8fr); align-items:center; width:100%; min-height:38px; padding:0 8px; border:0; border-bottom:1px solid #e3ebf5; background:transparent; text-align:left; cursor:pointer; }
.recent-row:hover,.recent-row:focus-visible { background:#f3f8ff; outline:none; }
.recent-row strong,.recent-row span,.recent-row time { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:12px; }
.recent-row strong { color:#0071e8; }
.recent-row span,.recent-row time { color:#5c7398; }
.recent-row time { text-align:right; }
.empty-copy { display:grid; min-height:165px; place-items:center; margin:0; color:#8291a8; font-size:13px; }
@media (max-width:600px) {
  .recent-row { grid-template-columns:minmax(80px,.8fr) minmax(120px,1.2fr); }
  .recent-row span:nth-of-type(2),.recent-row time { display:none; }
}
</style>
