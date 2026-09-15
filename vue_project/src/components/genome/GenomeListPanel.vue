<template>
  <div class="genome-list-panel">
    <div class="genome-list-filters">
      <div class="filter-item">
        <span class="filter-label">{{ $t('page.genomeCard.species') }}</span>
        <el-select
          :model-value="filters.species_id"
          :placeholder="$t('page.genomeCard.selectSpecies')"
          clearable
          filterable
          class="filter-select"
          @update:model-value="updateFilter('species_id', $event)"
          @change="$emit('refresh')"
        >
          <el-option
            v-for="item in filterOptions.species"
            :key="item.id"
            :label="`${item.label}${item.latin_name && item.latin_name !== '-' ? ' / ' + item.latin_name : ''}`"
            :value="item.id"
          />
        </el-select>
      </div>

      <div class="filter-item">
        <span class="filter-label">{{ $t('page.genomeCard.accession') }}</span>
        <el-select
          :model-value="filters.accession_id"
          :placeholder="$t('page.genomeCard.selectAccession')"
          clearable
          filterable
          class="filter-select"
          @update:model-value="updateFilter('accession_id', $event)"
          @change="$emit('refresh')"
        >
          <el-option
            v-for="item in filteredAccessions"
            :key="item.id"
            :label="item.label"
            :value="item.id"
          />
        </el-select>
      </div>

      <div class="filter-item">
        <span class="filter-label">{{ $t('page.genomeCard.assemblyLevel') }}</span>
        <el-select
          :model-value="filters.assembly_level"
          :placeholder="$t('page.genomeCard.selectAssemblyLevel')"
          clearable
          class="filter-select"
          @update:model-value="updateFilter('assembly_level', $event)"
          @change="$emit('refresh')"
        >
          <el-option
            v-for="item in filterOptions.assembly_levels"
            :key="item"
            :label="item"
            :value="item"
          />
        </el-select>
      </div>

      <el-button class="list-refresh" @click="$emit('refresh')">
        <el-icon><Refresh /></el-icon>
        {{ $t('common.refresh') }}
      </el-button>
    </div>

    <div class="genome-table-card">
      <el-table
        v-loading="loading"
        :data="rows"
        class="genome-table"
        row-key="assembly_id"
        :empty-text="$t('page.genomeCard.emptyGenome')"
      >
        <el-table-column :label="$t('page.genomeCard.species')" min-width="260">
          <template #default="{ row }">
            <div class="species-cell">
              <span class="species-icon">⌘</span>
              <div>
                <div class="species-main">{{ row.species_name || '-' }} {{ row.accession || '' }}</div>
                <div class="species-latin">{{ row.latin_name || '-' }}</div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="$t('page.genomeCard.accession')" min-width="170">
          <template #default="{ row }">
            <button type="button" class="accession-link" @click="$emit('go-accession', row)">
              {{ row.accession || '-' }}
            </button>
          </template>
        </el-table-column>
        <el-table-column :label="$t('page.genomeCard.assemblyLevel')" min-width="160">
          <template #default="{ row }">
            <span v-if="row.assembly_level && row.assembly_level !== '-'" class="assembly-level-badge">
              {{ row.assembly_level }}
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="chromosome_count" :label="$t('page.genomeCard.chromosomeCount')" min-width="130" />
        <el-table-column prop="genome_size_display" :label="$t('page.genomeCard.genomeSize')" min-width="160" />
        <el-table-column :label="$t('common.actions')" width="210" fixed="right">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button size="small" @click="$emit('open-files', row)">{{ $t('page.genomeCard.viewFiles') }}</el-button>
              <el-button size="small" type="primary" plain @click="$emit('download-row', row)">
                <el-icon><Download /></el-icon>
                {{ $t('common.download') }}
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="genome-pagination">
        <span>{{ $t('common.totalCount', { count: pagination.total }) }}</span>
        <el-pagination
          background
          layout="sizes, prev, pager, next, jumper"
          :total="pagination.total"
          :current-page="pagination.page"
          :page-size="pagination.page_size"
          :page-sizes="[20, 50, 100]"
          @current-change="$emit('page-change', $event)"
          @size-change="$emit('page-size-change', $event)"
        />
      </div>
    </div>
  </div>
</template>

<script>
import { Download, Refresh } from '@element-plus/icons-vue';

export default {
  name: 'GenomeListPanel',
  components: { Download, Refresh },
  props: {
    loading: { type: Boolean, default: false },
    rows: { type: Array, default: () => [] },
    filters: { type: Object, required: true },
    filterOptions: {
      type: Object,
      default: () => ({ species: [], accessions: [], assembly_levels: [] })
    },
    filteredAccessions: { type: Array, default: () => [] },
    pagination: {
      type: Object,
      default: () => ({ page: 1, page_size: 20, total: 0 })
    }
  },
  emits: [
    'update-filter',
    'refresh',
    'open-files',
    'download-row',
    'go-accession',
    'page-change',
    'page-size-change'
  ],
  methods: {
    updateFilter(key, value) {
      this.$emit('update-filter', { key, value });
    }
  }
};
</script>

<style scoped>
.genome-list-panel { display: flex; flex-direction: column; gap: 20px; }
.genome-list-filters { display: grid; grid-template-columns: auto minmax(190px, 260px) auto minmax(190px, 260px) auto minmax(190px, 260px) 1fr auto; align-items: center; gap: 14px 18px; padding: 22px 24px; border: 1px solid #dbe7f6; border-radius: 10px; background: #fff; box-shadow: 0 14px 32px rgba(34, 71, 120, 0.07); }
.filter-item { display: contents; }
.filter-label { color: #1a2f4d; font-size: 15px; font-weight: 900; white-space: nowrap; }
.filter-select { width: 100%; }
.list-refresh { min-width: 96px; height: 40px; font-weight: 900; }
.genome-table-card { overflow: hidden; border: 1px solid #dbe7f6; border-radius: 10px; background: #fff; box-shadow: 0 14px 32px rgba(34, 71, 120, 0.07); }
.genome-table { width: 100%; }
.genome-table :deep(th.el-table__cell) { background: #f0f6fd; color: #294561; font-size: 15px; font-weight: 900; }
.genome-table :deep(td.el-table__cell) { height: 88px; color: #173052; font-weight: 700; }
.species-cell { display: flex; align-items: center; gap: 16px; }
.species-icon { flex: 0 0 auto; width: 46px; height: 46px; display: grid; place-items: center; border-radius: 50%; background: #e8f9ef; color: #08a86f; font-size: 25px; font-weight: 900; }
.species-main { color: #08264b; font-size: 19px; line-height: 1.2; font-weight: 900; letter-spacing: -0.02em; }
.species-latin { display: block; margin-top: 5px; color: #53647b; font-size: 15px; line-height: 1.15; font-style: italic; font-weight: 800; }
.accession-link { border: 0; background: transparent; color: #1768f2; font-size: 15px; font-weight: 900; cursor: pointer; }
.assembly-level-badge { display: inline-flex; align-items: center; min-height: 28px; padding: 0 12px; border-radius: 999px; background: #eaf6ff; color: #0e5ad7; font-weight: 900; }
.table-actions { display: flex; align-items: center; gap: 8px; }
.genome-pagination { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border-top: 1px solid #dbe7f6; color: #5d6f89; font-weight: 800; }
@media (max-width: 768px) {
  .genome-list-filters { grid-template-columns: 1fr; }
  .filter-item { display: flex; flex-direction: column; gap: 6px; }
}
</style>
