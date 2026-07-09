<template>
  <section class="resource-summary-card">
    <div class="resource-header">
      <div>
        <p class="resource-kicker">Data Resource Summary</p>
        <h3>数据资源统计</h3>
      </div>
      <button class="resource-view-all" @click="emit('navigate', '/data-overview')">
        查看全部数据资源
        <span>›</span>
      </button>
    </div>

    <div class="resource-grid">
      <button
        v-for="resource in normalizedItems"
        :key="resource.key"
        :class="['resource-card', { 'is-muted': resource.status === 'coming_soon' }]"
        @click="emit('navigate', buildTarget(resource))"
      >
        <span class="resource-icon">{{ iconFor(resource.icon || resource.key) }}</span>
        <span v-if="resource.status === 'coming_soon'" class="resource-status">建设中</span>
        <strong>{{ resource.title }}</strong>
        <b>{{ resource.count_display }}</b>
        <em>{{ resource.unit }}</em>
      </button>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  items: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['navigate'])

const fallbackItems = [
  { key: 'raw_data', title: '原始数据', count_display: '0', unit: '文件数', route: '/raw-data', icon: 'raw' },
  { key: 'genome', title: '基因组', count_display: '0', unit: '组装数', route: '/genome-card', icon: 'genome' },
  { key: 'annotation', title: '注释', count_display: '0', unit: '记录数', route: '/annotation', icon: 'annotation' },
  { key: 'transcriptome', title: '转录组', count_display: '0', unit: '数据集', route: '/transcriptome-overview', icon: 'transcriptome' },
  { key: 'population_genetics', title: '群体遗传', count_display: '0', unit: '数据集', route: '/data-overview', query: { dataset_type: 'population_genetics' }, icon: 'population', status: 'coming_soon' },
  { key: 'download', title: '下载', count_display: '-', unit: '可用数据量', route: '/data-overview', query: { download_mode: 'by_type' }, icon: 'download' }
]

const normalizedItems = computed(() => (props.items && props.items.length ? props.items : fallbackItems))

const iconFor = (key) => {
  const iconMap = {
    raw: '▣',
    raw_data: '▣',
    genome: '⌬',
    annotation: '▤',
    transcriptome: '⌁',
    population: '●',
    population_genetics: '●',
    download: '⇩'
  }
  return iconMap[key] || '▣'
}

const buildTarget = (resource) => ({
  path: resource.route || '/data-overview',
  query: resource.query || {}
})
</script>

<style scoped>
.resource-summary-card {
  min-height: 100%;
  padding: 24px;
  border-radius: 28px;
  background: linear-gradient(180deg, #ffffff, #f8fbff);
  border: 1px solid rgba(210, 221, 236, 0.9);
  box-shadow: 0 18px 40px rgba(14, 30, 66, 0.08);
}

.resource-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 20px;
}

.resource-kicker {
  margin: 0 0 5px;
  color: #1d4ed8;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.15em;
  text-transform: uppercase;
}

.resource-header h3 {
  margin: 0;
  color: #0f172a;
  font-size: 24px;
}

.resource-view-all {
  border: none;
  background: transparent;
  color: #2563eb;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
  white-space: nowrap;
}

.resource-view-all span {
  margin-left: 4px;
  font-size: 18px;
}

.resource-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.resource-card {
  position: relative;
  display: grid;
  justify-items: center;
  gap: 7px;
  min-height: 126px;
  padding: 18px 12px;
  border-radius: 20px;
  border: 1px solid rgba(216, 226, 238, 0.95);
  background: linear-gradient(180deg, #f9fcff, #f2f7ff);
  color: #12346d;
  cursor: pointer;
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.resource-card:hover {
  transform: translateY(-3px);
  border-color: rgba(37, 99, 235, 0.38);
  box-shadow: 0 16px 28px rgba(37, 99, 235, 0.1);
}

.resource-card.is-muted {
  background: linear-gradient(180deg, #f8fafc, #f1f5f9);
  color: #64748b;
}

.resource-icon {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 14px;
  background: #e8f0ff;
  color: #2563eb;
  font-size: 20px;
  font-weight: 900;
}

.resource-card:nth-child(2) .resource-icon {
  background: #e7f8ee;
  color: #059669;
}

.resource-card:nth-child(3) .resource-icon {
  background: #fff3df;
  color: #f97316;
}

.resource-card:nth-child(4) .resource-icon {
  background: #f0eaff;
  color: #7c3aed;
}

.resource-card:nth-child(5) .resource-icon {
  background: #e6fbff;
  color: #0891b2;
}

.resource-card:nth-child(6) .resource-icon {
  background: #eaf2ff;
  color: #2563eb;
}

.resource-status {
  position: absolute;
  top: 10px;
  right: 10px;
  padding: 3px 8px;
  border-radius: 999px;
  background: #e2e8f0;
  color: #64748b;
  font-size: 11px;
  font-weight: 800;
}

.resource-card strong {
  font-size: 14px;
  color: inherit;
}

.resource-card b {
  font-size: 24px;
  line-height: 1;
  color: #123a82;
}

.resource-card em {
  color: #64748b;
  font-size: 12px;
  font-style: normal;
  font-weight: 700;
}

@media (max-width: 1180px) {
  .resource-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
