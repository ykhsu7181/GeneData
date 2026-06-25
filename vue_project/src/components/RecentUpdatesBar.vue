<template>
  <section class="recent-updates-card">
    <div class="recent-title">
      <strong>最近更新</strong>
      <span>Latest Updates</span>
    </div>

    <div v-if="items.length" class="recent-chip-list">
      <button
        v-for="item in items"
        :key="`${item.title}-${item.date}`"
        class="update-chip"
        @click="emit('navigate', buildTarget(item))"
      >
        <span class="update-type-dot"></span>
        <strong>{{ item.title }}</strong>
        <em>{{ item.date }}</em>
      </button>
    </div>

    <div v-else class="recent-empty">暂无最近更新</div>

    <button class="recent-more" @click="emit('navigate', '/data-overview')">
      查看全部更新
      <span>›</span>
    </button>
  </section>
</template>

<script setup>
defineProps({
  items: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['navigate'])

const buildTarget = (item) => ({
  path: item.route || '/data-overview',
  query: item.query || {}
})
</script>

<style scoped>
.recent-updates-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 18px;
  padding: 16px 22px;
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff, #f8fbff);
  border: 1px solid rgba(210, 221, 236, 0.9);
  box-shadow: 0 14px 30px rgba(14, 30, 66, 0.07);
}

.recent-title {
  display: grid;
  gap: 2px;
  color: #0f172a;
}

.recent-title strong {
  font-size: 17px;
}

.recent-title span {
  color: #64748b;
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.recent-chip-list {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  overflow: hidden;
}

.update-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  max-width: 280px;
  padding: 8px 12px;
  border: none;
  border-radius: 999px;
  background: #eef6ff;
  color: #1e3a8a;
  cursor: pointer;
}

.update-chip strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.update-chip em {
  color: #64748b;
  font-size: 12px;
  font-style: normal;
  white-space: nowrap;
}

.update-type-dot {
  flex: 0 0 auto;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #38bdf8;
  box-shadow: 0 0 0 4px rgba(56, 189, 248, 0.16);
}

.recent-empty {
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
}

.recent-more {
  border: none;
  background: transparent;
  color: #2563eb;
  font-size: 13px;
  font-weight: 900;
  cursor: pointer;
  white-space: nowrap;
}

.recent-more span {
  margin-left: 4px;
  font-size: 18px;
}
</style>
