<template>
  <section class="annotation-search-panel" role="search" :aria-label="$t('page.annotation.searchPanelLabel')">
    <div
      class="search-scroll"
      tabindex="0"
      :aria-label="$t('page.annotation.searchControlsLabel')"
      :aria-describedby="'annotation-scroll-hint'"
    >
      <span id="annotation-scroll-hint" class="sr-only">
        {{ $t('page.annotation.horizontalScrollHint') }}
      </span>
      <div class="search-grid">
        <div class="field field-accession">
          <span class="field-label">Accession</span>
          <el-autocomplete
            :model-value="accession"
            :aria-label="$t('page.annotation.accessionFieldLabel')"
            :placeholder="$t('page.annotation.searchPlaceholder')"
            :fetch-suggestions="fetchSuggestions"
            :trigger-on-focus="false"
            clearable
            @update:model-value="$emit('update:accession', $event)"
            @input="$emit('accession-input', $event)"
            @select="$emit('accession-select', $event)"
            @clear="$emit('clear-accession')"
            @keyup.enter="$emit('search')"
          />
        </div>

        <div class="field field-assembly">
          <span class="field-label">{{ $t('page.annotation.assembly') }}</span>
          <el-select
            :model-value="assemblyId"
            :aria-label="$t('page.annotation.assemblyFieldLabel')"
            :placeholder="$t('page.annotation.selectAssembly')"
            :loading="loadingHierarchy"
            :disabled="!accession || !assemblyOptions.length"
            filterable
            @change="$emit('assembly-change', $event)"
          >
            <el-option
              v-for="item in assemblyOptions"
              :key="item.id"
              :label="assemblyLabel(item)"
              :value="String(item.id)"
            />
          </el-select>
        </div>

        <div class="field field-annotation">
          <span class="field-label">{{ $t('page.annotation.annotation') }}</span>
          <el-select
            :model-value="annotationId"
            :aria-label="$t('page.annotation.annotationFieldLabel')"
            :placeholder="$t('page.annotation.selectAnnotation')"
            :disabled="!assemblyId || !annotationOptions.length"
            filterable
            @change="$emit('annotation-change', $event)"
          >
            <el-option
              v-for="item in annotationOptions"
              :key="item.id"
              :label="annotationLabel(item)"
              :value="String(item.id)"
            />
          </el-select>
        </div>

        <div class="field field-chromosome">
          <span class="field-label">{{ $t('page.annotation.chromosome') }}</span>
          <el-select
            :model-value="chromosome"
            :aria-label="$t('page.annotation.chromosomeFieldLabel')"
            :placeholder="$t('page.annotation.allChromosomes')"
            :loading="loadingOptions"
            :disabled="!annotationId"
            clearable
            @change="$emit('chromosome-change', $event)"
          >
            <el-option
              v-for="item in chromosomeOptions"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
        </div>

        <div class="field field-feature">
          <span class="field-label">{{ $t('page.annotation.featureType') }}</span>
          <el-select
            :model-value="featureType"
            :aria-label="$t('page.annotation.featureFieldLabel')"
            :placeholder="$t('page.annotation.allFeatures')"
            :loading="loadingOptions"
            :disabled="viewMode === 'chart' || !annotationId"
            clearable
            @change="$emit('feature-change', $event)"
          >
            <el-option :label="$t('page.annotation.allFeatures')" value="all" />
            <el-option
              v-for="item in selectableFeatureTypes"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
        </div>

        <el-button
          class="submit-button"
          type="primary"
          :loading="loading || loadingOrganisms"
          :disabled="!accession"
          @click="$emit('search')"
        >
          {{ $t('common.search') }}
        </el-button>
      </div>
    </div>

    <div class="search-footer">
      <div class="current-context" :aria-label="$t('page.annotation.currentData')" aria-live="polite">
        <span class="context-label">{{ $t('page.annotation.currentData') }}:</span>
        <el-tag v-if="accession" round>{{ accession }}</el-tag>
        <el-tag v-if="assemblyName" round type="info">{{ assemblyName }}</el-tag>
        <el-tag v-if="annotationName" round type="success">{{ annotationName }}</el-tag>
        <span v-if="!accession" class="context-empty">{{ $t('page.annotation.noContextSelected') }}</span>
      </div>

      <div class="footer-actions">
        <el-button :icon="RefreshLeft" @click="$emit('reset')">
          {{ $t('page.annotation.resetFilters') }}
        </el-button>
        <el-button-group class="view-toggle" :aria-label="$t('page.annotation.viewMode')">
          <el-button
            :type="viewMode === 'table' ? 'primary' : 'default'"
            :icon="Grid"
            :aria-pressed="viewMode === 'table'"
            @click="$emit('view-change', 'table')"
          >
            {{ $t('page.annotation.tableView') }}
          </el-button>
          <el-button
            :type="viewMode === 'chart' ? 'primary' : 'default'"
            :icon="TrendCharts"
            :aria-pressed="viewMode === 'chart'"
            @click="$emit('view-change', 'chart')"
          >
            {{ $t('page.annotation.chartView') }}
          </el-button>
        </el-button-group>
      </div>
    </div>
  </section>
