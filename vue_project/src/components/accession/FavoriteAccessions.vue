<template>
  <article class="shortcut-card" aria-labelledby="favorites-title">
    <header class="card-heading">
      <h2 id="favorites-title"><el-icon aria-hidden="true"><StarFilled /></el-icon>{{ $t('page.accessionPortal.favorites') }}</h2>
      <button v-if="items.length" type="button" @click="$emit('view-all', $event.currentTarget)">
        {{ $t('page.accessionPortal.viewAll') }} →
      </button>
    </header>

    <div v-if="items.length" class="favorite-list">
      <div v-for="item in items" :key="item.accession" class="favorite-row">
        <button
          type="button"
          class="remove-favorite"
          :aria-label="$t('page.accessionPortal.removeFavorite', { accession: item.accession })"
          @click="$emit('remove', item.accession)"
        ><el-icon aria-hidden="true"><StarFilled /></el-icon></button>
        <button type="button" class="favorite-link" @click="$emit('select', item.accession)">
          <strong :title="item.accession">{{ item.accession }}</strong>
          <span :title="item.scientific_name || ''">{{ item.scientific_name || '—' }}</span>
          <span :title="item.sub_population || ''">{{ item.sub_population || '—' }}</span>
        </button>
      </div>
    </div>
    <p v-else class="empty-copy">{{ $t('page.accessionPortal.noFavorites') }}</p>
  </article>
</template>

<script>
import { StarFilled } from '@element-plus/icons-vue';

export default {
  name: 'FavoriteAccessions',
  components: { StarFilled },
  props: {
    items: { type: Array, default: () => [] }
  },
  emits: ['select', 'view-all', 'remove']
};
</script>

<style scoped>
.shortcut-card { min-height:218px; padding:14px 15px; border:1px solid rgba(202,220,240,.9); border-radius:12px; background:rgba(255,255,255,.97); box-shadow:0 10px 28px rgba(49,93,147,.06); }
.card-heading { display:flex; align-items:center; justify-content:space-between; gap:14px; margin-bottom:9px; }
.card-heading h2 { display:flex; align-items:center; gap:8px; margin:0; color:#086cde; font-size:17px; }
.card-heading h2 .el-icon { color:#153f79; font-size:20px; }
.card-heading > button { padding:4px; border:0; background:transparent; color:#0874e9; font-size:12px; font-weight:700; cursor:pointer; }
.favorite-list { max-height:190px; overflow-y:auto; border-top:1px solid #e3ebf5; scrollbar-width:thin; }
.favorite-row { display:grid; grid-template-columns:28px minmax(0,1fr); align-items:center; min-height:38px; border-bottom:1px solid #e3ebf5; }
.remove-favorite { display:inline-flex; align-items:center; justify-content:center; border:0; background:transparent; color:#f2b705; font-size:17px; cursor:pointer; }
.remove-favorite:hover,.remove-favorite:focus-visible { color:#c98700; outline:2px solid rgba(230,173,22,.25); outline-offset:1px; }
.favorite-link { display:grid; grid-template-columns:minmax(76px,.8fr) minmax(110px,1.3fr) minmax(58px,.7fr); align-items:center; min-width:0; min-height:37px; padding:0 8px; border:0; background:transparent; text-align:left; cursor:pointer; }
.favorite-link:hover,.favorite-link:focus-visible { background:#f3f8ff; outline:none; }
.favorite-link strong,.favorite-link span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:12px; }
.favorite-link strong { color:#0071e8; }
.favorite-link span { color:#5c7398; }
.empty-copy { display:grid; min-height:145px; place-items:center; margin:0; color:#8291a8; font-size:13px; }
@media (max-width:600px) {
  .favorite-link { grid-template-columns:minmax(85px,.8fr) minmax(120px,1.2fr); }
  .favorite-link span:last-child { display:none; }
}
</style>
