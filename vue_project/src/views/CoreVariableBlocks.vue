<template>
  <div class="core-variable-blocks-view">
    <div class="page-header">
      <h2 class="title">Core&Variable Blocks</h2>
      <div class="header-actions">
        <el-tooltip content="Refresh data" placement="top">
          <el-button circle size="small" @click="refreshPage" :loading="loadingPage">
            <el-icon><Refresh /></el-icon>
          </el-button>
        </el-tooltip>
      </div>
    </div>

    <div class="toolbar">
      <div class="toolbar-main">
        <div class="search-wrapper">
          <el-icon class="search-icon"><Search /></el-icon>
          <el-select
            v-model="selectedOrganism"
            filterable
            remote
            clearable
            class="search-select"
            placeholder="Search accession"
            :remote-method="searchOrganisms"
            :loading="loadingOrganisms"
            @change="handleOrganismChange"
          >
            <el-option v-for="item in organismOptions" :key="item" :label="item" :value="item" />
          </el-select>
        </div>

        <div class="chromosome-wrapper">
          <span class="field-label">Chromosome</span>
          <el-select
            v-model="selectedChromosome"
            clearable
            filterable
            class="chromosome-select"
            placeholder="Select chromosome"
            :loading="loadingChromosomes"
            @change="handleChromosomeChange"
          >
            <el-option v-for="item in chromosomeOptions" :key="item" :label="item" :value="item" />
          </el-select>
        </div>
      </div>
    </div>

    <div class="data-card">
      <div v-if="loadingPage" class="loading">
        <el-skeleton :rows="10" animated />
      </div>

      <div v-else-if="!selectedOrganism" class="empty-state">
        <el-empty description="Select an accession to explore core and variable block summaries" />
      </div>

      <div v-else-if="errorMessage" class="empty-state">
        <el-empty :description="errorMessage" />
      </div>

      <div v-else class="content-container">
        <div class="summary-panel">
          <div class="panel-header summary-header">
            <div>
              <h3 class="panel-title">{{ accessionDetail?.accession || selectedOrganism }}</h3>
            </div>
            <span class="panel-badge">{{ coreBlocksFile ? 'Core Ready' : 'Core Missing' }}</span>
          </div>

          <div class="summary-grid">
            <div class="summary-item">
              <div class="info-label">Accession</div>
              <div class="summary-value">{{ accessionDetail?.accession || selectedOrganism }}</div>
            </div>
            <div class="summary-item">
              <div class="info-label">Assembly</div>
              <div class="summary-value">{{ currentAssembly?.name || '-' }}</div>
            </div>
            <div class="summary-item">
              <div class="info-label">Chromosome</div>
              <div class="summary-value">{{ selectedChromosome || '-' }}</div>
            </div>
            <div class="summary-item">
              <div class="info-label">SubPopulation</div>
              <div class="summary-value">{{ accessionDetail?.sub_population || '-' }}</div>
            </div>
            <div class="summary-item">
              <div class="info-label">Status</div>
              <div class="summary-value">{{ coreBlocksFile ? 'Ready' : 'Missing' }}</div>
            </div>
            <div class="summary-item summary-item-wide">
              <div class="info-label">Source</div>
              <div class="summary-value summary-value-ellipsis" :title="coreBlocksFile?.name || 'No related file'">
                {{ coreBlocksFile?.name || 'No related file' }}
              </div>
            </div>
          </div>
        </div>

        <div class="overview-grid">
          <div class="overview-panel">
            <div class="panel-header">
              <h3 class="panel-title">Core Blocks Overview</h3>
              <span class="panel-tip">{{ selectedChromosome || 'Select a chromosome to inspect core blocks' }}</span>
            </div>

            <div class="stats-list">
              <div class="stat-card">
                <div class="stat-label">Block Count</div>
                <div class="stat-value">{{ stats.blockCount }}</div>
              </div>
              <div class="stat-card">
                <div class="stat-label">Total Length</div>
                <div class="stat-value">{{ formatNumber(stats.totalLength) }}</div>
                <div class="stat-subvalue">{{ totalLengthCoverageText }}</div>
              </div>
              <div class="stat-card">
                <div class="stat-label">Coverage %</div>
                <div class="stat-value">{{ totalLengthCoverageValue }}</div>
              </div>
              <div class="stat-card">
                <div class="stat-label">Longest Block</div>
                <div class="stat-value">{{ formatNumber(stats.maxLength) }}</div>
              </div>
            </div>

            <div v-if="!coreBlocksFile" class="warning-panel overview-warning">
              <div class="warning-title">Core blocks unavailable</div>
              <div class="warning-text">No core block source file is available for the current assembly.</div>
            </div>
            <div v-else-if="!selectedChromosome" class="inline-empty">Select a chromosome to view the core blocks overview.</div>
            <div v-else-if="loadingBlocks" class="loading-inline"><el-skeleton :rows="5" animated /></div>
            <div v-else-if="!coreBlocksData.length" class="inline-empty">No core block data is available for the current chromosome.</div>
            <div v-else class="visual-content">
              <div class="chromosome-scale">
                <div
                  v-for="block in scaledBlocks"
                  :key="block.id"
                  :class="['block-segment', block.blockKey === activeBlockKey ? 'block-segment-active' : '']"
                  :style="{ left: block.left, width: block.width }"
                  :title="`${block.seqid}: ${block.start}-${block.end} (${block.length})`"
                ></div>
              </div>
              <div class="range-hints"><span>0</span><span>{{ formatNumber(scaleMax) }}</span></div>
              <div class="top-blocks">
                <div class="subsection-title">Top Core Blocks</div>
                <div
                  v-for="item in longestBlocks"
                  :key="`${item.seqid}-${item.start}-${item.end}`"
                  :class="['top-block-item', item.blockKey === activeBlockKey ? 'top-block-item-active' : '']"
                  role="button"
                  tabindex="0"
                  @click="toggleActiveBlock(item)"
                  @keydown.enter.prevent="toggleActiveBlock(item)"
                  @keydown.space.prevent="toggleActiveBlock(item)"
                >
                  <span class="top-block-range">{{ item.seqid }}: {{ formatNumber(item.start) }} - {{ formatNumber(item.end) }}</span>
                  <span class="top-block-length">{{ formatNumber(item.length) }}</span>
                </div>
              </div>
            </div>
          </div>

          <div class="overview-panel overview-panel-variable">
            <div class="panel-header">
              <h3 class="panel-title">Variable Blocks Overview</h3>
              <span class="panel-badge panel-badge-muted">
                {{ variableBlocksFile ? 'Variable Ready' : 'Variable Missing' }}
              </span>
            </div>

            <div class="stats-list variable-stats-list">
              <div class="stat-card">
                <div class="stat-label">Block Count</div>
                <div class="stat-value">{{ variableStats.blockCount }}</div>
              </div>
              <div class="stat-card">
                <div class="stat-label">Total Length</div>
                <div class="stat-value">{{ formatNumber(variableStats.totalLength) }}</div>
                <div class="stat-subvalue">{{ variableTotalLengthCoverageText }}</div>
              </div>
              <div class="stat-card">
                <div class="stat-label">Coverage %</div>
                <div class="stat-value">{{ variableTotalLengthCoverageValue }}</div>
              </div>
              <div class="stat-card">
                <div class="stat-label">Longest Block</div>
                <div class="stat-value">{{ formatNumber(variableStats.maxLength) }}</div>
              </div>
            </div>

            <div v-if="!variableBlocksFile" class="warning-panel overview-warning variable-warning">
              <div class="warning-title">Variable blocks unavailable</div>
              <div class="warning-text">No variable block source file is available for the current assembly.</div>
            </div>
            <div v-else-if="!selectedChromosome" class="inline-empty variable-inline-empty">
              Select a chromosome to view the variable blocks overview.
            </div>
            <div v-else-if="loadingVariableBlocks" class="loading-inline">
              <el-skeleton :rows="5" animated />
            </div>
            <div v-else-if="!variableBlocksData.length" class="inline-empty variable-inline-empty">
              No variable block data is available for the current chromosome.
            </div>
            <div v-else class="visual-content">
              <div class="chromosome-scale variable-scale">
                <div
                  v-for="block in scaledVariableBlocks"
                  :key="block.id"
                  :class="['variable-block-segment', block.blockKey === activeVariableBlockKey ? 'variable-block-segment-active' : '']"
                  :style="{ left: block.left, width: block.width }"
                  :title="`${block.seqid}: ${block.start}-${block.end} (${block.length})`"
                ></div>
              </div>
              <div class="range-hints"><span>0</span><span>{{ formatNumber(variableScaleMax) }}</span></div>
              <div class="top-blocks variable-top-blocks">
                <div class="subsection-title">Top Variable Blocks</div>
                <div
                  v-for="item in topVariableBlocks"
                  :key="`${item.seqid}-${item.start}-${item.end}`"
                  :class="['top-block-item', item.blockKey === activeVariableBlockKey ? 'top-block-item-active' : '']"
                  role="button"
                  tabindex="0"
                  @click="toggleActiveVariableBlock(item)"
                  @keydown.enter.prevent="toggleActiveVariableBlock(item)"
                  @keydown.space.prevent="toggleActiveVariableBlock(item)"
                >
                  <span class="top-block-range">{{ item.seqid }}: {{ formatNumber(item.start) }} - {{ formatNumber(item.end) }}</span>
                  <span class="top-block-length">{{ formatNumber(item.length) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="details-panel">
          <el-tabs v-model="activeDetailTab" class="details-tabs">
            <el-tab-pane label="Core Details" name="core">
              <div class="table-panel">
                <div class="panel-header">
                  <h3 class="panel-title">Core Blocks Table</h3>
                  <span class="panel-tip">{{ coreBlocksData.length }} records</span>
                </div>
                <el-table
                  :data="coreBlocksData"
                  border
                  style="width: 100%"
                  :row-class-name="getTableRowClassName"
                  :header-cell-style="{ background: '#f0f5ff', color: '#1a56db', fontWeight: 'bold' }"
                >
                  <el-table-column prop="seqid" label="Chromosome" min-width="140" />
                  <el-table-column prop="start" label="Start" min-width="140">
                    <template #default="scope">{{ formatNumber(scope.row.start) }}</template>
                  </el-table-column>
                  <el-table-column prop="end" label="End" min-width="140">
                    <template #default="scope">{{ formatNumber(scope.row.end) }}</template>
                  </el-table-column>
                  <el-table-column prop="length" label="Length" min-width="140">
                    <template #default="scope">{{ formatNumber(scope.row.length) }}</template>
                  </el-table-column>
                </el-table>
              </div>
            </el-tab-pane>
            <el-tab-pane label="Variable Details" name="variable">
              <div class="table-panel">
                <div class="panel-header">
                  <h3 class="panel-title">Variable Blocks Table</h3>
                  <span class="panel-tip">{{ variableBlocksData.length }} records</span>
                </div>
                <div class="detail-summary-strip">
                  <div class="detail-summary-item">
                    <span class="detail-summary-label">Count</span>
                    <span class="detail-summary-value">{{ variableStats.blockCount }}</span>
                  </div>
                  <div class="detail-summary-item">
                    <span class="detail-summary-label">Total Length</span>
                    <span class="detail-summary-value">{{ formatNumber(variableStats.totalLength) }}</span>
                  </div>
                  <div class="detail-summary-item">
                    <span class="detail-summary-label">Coverage</span>
                    <span class="detail-summary-value">{{ variableTotalLengthCoverageValue }}</span>
                  </div>
                  <div class="detail-summary-item">
                    <span class="detail-summary-label">Longest</span>
                    <span class="detail-summary-value">{{ formatNumber(variableStats.maxLength) }}</span>
                  </div>
                </div>
                <p class="variable-placeholder-text variable-detail-note">
                  Matrix comparison will be added in the next stage. This first pass focuses on summary, distribution, and block details.
                </p>
                <div v-if="!variableBlocksFile" class="inline-empty variable-inline-empty">No variable block file is available for the current assembly.</div>
                <div v-else-if="!selectedChromosome" class="inline-empty variable-inline-empty">Select a chromosome to inspect variable block details.</div>
                <div v-else-if="loadingVariableBlocks" class="loading-inline"><el-skeleton :rows="5" animated /></div>
                <div v-else-if="!variableBlocksData.length" class="inline-empty variable-inline-empty">No variable block details are available for the current chromosome.</div>
                <el-table
                  v-else
                  :data="variableBlocksData"
                  border
                  style="width: 100%"
                  :row-class-name="getVariableTableRowClassName"
                  :header-cell-style="{ background: '#fff4ee', color: '#ea580c', fontWeight: 'bold' }"
                >
                  <el-table-column prop="seqid" label="Chromosome" min-width="140" />
                  <el-table-column prop="start" label="Start" min-width="140">
                    <template #default="scope">{{ formatNumber(scope.row.start) }}</template>
                  </el-table-column>
                  <el-table-column prop="end" label="End" min-width="140">
                    <template #default="scope">{{ formatNumber(scope.row.end) }}</template>
                  </el-table-column>
                  <el-table-column prop="length" label="Length" min-width="140">
                    <template #default="scope">{{ formatNumber(scope.row.length) }}</template>
                  </el-table-column>
                </el-table>
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { computed, onMounted, ref, watch } from 'vue';
import axios from 'axios';
import { ElMessage } from 'element-plus';
import { Refresh, Search } from '@element-plus/icons-vue';
import { useRoute, useRouter } from 'vue-router';

export default {
  name: 'CoreVariableBlocks',
  components: { Refresh, Search },
  setup() {
    const route = useRoute();
    const router = useRouter();
    const loadingPage = ref(false);
    const loadingOrganisms = ref(false);
    const loadingChromosomes = ref(false);
    const loadingBlocks = ref(false);
    const loadingVariableBlocks = ref(false);
    const selectedOrganism = ref('');
    const selectedChromosome = ref('');
    const organismOptions = ref([]);
    const allOrganisms = ref([]);
    const chromosomeOptions = ref([]);
    const activeDetailTab = ref('core');
    const accessionDetail = ref(null);
    const fileList = ref([]);
    const coreBlocksData = ref([]);
    const variableBlocksData = ref([]);
    const errorMessage = ref('');
    const chromosomeSource = ref('');
    const hierarchyAssemblies = ref([]);
    const contextAccession = ref('');
    const contextAssemblyId = ref('');
    const routeSyncInProgress = ref(false);
    const activeBlockKey = ref('');
    const activeVariableBlockKey = ref('');

    const clearPageData = () => {
      accessionDetail.value = null;
      fileList.value = [];
      hierarchyAssemblies.value = [];
      contextAccession.value = '';
      contextAssemblyId.value = '';
      chromosomeOptions.value = [];
      selectedChromosome.value = '';
      coreBlocksData.value = [];
      variableBlocksData.value = [];
      chromosomeSource.value = '';
      errorMessage.value = '';
      activeBlockKey.value = '';
      activeVariableBlockKey.value = '';
      activeDetailTab.value = 'core';
    };

    const formatNumber = (value) => {
      const num = Number(value || 0);
      return Number.isFinite(num) ? num.toLocaleString() : '-';
    };

    const buildBlockKey = (block) => (block ? `${block.seqid}:${block.start}:${block.end}` : '');
    const normalizeLineEndings = (text) => String(text || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    const normalizeQueryValue = (value) => Array.isArray(value) ? normalizeQueryValue(value[0]) : (value == null ? '' : String(value).trim());
    const matchesId = (left, right) => String(left) === String(right);

    const pickAssembly = (assemblies, assemblyId) => {
      if (!Array.isArray(assemblies) || !assemblies.length) return null;
      const normalizedAssemblyId = normalizeQueryValue(assemblyId);
      if (normalizedAssemblyId) {
        const matchedAssembly = assemblies.find((assembly) => matchesId(assembly?.id, normalizedAssemblyId));
        if (matchedAssembly) return matchedAssembly;
      }
      return assemblies.find((assembly) => assembly?.is_default) || assemblies[0];
    };

    const buildNormalizedQuery = ({ accession, assembly }) => {
      const query = {};
      if (accession) query.accession = String(accession);
      if (assembly) query.assembly = String(assembly);
      return query;
    };

    const replaceRouteQuery = async ({ accession, assembly }) => {
      routeSyncInProgress.value = true;
      try {
        await router.replace({ path: route.path, query: buildNormalizedQuery({ accession, assembly }) });
      } finally {
        routeSyncInProgress.value = false;
      }
    };

    const parseChromosomesFromBedText = (text) => {
      const chromosomes = new Set();
      for (const rawLine of normalizeLineEndings(text).split('\n')) {
        const line = rawLine.trim();
        if (!line || line.startsWith('#')) continue;
        const parts = line.split('\t');
        if (parts.length >= 3 && parts[0]) chromosomes.add(parts[0].trim());
      }
      return Array.from(chromosomes);
    };

    const coreBlocksFile = computed(() => fileList.value.find((file) => file.category === 'coreBlocks' && Number(file.size) > 0) || null);
    const variableBlocksFile = computed(() => fileList.value.find((file) => file.category === 'variableBlocks' && Number(file.size) > 0) || null);
    const currentAssembly = computed(() => pickAssembly(hierarchyAssemblies.value, contextAssemblyId.value));
    const stats = computed(() => {
      const lengths = coreBlocksData.value.map((item) => Number(item.length) || 0);
      const totalLength = lengths.reduce((sum, value) => sum + value, 0);
      const blockCount = lengths.length;
      return {
        blockCount,
        totalLength,
        maxLength: blockCount ? Math.max(...lengths) : 0,
        avgLength: blockCount ? Math.round(totalLength / blockCount) : 0
      };
    });
    const scaleMax = computed(() => !coreBlocksData.value.length ? 0 : Math.max(...coreBlocksData.value.map((item) => Number(item.end) || 0)));
    const totalLengthCoverage = computed(() => (!stats.value.totalLength || !scaleMax.value ? 0 : (stats.value.totalLength / scaleMax.value) * 100));
    const totalLengthCoverageText = computed(() => (!stats.value.totalLength || !scaleMax.value ? 'No coverage data' : `${totalLengthCoverage.value.toFixed(2)}% of current chromosome span`));
    const totalLengthCoverageValue = computed(() => `${totalLengthCoverage.value.toFixed(2)}%`);
    const variableStats = computed(() => {
      const lengths = variableBlocksData.value.map((item) => Number(item.length) || 0);
      const totalLength = lengths.reduce((sum, value) => sum + value, 0);
      const blockCount = lengths.length;
      return {
        blockCount,
        totalLength,
        maxLength: blockCount ? Math.max(...lengths) : 0
      };
    });
    const scaledBlocks = computed(() => {
      if (!coreBlocksData.value.length || !scaleMax.value) return [];
      return coreBlocksData.value.map((item, index) => {
        const start = Number(item.start) || 0;
        const end = Number(item.end) || 0;
        return {
          ...item,
          id: `${item.seqid}-${item.start}-${item.end}-${index}`,
          blockKey: buildBlockKey(item),
          left: `${(start / scaleMax.value) * 100}%`,
          width: `${Math.max(((end - start) / scaleMax.value) * 100, 0.6)}%`
        };
      });
    });
    const longestBlocks = computed(() => [...coreBlocksData.value]
      .sort((a, b) => (Number(b.length) || 0) - (Number(a.length) || 0))
      .map((item) => ({ ...item, blockKey: buildBlockKey(item) }))
      .slice(0, 8));
    const variableScaleMax = computed(() => !variableBlocksData.value.length ? 0 : Math.max(...variableBlocksData.value.map((item) => Number(item.end) || 0)));
    const variableTotalLengthCoverage = computed(() => (!variableStats.value.totalLength || !variableScaleMax.value ? 0 : (variableStats.value.totalLength / variableScaleMax.value) * 100));
    const variableTotalLengthCoverageText = computed(() => (!variableStats.value.totalLength || !variableScaleMax.value ? 'No coverage data' : `${variableTotalLengthCoverage.value.toFixed(2)}% of current chromosome span`));
    const variableTotalLengthCoverageValue = computed(() => `${variableTotalLengthCoverage.value.toFixed(2)}%`);
    const scaledVariableBlocks = computed(() => {
      if (!variableBlocksData.value.length || !variableScaleMax.value) return [];
      return variableBlocksData.value.map((item, index) => {
        const start = Number(item.start) || 0;
        const end = Number(item.end) || 0;
        return {
          ...item,
          id: `${item.seqid}-${item.start}-${item.end}-${index}`,
          blockKey: buildBlockKey(item),
          left: `${(start / variableScaleMax.value) * 100}%`,
          width: `${Math.max(((end - start) / variableScaleMax.value) * 100, 0.6)}%`
        };
      });
    });
    const topVariableBlocks = computed(() => [...variableBlocksData.value]
      .sort((a, b) => (Number(b.length) || 0) - (Number(a.length) || 0))
      .map((item) => ({ ...item, blockKey: buildBlockKey(item) }))
      .slice(0, 8));

    const toggleActiveBlock = (block) => {
      const nextKey = buildBlockKey(block);
      activeBlockKey.value = activeBlockKey.value === nextKey ? '' : nextKey;
    };
    const getTableRowClassName = ({ row }) => buildBlockKey(row) === activeBlockKey.value ? 'core-block-row-active' : '';
    const toggleActiveVariableBlock = (block) => {
      const nextKey = buildBlockKey(block);
      activeVariableBlockKey.value = activeVariableBlockKey.value === nextKey ? '' : nextKey;
    };
    const getVariableTableRowClassName = ({ row }) => buildBlockKey(row) === activeVariableBlockKey.value ? 'variable-block-row-active' : '';

    const fetchOrganisms = async () => {
      try {
        loadingOrganisms.value = true;
        const response = await axios.get('/files/query/organisms/');
        allOrganisms.value = response.data || [];
        organismOptions.value = allOrganisms.value;
      } catch (error) {
        console.error('Failed to load accessions:', error);
        ElMessage.error('Failed to load accessions');
      } finally {
        loadingOrganisms.value = false;
      }
    };

    const searchOrganisms = (query) => {
      organismOptions.value = query
        ? allOrganisms.value.filter((item) => item.toLowerCase().includes(query.toLowerCase()))
        : allOrganisms.value;
    };

    const fetchAccessionDetail = async (accession) => {
      const response = await axios.get(`/files/accessions/${accession}/`);
      if (!response.data?.success) throw new Error(response.data?.message || 'Failed to load accession detail');
      const payload = response.data.data || {};
      accessionDetail.value = payload.accession || null;
      hierarchyAssemblies.value = payload.assemblies || [];
      return payload;
    };

    const fetchChromosomesFromCoreBlocksFile = async () => {
      const downloadUrl = coreBlocksFile.value?.download_url || coreBlocksFile.value?.datafile_download_url;
      if (!downloadUrl) return [];
      try {
        const response = await axios.get(new URL(downloadUrl, window.location.origin).toString(), { responseType: 'text' });
        return parseChromosomesFromBedText(response.data);
      } catch (error) {
        console.error('Failed to parse chromosomes from coreBlocks file:', error);
        return [];
      }
    };

    const fetchChromosomes = async () => {
      try {
        loadingChromosomes.value = true;
        chromosomeSource.value = '';
        let chromosomes = [];
        try {
          const response = await axios.get('/files/query/chromosomes/', {
            params: {
              ...(contextAssemblyId.value ? { assembly_id: contextAssemblyId.value } : {}),
              ...(contextAccession.value ? { accession: contextAccession.value } : {}),
              ...(!contextAssemblyId.value && !contextAccession.value && selectedOrganism.value ? { organism: selectedOrganism.value } : {})
            }
          });
          chromosomes = response.data || [];
          if (chromosomes.length > 0) chromosomeSource.value = 'genome';
        } catch (error) {
          console.warn('Genome chromosome endpoint failed, fallback to coreBlocks file:', error);
        }
        if (!chromosomes || !chromosomes.length) {
          chromosomes = await fetchChromosomesFromCoreBlocksFile();
          if (chromosomes.length > 0) chromosomeSource.value = 'coreBlocks';
        }
        chromosomeOptions.value = chromosomes || [];
        if (!chromosomeOptions.value.length) ElMessage.warning('No chromosome options were found');
      } catch (error) {
        console.error('Failed to load chromosomes:', error);
        chromosomeOptions.value = [];
        chromosomeSource.value = '';
        ElMessage.error('Failed to load chromosomes');
      } finally {
        loadingChromosomes.value = false;
      }
    };

    const fetchCoreBlocks = async () => {
      if (!selectedOrganism.value || !selectedChromosome.value || !coreBlocksFile.value) {
        coreBlocksData.value = [];
        activeBlockKey.value = '';
        return;
      }
      try {
        loadingBlocks.value = true;
        const response = await axios.get('/files/query/core-blocks/', {
          params: {
            ...(contextAssemblyId.value ? { assembly_id: contextAssemblyId.value } : {}),
            ...(contextAccession.value ? { accession: contextAccession.value } : {}),
            organism: selectedOrganism.value,
            chromosome: selectedChromosome.value
          }
        });
        coreBlocksData.value = response.data || [];
        activeBlockKey.value = '';
      } catch (error) {
        console.error('Failed to load coreBlocks:', error);
        coreBlocksData.value = [];
        ElMessage.error('Failed to load coreBlocks');
      } finally {
        loadingBlocks.value = false;
      }
    };

    const fetchVariableBlocks = async () => {
      if (!selectedOrganism.value || !selectedChromosome.value || !variableBlocksFile.value) {
        variableBlocksData.value = [];
        activeVariableBlockKey.value = '';
        return;
      }
      try {
        loadingVariableBlocks.value = true;
        const response = await axios.get('/files/query/variable-blocks/', {
          params: {
            ...(contextAssemblyId.value ? { assembly_id: contextAssemblyId.value } : {}),
            ...(contextAccession.value ? { accession: contextAccession.value } : {}),
            organism: selectedOrganism.value,
            chromosome: selectedChromosome.value
          }
        });
        variableBlocksData.value = response.data || [];
        activeVariableBlockKey.value = '';
      } catch (error) {
        console.error('Failed to load variableBlocks:', error);
        variableBlocksData.value = [];
      } finally {
        loadingVariableBlocks.value = false;
      }
    };

    const loadOrganismPage = async () => {
      const accession = normalizeQueryValue(route.query.accession) || normalizeQueryValue(route.query.organism);
      if (!accession) {
        clearPageData();
        return;
      }
      try {
        loadingPage.value = true;
        errorMessage.value = '';
        selectedOrganism.value = accession;
        contextAccession.value = accession;
        const payload = await fetchAccessionDetail(accession);
        const resolvedAssembly = pickAssembly(payload.assemblies || [], route.query.assembly);
        contextAssemblyId.value = resolvedAssembly?.id ? String(resolvedAssembly.id) : '';
        fileList.value = resolvedAssembly?.files || [];
        const normalizedAssembly = resolvedAssembly?.id ? String(resolvedAssembly.id) : '';
        const routeAssembly = normalizeQueryValue(route.query.assembly);
        const routeHasLegacyOrganism = Boolean(normalizeQueryValue(route.query.organism));
        if (routeHasLegacyOrganism || routeAssembly !== normalizedAssembly) {
          await replaceRouteQuery({ accession, assembly: normalizedAssembly });
        }
        await fetchChromosomes();
        if (chromosomeOptions.value.length > 0) {
          selectedChromosome.value = chromosomeOptions.value.includes(selectedChromosome.value) ? selectedChromosome.value : chromosomeOptions.value[0];
          await Promise.all([fetchCoreBlocks(), fetchVariableBlocks()]);
        } else {
          selectedChromosome.value = '';
          coreBlocksData.value = [];
          variableBlocksData.value = [];
        }
      } catch (error) {
        console.error('Failed to load Core&Variable Blocks page:', error);
        clearPageData();
        errorMessage.value = 'Failed to load Core&Variable Blocks data';
        ElMessage.error('Failed to load Core&Variable Blocks data');
      } finally {
        loadingPage.value = false;
      }
    };

    const handleOrganismChange = async (value) => {
      selectedOrganism.value = value || '';
      if (!selectedOrganism.value) {
        clearPageData();
        await replaceRouteQuery({ accession: '', assembly: '' });
        return;
      }
      await replaceRouteQuery({ accession: selectedOrganism.value, assembly: '' });
      await loadOrganismPage();
    };

    const handleChromosomeChange = async () => {
      await Promise.all([fetchCoreBlocks(), fetchVariableBlocks()]);
    };

    const refreshPage = async () => {
      if (!selectedOrganism.value) {
        clearPageData();
        return;
      }
      await loadOrganismPage();
    };

    watch(() => [route.query.accession, route.query.assembly, route.query.organism], async () => {
      if (!routeSyncInProgress.value) await loadOrganismPage();
    });

    watch(() => coreBlocksData.value, (blocks) => {
      if (!activeBlockKey.value) return;
      const stillExists = (blocks || []).some((item) => buildBlockKey(item) === activeBlockKey.value);
      if (!stillExists) activeBlockKey.value = '';
    }, { deep: true });
    watch(() => variableBlocksData.value, (blocks) => {
      if (!activeVariableBlockKey.value) return;
      const stillExists = (blocks || []).some((item) => buildBlockKey(item) === activeVariableBlockKey.value);
      if (!stillExists) activeVariableBlockKey.value = '';
    }, { deep: true });

    onMounted(async () => {
      await fetchOrganisms();
      await loadOrganismPage();
    });

    return {
      loadingPage,
      loadingOrganisms,
      loadingChromosomes,
      loadingBlocks,
      loadingVariableBlocks,
      selectedOrganism,
      selectedChromosome,
      organismOptions,
      chromosomeOptions,
      activeDetailTab,
      accessionDetail,
      coreBlocksData,
      variableBlocksData,
      coreBlocksFile,
      variableBlocksFile,
      currentAssembly,
      errorMessage,
      stats,
      variableStats,
      totalLengthCoverageText,
      totalLengthCoverageValue,
      variableTotalLengthCoverageText,
      variableTotalLengthCoverageValue,
      scaleMax,
      scaledBlocks,
      longestBlocks,
      variableScaleMax,
      scaledVariableBlocks,
      topVariableBlocks,
      activeBlockKey,
      activeVariableBlockKey,
      toggleActiveBlock,
      toggleActiveVariableBlock,
      getTableRowClassName,
      getVariableTableRowClassName,
      searchOrganisms,
      handleOrganismChange,
      handleChromosomeChange,
      refreshPage,
      formatNumber
    };
  }
};
</script>

<style scoped>
.core-variable-blocks-view { padding: 0; }
.page-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:24px; }
.title { margin:0; font-size:24px; font-weight:600; color:#1a56db; }
.header-actions, .toolbar-main { display:flex; gap:16px; flex-wrap:wrap; }
.toolbar { display:flex; justify-content:space-between; gap:16px; align-items:flex-end; margin-bottom:24px; flex-wrap:wrap; }
.search-wrapper, .chromosome-wrapper { display:flex; align-items:center; background:#fff; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,.05); }
.search-wrapper { padding:0 16px; min-width:320px; }
.chromosome-wrapper { padding:0 12px; gap:12px; }
.search-icon { color:#606266; margin-right:8px; flex-shrink:0; }
.search-select { min-width:240px; }
.chromosome-select { min-width:180px; }
.field-label, .panel-tip, .info-label, .stat-label, .stat-subvalue, .range-hints, .inline-empty, .variable-placeholder-text { color:#6b7280; font-size:13px; }
.field-label { white-space:nowrap; }
.data-card, .summary-panel, .overview-panel, .details-panel, .table-panel, .warning-panel { background:#fff; border:1px solid #eef2f7; border-radius:12px; }
.data-card { box-shadow:0 2px 12px rgba(0,0,0,.08); padding:24px; }
.loading { padding:20px; }
.empty-state { padding:48px 20px; }
.content-container, .variable-placeholder, .disabled-panel-body { display:flex; flex-direction:column; gap:24px; }
.summary-panel, .overview-panel, .details-panel, .table-panel, .warning-panel { padding:20px; }
.panel-header { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:18px; }
.summary-panel {
  padding: 14px 16px;
  background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
}
.summary-header { margin-bottom:12px; }
.panel-title { margin:0; font-size:18px; font-weight:600; color:#1a56db; }
.panel-badge { display:inline-flex; align-items:center; padding:4px 10px; border-radius:999px; background:#eef4ff; color:#1a56db; font-size:12px; font-weight:600; }
.panel-badge-muted { background:#f3f4f6; color:#6b7280; }
.summary-grid { display:grid; grid-template-columns:repeat(6, minmax(0,1fr)); gap:14px; }
.summary-grid {
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 10px;
}
.summary-item {
  background:#f8fbff;
  border: 1px solid #eef4ff;
  border-radius:8px;
  padding:10px 12px;
  min-height:auto;
  grid-column: span 2;
}
.summary-item-wide { grid-column:span 2; }
.summary-value { color:#111827; line-height:1.5; font-size:15px; font-weight:500; }
.summary-value-ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.text-break, .top-block-range { word-break:break-word; }
.overview-grid { display:grid; grid-template-columns:minmax(0,1.2fr) minmax(320px,.8fr); gap:24px; }
.overview-panel-variable { background:linear-gradient(180deg, #ffffff 0%, #fcfcff 100%); }
.stats-list { display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:14px; margin-bottom:18px; }
.stat-card, .top-blocks { background:#f8fbff; border-radius:10px; padding:14px 16px; }
.variable-stats-list .stat-card { background: #fff7f2; }
.stat-value { color:#111827; font-size:20px; font-weight:600; }
.warning-panel { background:#fffbeb; border-color:#fcd34d; }
.overview-warning { margin-top:8px; }
.warning-title { color:#92400e; font-weight:600; margin-bottom:8px; }
.warning-text { color:#92400e; }
.inline-empty { padding:32px 0; }
.loading-inline { padding:12px 0; }
.visual-content { display:flex; flex-direction:column; gap:18px; }
.chromosome-scale, .variable-band-placeholder { position:relative; width:100%; height:36px; border-radius:999px; background:linear-gradient(90deg, #e5e7eb 0%, #f3f4f6 100%); overflow:hidden; }
.block-segment { position:absolute; top:8px; height:20px; background:linear-gradient(90deg, #2563eb 0%, #60a5fa 100%); border-radius:999px; box-shadow:0 2px 8px rgba(37,99,235,.25); transition:transform .18s ease, box-shadow .18s ease, opacity .18s ease; }
.block-segment-active { transform:translateY(-1px) scaleY(1.08); background:linear-gradient(90deg, #dc2626 0%, #f87171 100%); box-shadow:0 0 0 2px rgba(220,38,38,.18), 0 6px 14px rgba(220,38,38,.35); }
.variable-scale { background: linear-gradient(90deg, #f3f4f6 0%, #fff7ed 100%); }
.variable-block-segment { position:absolute; top:8px; height:20px; background:linear-gradient(90deg, #f97316 0%, #fb7185 100%); border-radius:999px; box-shadow:0 2px 8px rgba(249,115,22,.25); transition:transform .18s ease, box-shadow .18s ease, opacity .18s ease; }
.variable-block-segment-active { transform:translateY(-1px) scaleY(1.08); background:linear-gradient(90deg, #dc2626 0%, #fb7185 100%); box-shadow:0 0 0 2px rgba(220,38,38,.18), 0 6px 14px rgba(220,38,38,.35); }
.range-hints { display:flex; justify-content:space-between; font-size:12px; }
.subsection-title, .placeholder-subtitle { color:#1f2937; font-size:14px; font-weight:600; margin-bottom:10px; }
.top-block-item { display:flex; justify-content:space-between; gap:12px; padding:8px 0; border-bottom:1px solid #eef2f7; cursor:pointer; border-radius:8px; transition:background-color .18s ease, box-shadow .18s ease; }
.top-block-item:hover { background:#eef4ff; }
.top-block-item-active { background:#fef2f2; box-shadow:inset 0 0 0 1px #fca5a5; }
.top-block-item:last-child { border-bottom:none; }
.top-block-length { color:#1a56db; font-weight:600; white-space:nowrap; }
.variable-inline-empty { padding:0; }
.placeholder-list, .disabled-panel-body { display:flex; flex-direction:column; gap:12px; }
.placeholder-list-item, .disabled-card { height:72px; border-radius:12px; background:linear-gradient(90deg, #f9fafb 0%, #eef2f7 100%); }
.variable-top-blocks { background: #fff7f2; }
.short { height:56px; }
.details-tabs { margin-top:-4px; }
.detail-summary-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}
.detail-summary-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid #e8eefc;
  border-radius: 10px;
  background: #f8fbff;
}
.detail-summary-label {
  color: #6b7280;
  font-size: 12px;
}
.detail-summary-value {
  color: #1f2937;
  font-size: 14px;
  font-weight: 600;
}
.variable-details-placeholder { padding-top:8px; }
.variable-placeholder-text { margin:0 0 18px; line-height:1.7; }
:deep(.el-tabs__item.is-active) { color:#1a56db; }
:deep(.el-tabs__active-bar) { background-color:#1a56db; }
:deep(.el-table) { --el-table-border-color:#e5e7eb; --el-table-header-bg-color:#f0f5ff; --el-table-row-hover-bg-color:#f9fafb; }
:deep(.el-table th) { font-weight:600; }
:deep(.el-table .core-block-row-active td) { background:#fef2f2 !important; }
:deep(.el-table .variable-block-row-active td) { background:#fff7ed !important; }
@media (max-width:1200px) {
  .summary-grid { grid-template-columns:repeat(3, minmax(0,1fr)); }
  .summary-item,
  .summary-item-wide { grid-column:span 1; }
  .stats-list { grid-template-columns:repeat(2, minmax(0,1fr)); }
  .detail-summary-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width:1100px) { .overview-grid { grid-template-columns:1fr; } }
@media (max-width:900px) {
  .summary-grid, .stats-list { grid-template-columns:1fr; }
  .detail-summary-strip { grid-template-columns: 1fr; }
  .search-wrapper, .chromosome-wrapper { width:100%; }
  .search-select, .chromosome-select { width:100%; min-width:0; }
}
</style>