</template>

<script>
import { computed } from 'vue';
import { Grid, RefreshLeft, TrendCharts } from '@element-plus/icons-vue';

export default {
  name: 'AnnotationSearchPanel',
  props: {
    accession: { type: String, default: '' },
    assemblyId: { type: String, default: '' },
    annotationId: { type: String, default: '' },
    chromosome: { type: String, default: '' },
    featureType: { type: String, default: 'all' },
    viewMode: { type: String, default: 'table' },
    assemblyOptions: { type: Array, default: () => [] },
    annotationOptions: { type: Array, default: () => [] },
    chromosomeOptions: { type: Array, default: () => [] },
    featureTypeOptions: { type: Array, default: () => [] },
    loading: Boolean,
    loadingOrganisms: Boolean,
    loadingHierarchy: Boolean,
    loadingOptions: Boolean,
    fetchSuggestions: { type: Function, required: true },
    assemblyLabel: { type: Function, required: true },
    annotationLabel: { type: Function, required: true }
  },
  emits: [
    'update:accession',
    'accession-input',
    'accession-select',
    'clear-accession',
    'assembly-change',
    'annotation-change',
    'chromosome-change',
    'feature-change',
    'search',
    'reset',
    'view-change'
  ],
  setup(props) {
    const selectableFeatureTypes = computed(() => (
      props.featureTypeOptions.filter(item => item && item !== 'all')
    ));
    const assemblyName = computed(() => {
      const item = props.assemblyOptions.find(option => String(option.id) === String(props.assemblyId));
      return item ? props.assemblyLabel(item) : '';
    });
    const annotationName = computed(() => {
      const item = props.annotationOptions.find(option => String(option.id) === String(props.annotationId));
      return item ? props.annotationLabel(item) : '';
    });

    return {
      Grid,
      RefreshLeft,
      TrendCharts,
      selectableFeatureTypes,
      assemblyName,
      annotationName
    };
  }
};
</script>

<style scoped>
.annotation-search-panel {
  margin-bottom: 14px;
  padding: 16px 20px 14px;
  border: 1px solid #d9e7f7;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 14px 36px rgba(36, 103, 178, 0.08);
}

.search-scroll { overflow-x: auto; padding-bottom: 2px; }
.search-scroll:focus-visible { outline: 2px solid #409eff; outline-offset: 3px; border-radius: 6px; }
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.search-grid {
  display: grid;
  grid-template-columns: minmax(160px, .82fr) minmax(220px, 1.12fr) minmax(235px, 1.22fr) minmax(150px, .76fr) minmax(165px, .82fr) 110px;
  gap: 12px;
  align-items: end;
  min-width: 1100px;
}

.field { display: grid; gap: 7px; min-width: 0; }
.field-label { color: #153d74; font-size: 13px; font-weight: 700; }
.field :deep(.el-input__wrapper),
.field :deep(.el-select__wrapper) {
  min-height: 46px;
  border: 1px solid #cbdcf1;
  border-radius: 8px;
  box-shadow: none;
}
.field :deep(.el-input__wrapper.is-focus),
.field :deep(.el-select__wrapper.is-focused) {
  border-color: #4c9df3;
  box-shadow: 0 0 0 2px rgba(47, 136, 255, .12);
}
.field :deep(.el-autocomplete), .field :deep(.el-select) { width: 100%; }

.submit-button {
  min-height: 46px;
  border: 0;
  border-radius: 8px;
  background: linear-gradient(180deg, #2e91f5, #0b71df);
  font-weight: 700;
}

.search-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid #e2ebf6;
}
.current-context, .footer-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.context-label, .context-empty { color: #60799e; font-size: 13px; }
.current-context :deep(.el-tag) { border: 0; font-weight: 700; }
.view-toggle :deep(.el-button) { min-width: 82px; }

@media (max-width: 760px) {
  .annotation-search-panel { padding: 14px; }
  .search-footer { align-items: flex-start; flex-direction: column; }
  .footer-actions { width: 100%; justify-content: space-between; }
}
</style>
