<template>
  <div class="codon-card-view">
    <div class="page-header">
      <h2 class="title">{{ $t('page.codonCard.title') }}</h2>
      <div class="header-actions">
        <el-tooltip :content="$t('page.codonCard.refreshData')" placement="top">
          <el-button circle size="small" @click="fetchFiles">
            <el-icon><Refresh /></el-icon>
          </el-button>
        </el-tooltip>
      </div>
    </div>

    <!-- 搜索和上传区域 -->
    <div class="search-container">
      <!-- 搜索框和上传按钮 -->
      <div class="search-wrapper">
        <el-icon class="search-icon"><Search /></el-icon>
        <el-select
          v-model="selectedOrganism"
          filterable
          remote
          :placeholder="$t('page.codonCard.searchPlaceholder')"
          :remote-method="searchOrganisms"
          :loading="loadingOrganisms"
          clearable
          @change="handleOrganismChange"
          class="search-select"
        >
          <el-option
            v-for="item in organismOptions"
            :key="item"
            :label="item"
            :value="item"
          />
        </el-select>

        <!-- 上传CodonW结果按钮 -->
        <el-upload
          ref="resultUploadRef"
          :action="uploadUrl"
          :headers="uploadHeaders"
          :on-success="handleResultUploadSuccess"
          :on-error="handleResultUploadError"
          :before-upload="beforeResultUpload"
          :show-file-list="false"
          accept=".zip"
          :auto-upload="true"
          style="margin-left: 10px;"
        >
          <el-button type="primary" size="small">
            <el-icon><Upload /></el-icon>
            {{ $t('page.codonCard.uploadCodonWResults') }}
          </el-button>
        </el-upload>
      </div>
    </div>

    <div class="data-card">
      <!-- 调试信息 (可以删除) -->
      <!-- <div style="background: #f0f0f0; padding: 10px; margin-bottom: 10px; font-size: 12px;">
        Debug: loading={{ loading }}, selectedOrganism={{ selectedOrganism }}, hasCodonData={{ !!codonData }}, hasError={{ !!error }}
      </div> -->

      <div v-if="loading" class="loading">
        <el-skeleton :rows="6" animated />
      </div>

      <div v-else-if="codonData" class="content-container">
        <div class="codon-info">
          <h3>{{ $t('page.codonCard.codonUsageData') }} - {{ selectedOrganism }}</h3>

          <!-- 基本统计信息 -->
          <div v-if="codonData.statistics" class="stats-section">
            <div class="section-header">
              <h4>📊 {{ $t('page.codonCard.codonUsageStatistics') }}</h4>
              <p class="section-subtitle">{{ $t('page.codonCard.statisticsSubtitle') }}</p>
            </div>

            <!-- 核苷酸组成可视化 -->
            <div class="nucleotide-composition">
              <h5 class="subsection-title">🧬 {{ $t('page.codonCard.nucleotideComposition') }}</h5>
              <div class="nucleotide-chart">
                <div class="nucleotide-bars">
                  <div class="nucleotide-bar" v-for="(nucleotide, index) in nucleotideData" :key="nucleotide.name">
                    <div class="nucleotide-info">
                      <span class="nucleotide-name">{{ nucleotide.name }}</span>
                      <span class="nucleotide-value">{{ nucleotide.percentage }}%</span>
                    </div>
                    <div class="nucleotide-bar-container">
                      <div
                        class="nucleotide-bar-fill"
                        :style="{
                          width: nucleotide.percentage + '%',
                          backgroundColor: nucleotide.color
                        }">
                      </div>
                    </div>
                  </div>
                </div>
                <div class="nucleotide-summary">
                  <div class="gc-content">
                    <span class="gc-label">{{ $t('page.codonCard.gcContent') }}</span>
                    <span class="gc-value">{{ (codonData.statistics.GC * 100).toFixed(1) }}%</span>
                    <div class="gc-bar">
                      <div
                        class="gc-bar-fill"
                        :style="{ width: (codonData.statistics.GC * 100) + '%' }">
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 密码子使用偏好性指标 -->
            <div class="bias-indicators">
              <h5 class="subsection-title">📈 {{ $t('page.codonCard.codonUsageIndicators') }}</h5>
              <div class="indicators-grid">
                <el-tooltip
                  effect="dark"
                  placement="top"
                  :show-after="500">
                  <template #content>
                    <div class="tooltip-content">
                      <strong>CAI (Codon Adaptation Index)</strong><br/>
                      {{ $t('page.codonCard.caiDescription') }}<br/>
                      <em>{{ $t('page.codonCard.caiRange') }}</em>
                    </div>
                  </template>
                  <div class="indicator-card cai-card">
                    <div class="indicator-header">
                      <span class="indicator-name">CAI</span>
                      <el-icon class="help-icon"><QuestionFilled /></el-icon>
                    </div>
                    <div class="indicator-value">{{ codonData.statistics.CAI?.toFixed(3) || 'N/A' }}</div>
                    <div class="indicator-description">{{ $t('page.codonCard.caiLabel') }}</div>
                    <div class="indicator-progress">
                      <div
                        class="progress-bar cai-progress"
                        :style="{ width: (codonData.statistics.CAI * 100) + '%' }">
                      </div>
                    </div>
                  </div>
                </el-tooltip>

                <el-tooltip
                  effect="dark"
                  placement="top"
                  :show-after="500">
                  <template #content>
                    <div class="tooltip-content">
                      <strong>CBI (Codon Bias Index)</strong><br/>
                      {{ $t('page.codonCard.cbiDescription') }}<br/>
                      <em>{{ $t('page.codonCard.cbiRange') }}</em>
                    </div>
                  </template>
                  <div class="indicator-card cbi-card">
                    <div class="indicator-header">
                      <span class="indicator-name">CBI</span>
                      <el-icon class="help-icon"><QuestionFilled /></el-icon>
                    </div>
                    <div class="indicator-value">{{ codonData.statistics.CBI?.toFixed(3) || 'N/A' }}</div>
                    <div class="indicator-description">{{ $t('page.codonCard.cbiLabel') }}</div>
                    <div class="indicator-progress">
                      <div
                        class="progress-bar cbi-progress"
                        :style="{ width: ((codonData.statistics.CBI + 1) * 50) + '%' }">
                      </div>
                    </div>
                  </div>
                </el-tooltip>

                <el-tooltip
                  effect="dark"
                  placement="top"
                  :show-after="500">
                  <template #content>
                    <div class="tooltip-content">
                      <strong>Fop (Frequency of Optimal codons)</strong><br/>
                      {{ $t('page.codonCard.fopDescription') }}<br/>
                      <em>{{ $t('page.codonCard.fopRange') }}</em>
                    </div>
                  </template>
                  <div class="indicator-card fop-card">
                    <div class="indicator-header">
                      <span class="indicator-name">Fop</span>
                      <el-icon class="help-icon"><QuestionFilled /></el-icon>
                    </div>
                    <div class="indicator-value">{{ codonData.statistics.Fop?.toFixed(3) || 'N/A' }}</div>
                    <div class="indicator-description">{{ $t('page.codonCard.fopLabel') }}</div>
                    <div class="indicator-progress">
                      <div
                        class="progress-bar fop-progress"
                        :style="{ width: (codonData.statistics.Fop * 100) + '%' }">
                      </div>
                    </div>
                  </div>
                </el-tooltip>

                <el-tooltip
                  effect="dark"
                  placement="top"
                  :show-after="500">
                  <template #content>
                    <div class="tooltip-content">
                      <strong>Nc (Number of Codons)</strong><br/>
                      {{ $t('page.codonCard.ncDescription') }}<br/>
                      <em>{{ $t('page.codonCard.ncRange') }}</em>
                    </div>
                  </template>
                  <div class="indicator-card nc-card">
                    <div class="indicator-header">
                      <span class="indicator-name">Nc</span>
                      <el-icon class="help-icon"><QuestionFilled /></el-icon>
                    </div>
                    <div class="indicator-value">{{ codonData.statistics.Nc?.toFixed(1) || 'N/A' }}</div>
                    <div class="indicator-description">{{ $t('page.codonCard.ncLabel') }}</div>
                    <div class="indicator-progress">
                      <div
                        class="progress-bar nc-progress"
                        :style="{ width: ((61 - codonData.statistics.Nc) / 41 * 100) + '%' }">
                      </div>
                    </div>
                  </div>
                </el-tooltip>
              </div>
            </div>

            <!-- 其他统计指标 -->
            <div class="additional-stats">
              <h5 class="subsection-title">🔬 {{ $t('page.codonCard.otherStatistics') }}</h5>
              <div class="stats-compact-grid">
                <el-tooltip
                  effect="dark"
                  placement="top"
                  :show-after="500">
                  <template #content>
                    <div class="tooltip-content">
                      <strong>GC3s (GC content at 3rd codon position)</strong><br/>
                      {{ $t('page.codonCard.gc3sDescription') }}<br/>
                      <em>{{ $t('page.codonCard.gc3sNote') }}</em>
                    </div>
                  </template>
                  <div class="compact-stat-card tooltip-trigger">
                    <div class="compact-stat-label">
                      {{ $t('page.codonCard.gc3sLabel') }}
                      <el-icon class="help-icon-small"><QuestionFilled /></el-icon>
                    </div>
                    <div class="compact-stat-value">{{ (codonData.statistics.GC3s * 100).toFixed(1) }}%</div>
                  </div>
                </el-tooltip>

                <el-tooltip
                  effect="dark"
                  placement="top"
                  :show-after="500">
                  <template #content>
                    <div class="tooltip-content">
                      <strong>L_aa (Amino Acid Length)</strong><br/>
                      {{ $t('page.codonCard.sequenceLengthDescription') }}<br/>
                      <em>{{ $t('page.codonCard.sequenceLengthNote') }}</em>
                    </div>
                  </template>
                  <div class="compact-stat-card tooltip-trigger">
                    <div class="compact-stat-label">
                      {{ $t('page.codonCard.sequenceLengthLabel') }}
                      <el-icon class="help-icon-small"><QuestionFilled /></el-icon>
                    </div>
                    <div class="compact-stat-value">{{ formatLargeNumber(codonData.statistics.L_aa) }}</div>
                  </div>
                </el-tooltip>

                <el-tooltip
                  effect="dark"
                  placement="top"
                  :show-after="500">
                  <template #content>
                    <div class="tooltip-content">
                      <strong>Gravy (Grand Average of Hydropathy)</strong><br/>
                      {{ $t('page.codonCard.gravyDescription') }}<br/>
                      <em>{{ $t('page.codonCard.gravyNote') }}</em>
                    </div>
                  </template>
                  <div class="compact-stat-card tooltip-trigger">
                    <div class="compact-stat-label">
                      {{ $t('page.codonCard.gravyLabel') }}
                      <el-icon class="help-icon-small"><QuestionFilled /></el-icon>
                    </div>
                    <div class="compact-stat-value">{{ codonData.statistics.Gravy?.toFixed(3) || 'N/A' }}</div>
                  </div>
                </el-tooltip>

                <el-tooltip
                  effect="dark"
                  placement="top"
                  :show-after="500">
                  <template #content>
                    <div class="tooltip-content">
                      <strong>Aromo (Aromaticity)</strong><br/>
                      {{ $t('page.codonCard.aromoDescription') }}<br/>
                      <em>{{ $t('page.codonCard.aromoNote') }}</em>
                    </div>
                  </template>
                  <div class="compact-stat-card tooltip-trigger">
                    <div class="compact-stat-label">
                      {{ $t('page.codonCard.aromoLabel') }}
                      <el-icon class="help-icon-small"><QuestionFilled /></el-icon>
                    </div>
                    <div class="compact-stat-value">{{ codonData.statistics.Aromo?.toFixed(3) || 'N/A' }}</div>
                  </div>
                </el-tooltip>
              </div>
            </div>
          </div>

          <!-- 氨基酸数据表格 -->
          <div v-if="codonData.amino_acids" class="amino-acids-section">
            <h4>🧬 {{ $t('page.codonCard.aminoAcidUsage') }}</h4>
            <!-- 自定义氨基酸表格 -->
            <div class="custom-amino-acid-table">
              <div class="table-header">
                <div class="header-cell expand-cell"></div>
                <div class="header-cell name-cell">{{ $t('page.codonCard.aminoAcid') }}</div>
                <div class="header-cell count-cell">{{ $t('page.codonCard.totalUsage') }}</div>
                <div class="header-cell codon-count-cell">{{ $t('page.codonCard.codonCount') }}</div>
                <div class="header-cell frequency-cell">{{ $t('page.codonCard.usageFrequency') }}</div>
              </div>

              <div class="table-body">
                <div
                  v-for="aa in sortedAminoAcids"
                  :key="aa.name"
                  class="amino-acid-row-group">

                  <!-- 主行 -->
                  <div
                    class="amino-acid-row"
                    :class="{ 'expanded': expandedRows.includes(aa.name) }"
                    @click="toggleRowExpansion(aa)">

                    <div class="row-cell expand-cell">
                      <el-icon class="expand-icon" :class="{ 'expanded': expandedRows.includes(aa.name) }">
                        <ArrowRight />
                      </el-icon>
                    </div>

                    <div class="row-cell name-cell">
                      <el-tag type="primary">{{ aa.name }}</el-tag>
                    </div>

                    <div class="row-cell count-cell">
                      {{ aa.total_count.toLocaleString() }}
                    </div>

                    <div class="row-cell codon-count-cell">
                      {{ aa.codons.length }}
                    </div>

                    <div class="row-cell frequency-cell">
                      <div class="frequency-bar">
                        <div
                          class="frequency-fill"
                          :style="{ width: getPercentage(aa.total_count) + '%' }">
                        </div>
                        <span class="frequency-text">{{ getPercentage(aa.total_count).toFixed(1) }}%</span>
                      </div>
                    </div>
                  </div>

                  <!-- 展开的详情行 -->
                  <div
                    v-if="expandedRows.includes(aa.name)"
                    class="expand-content">
                    <div class="expand-header">
                      <h5>{{ aa.name }} {{ $t('page.codonCard.codonDetails') }}</h5>
                    </div>
                    <div class="codon-details-table">
                      <div class="codon-header">
                        <div class="codon-header-cell">{{ $t('page.codonCard.codon') }}</div>
                        <div class="codon-header-cell">{{ $t('page.codonCard.usageCount') }}</div>
                        <div class="codon-header-cell">
                          <el-tooltip
                            effect="dark"
                            placement="top"
                            :show-after="500">
                            <template #content>
                              <div class="tooltip-content">
                                <strong>RSCU (Relative Synonymous Codon Usage)</strong><br/>
                                {{ $t('page.codonCard.rscuDescription') }}<br/>
                                <em>{{ $t('page.codonCard.rscuNote') }}</em>
                              </div>
                            </template>
                            <span class="tooltip-trigger">
                              RSCU
                              <el-icon class="help-icon-small"><QuestionFilled /></el-icon>
                            </span>
                          </el-tooltip>
                        </div>
                        <div class="codon-header-cell">{{ $t('page.codonCard.relativeFrequency') }}</div>
                      </div>
                      <div
                        v-for="codon in getSortedCodons(aa.codons)"
                        :key="codon.codon"
                        class="codon-row">
                        <div class="codon-cell">{{ codon.codon }}</div>
                        <div class="codon-cell">{{ codon.count.toLocaleString() }}</div>
                        <div class="codon-cell">{{ codon.frequency.toFixed(3) }}</div>
                        <div class="codon-cell">{{ (codon.relative_frequency * 100).toFixed(1) }}%</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 无数据状态 -->
      <div v-else-if="error" class="no-data-container">
        <div v-if="isNoCodonDataError" class="no-codon-data">
          <div class="no-data-icon">🧬</div>
          <h3>{{ $t('page.codonCard.noCodonData') }}</h3>
          <p class="no-data-message">
            {{ $t('page.codonCard.noDataMessage', { organism: selectedOrganism }) }}
          </p>
          <div class="no-data-details">
            <p>{{ $t('page.codonCard.possibleReasons') }}</p>
            <ul>
              <li>{{ $t('page.codonCard.reasonAnalysisIncomplete') }}</li>
              <li>{{ $t('page.codonCard.reasonDataProcessing') }}</li>
              <li>{{ $t('page.codonCard.reasonNotInScope') }}</li>
            </ul>
          </div>
          <div class="no-data-actions">
            <el-button @click="tryAnotherOrganism" type="primary">
              {{ $t('page.codonCard.tryAnotherOrganism') }}
            </el-button>
            <el-button @click="fetchFiles" type="default">
              {{ $t('page.codonCard.recheck') }}
            </el-button>
          </div>
        </div>

        <!-- 其他错误 -->
        <div v-else class="error-container">
          <el-alert
            :title="$t('page.codonCard.dataLoadFailed')"
            :description="error"
            type="error"
            show-icon>
          </el-alert>
          <el-button @click="fetchFiles" type="primary" style="margin-top: 20px;">
            {{ $t('page.codonCard.reload') }}
          </el-button>
        </div>
      </div>

      <!-- 未选择生物体状态 -->
      <div v-else-if="!selectedOrganism" class="welcome-container">
        <div class="welcome-content">
          <!-- 欢迎标题 -->
          <div class="welcome-header">
            <div class="welcome-icon">🧬</div>
            <h2>{{ $t('page.codonCard.codonUsageAnalysis') }}</h2>
            <p class="welcome-subtitle">{{ $t('page.codonCard.analysisSubtitle') }}</p>
          </div>

          <!-- 功能介绍 -->
          <div class="feature-grid">
            <div class="feature-card">
              <div class="feature-icon">📊</div>
              <h4>{{ $t('page.codonCard.statisticalAnalysis') }}</h4>
              <p>{{ $t('page.codonCard.statisticalDescription') }}</p>
            </div>

            <div class="feature-card">
              <div class="feature-icon">🧪</div>
              <h4>{{ $t('page.codonCard.aminoAcidComposition') }}</h4>
              <p>{{ $t('page.codonCard.aminoAcidDescription') }}</p>
            </div>

            <div class="feature-card">
              <div class="feature-icon">🔬</div>
              <h4>{{ $t('page.codonCard.gcAnalysis') }}</h4>
              <p>{{ $t('page.codonCard.gcDescription') }}</p>
            </div>

            <div class="feature-card">
              <div class="feature-icon">📈</div>
              <h4>{{ $t('page.codonCard.proteinProperties') }}</h4>
              <p>{{ $t('page.codonCard.proteinDescription') }}</p>
            </div>
          </div>

          <!-- 使用指南 -->
          <div class="usage-guide">
            <h3>🚀 {{ $t('page.codonCard.startAnalysis') }}</h3>
            <div class="guide-steps">
              <div class="step">
                <span class="step-number">1</span>
                <span class="step-text">{{ $t('page.codonCard.step1') }}</span>
              </div>
              <div class="step">
                <span class="step-number">2</span>
                <span class="step-text">{{ $t('page.codonCard.step2') }}</span>
              </div>
              <div class="step">
                <span class="step-number">3</span>
                <span class="step-text">{{ $t('page.codonCard.step3') }}</span>
              </div>
            </div>
          </div>

          <!-- 示例数据 -->
          <div class="example-section">
            <h3>💡 {{ $t('page.codonCard.exampleData') }}</h3>
            <p>{{ $t('page.codonCard.exampleDescription') }}</p>
            <div class="example-organisms">
              <el-button
                v-for="example in exampleOrganisms"
                :key="example.id"
                @click="selectExample(example.id)"
                type="primary"
                plain
                size="small">
                {{ example.id }} - {{ example.name }}
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, computed, watch } from 'vue';
import axios from 'axios';
import { ElMessage } from 'element-plus';
import { Search, Refresh, QuestionFilled, ArrowRight, Upload } from '@element-plus/icons-vue';
import { useRoute } from 'vue-router';
import { useI18n } from 'vue-i18n';

export default {
  name: 'CodonCard',
  components: {
    Search,
    Refresh,
    QuestionFilled,
    ArrowRight,
    Upload
  },
  setup() {
    const route = useRoute();
    const { t } = useI18n();
    const loading = ref(false); // 初始不显示loading，显示欢迎页面
    const selectedOrganism = ref('');
    const organismOptions = ref([]);
    const loadingOrganisms = ref(false);
    const allOrganisms = ref([]);
    const codonData = ref(null);
    const error = ref(null);

    // 示例生物体数据
    const exampleOrganisms = ref([
      { id: 'IR64', name: t('page.codonCard.riceVariety') }
    ]);

    // 展开的行状态
    const expandedRows = ref([]);

    // 获取所有生物体列表
    const fetchOrganisms = async () => {
      try {
        loadingOrganisms.value = true;
        const response = await axios.get('/files/genome-files/organisms/');
        allOrganisms.value = response.data || [];
        organismOptions.value = allOrganisms.value;
      } catch (error) {
        console.error('获取生物体列表失败:', error);
        // 不显示错误消息，使用默认列表
        allOrganisms.value = ['IR64'];
        organismOptions.value = allOrganisms.value;
      } finally {
        loadingOrganisms.value = false;
      }
    };

    // 搜索生物体
    const searchOrganisms = (query) => {
      if (query) {
        organismOptions.value = allOrganisms.value.filter(item =>
          item.toLowerCase().includes(query.toLowerCase())
        );
      } else {
        organismOptions.value = allOrganisms.value;
      }
    };

    // 生物体选择变化
    const handleOrganismChange = async (value) => {
      selectedOrganism.value = value;
      if (value) {
        await fetchCodonData();
      }
    };

    // 获取密码子数据
    const fetchCodonData = async () => {
      if (!selectedOrganism.value) {
        return;
      }

      try {
        loading.value = true;
        error.value = null;
        codonData.value = null;

        // 检查是否是CodonW分析结果
        if (selectedOrganism.value.startsWith('CodonW Analysis (Task:') && selectedOrganism.value.endsWith(')')) {
          // 提取task_id
          const match = selectedOrganism.value.match(/Task:\s*([^)]+)/);
          if (match) {
            const taskId = match[1].trim();
            console.log('检测到CodonW分析结果，任务ID:', taskId);
            const response = await axios.get(`/files/genome-files/codonw_results/${taskId}/`);
            codonData.value = response.data;
          } else {
            throw new Error('无法解析CodonW任务ID');
          }
        } else {
          // 普通生物体，使用原有接口
          const response = await axios.get(`/files/genome-files/get_codon_data/?organism=${selectedOrganism.value}`);
          codonData.value = response.data;
        }
      } catch (err) {
        console.error('获取密码子数据失败:', err);
        const errorMessage = err.response?.data?.error || '网络请求失败';
        error.value = errorMessage;

        // 不显示错误消息，让用户看到友好的无数据提示
        if (!isNoCodonDataError.value) {
          ElMessage.error('获取密码子数据失败');
        }
      } finally {
        loading.value = false;
      }
    };

    // 刷新数据
    const fetchFiles = async () => {
      try {
        loading.value = true;
        await fetchOrganisms();
        if (selectedOrganism.value) {
          await fetchCodonData();
        }
      } catch (error) {
        console.error('刷新数据失败:', error);
      } finally {
        loading.value = false;
      }
    };

    // 计算百分比
    const getPercentage = (count) => {
      if (!codonData.value?.amino_acids) return 0;
      const total = Object.values(codonData.value.amino_acids)
        .reduce((sum, aa) => sum + aa.total_count, 0);
      return total > 0 ? (count / total) * 100 : 0;
    };

    // 判断是否是无密码子数据的错误
    const isNoCodonDataError = computed(() => {
      if (!error.value) return false;
      const errorMsg = error.value.toLowerCase();
      return errorMsg.includes('未找到') &&
             (errorMsg.includes('codon') || errorMsg.includes('密码子') || errorMsg.includes('压缩文件'));
    });

    // 尝试其他生物体
    const tryAnotherOrganism = () => {
      selectedOrganism.value = '';
      error.value = null;
      codonData.value = null;
    };

    // 格式化大数字
    const formatLargeNumber = (num) => {
      if (!num) return 'N/A';
      if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
      } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
      }
      return num.toLocaleString();
    };

    // 选择示例生物体
    const selectExample = (organismId) => {
      selectedOrganism.value = organismId;
      handleOrganismChange(organismId);
    };

    // 计算核苷酸组成数据
    const nucleotideData = computed(() => {
      if (!codonData.value?.statistics) return [];

      const stats = codonData.value.statistics;

      return [
        {
          name: 'T3s',
          percentage: (stats.T3s * 100).toFixed(1),
          color: '#ff6b6b'
        },
        {
          name: 'C3s',
          percentage: (stats.C3s * 100).toFixed(1),
          color: '#4ecdc4'
        },
        {
          name: 'A3s',
          percentage: (stats.A3s * 100).toFixed(1),
          color: '#45b7d1'
        },
        {
          name: 'G3s',
          percentage: (stats.G3s * 100).toFixed(1),
          color: '#96ceb4'
        }
      ];
    });

    // 按使用频率排序的氨基酸数据
    const sortedAminoAcids = computed(() => {
      if (!codonData.value?.amino_acids) return [];

      return Object.values(codonData.value.amino_acids)
        .sort((a, b) => b.total_count - a.total_count); // 按total_count降序排列
    });

    // 切换行展开状态
    const toggleRowExpansion = (row) => {
      const index = expandedRows.value.indexOf(row.name);
      if (index > -1) {
        // 如果已展开，则收起
        expandedRows.value.splice(index, 1);
      } else {
        // 如果未展开，则展开
        expandedRows.value.push(row.name);
      }
    };

    // 获取排序后的密码子列表
    const getSortedCodons = (codons) => {
      if (!codons || !Array.isArray(codons)) return [];

      return [...codons].sort((a, b) => b.count - a.count); // 按count降序排列
    };

    // 处理URL参数
    const handleRouteParams = () => {
      const organism = route.query.organism;
      const taskId = route.query.taskId;
      const source = route.query.source;

      // 如果来自CodonW工具，加载对应的分析结果
      if (taskId && source === 'codonw-tool') {
        loadCodonWResults(taskId);
        return;
      }

      // 原有的organism参数处理
      if (organism && allOrganisms.value.includes(organism)) {
        selectedOrganism.value = organism;
        handleOrganismChange(organism);
      }
    };

    // 加载CodonW分析结果
    const loadCodonWResults = async (taskId) => {
      try {
        loading.value = true;
        error.value = null;

        const response = await axios.get(`/files/genome-files/codonw_results/${taskId}/`);
        const data = response.data;

        // 转换CodonW结果为codon-card格式
        codonData.value = convertCodonWResults(data);
        selectedOrganism.value = `CodonW Analysis (Task: ${taskId})`;

      } catch (err) {
        console.error('加载CodonW结果失败:', err);
        error.value = '加载CodonW分析结果失败';
        ElMessage.error('加载CodonW分析结果失败');
      } finally {
        loading.value = false;
      }
    };

    // 转换CodonW结果为codon-card显示格式
    const convertCodonWResults = (codonwData) => {
      try {
        // 后端已经返回了格式化的数据，直接使用
        return {
          organism: codonwData.organism,
          codon_usage: codonwData.codon_usage,
          amino_acids: codonwData.amino_acids,
          total_codons: codonwData.total_codons,
          nucleotide_composition: codonwData.nucleotide_composition,
          statistics: codonwData.statistics,  // 添加统计数据
          analysis_info: codonwData.analysis_info
        };

      } catch (error) {
        console.error('转换CodonW数据失败:', error);
        return {};
      }
    };

    // 监听路由变化
    watch(() => route.query.organism, (newOrganism) => {
      if (newOrganism && allOrganisms.value.includes(newOrganism)) {
        selectedOrganism.value = newOrganism;
        handleOrganismChange(newOrganism);
      }
    });

    // 监听生物体列表加载完成，然后处理URL参数
    watch(allOrganisms, (newOrganisms) => {
      if (newOrganisms.length > 0) {
        handleRouteParams();
      }
    });

    onMounted(async () => {
      try {
        loading.value = true;
        await fetchOrganisms();
        // 不自动加载数据，让用户看到欢迎页面
      } catch (error) {
        console.error('初始化失败:', error);
      } finally {
        loading.value = false;
      }
    });

    // 上传相关逻辑
    const resultUploadRef = ref(null);
    const uploadUrl = '/gd/api/files/genome-files/codonw_result_upload/';

    // 上传头部信息
    const uploadHeaders = computed(() => {
      const headers = {};
      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
      if (csrfToken) {
        headers['X-CSRFToken'] = csrfToken.value;
      }
      return headers;
    });

    // 上传前检查
    const beforeResultUpload = (file) => {
      const isZip = file.type === 'application/zip' || file.name.toLowerCase().endsWith('.zip');
      if (!isZip) {
        ElMessage.error('只能上传ZIP格式的CodonW结果文件！');
        return false;
      }

      const isLt100M = file.size / 1024 / 1024 < 100;
      if (!isLt100M) {
        ElMessage.error('文件大小不能超过100MB！');
        return false;
      }

      ElMessage.info('正在上传CodonW结果文件...');
      return true;
    };

    // 上传成功处理
    const handleResultUploadSuccess = (response, file) => {
      console.log('上传成功:', response);
      if (response && response.success) {
        ElMessage.success('CodonW结果上传成功！');
        // 解析并显示结果
        if (response.data) {
          codonData.value = response.data;
          selectedOrganism.value = response.organism || t('page.codonCard.uploadedResults');
          error.value = null;
        }
      } else {
        ElMessage.error(response.message || '上传处理失败');
      }
    };

    // 上传失败处理
    const handleResultUploadError = (error, file) => {
      console.error('上传失败:', error);
      ElMessage.error('上传失败，请检查文件格式和网络连接');
    };

    return {
      loading,
      selectedOrganism,
      organismOptions,
      loadingOrganisms,
      codonData,
      error,
      searchOrganisms,
      handleOrganismChange,
      fetchFiles,
      fetchCodonData,
      handleRouteParams,
      getPercentage,
      isNoCodonDataError,
      tryAnotherOrganism,
      formatLargeNumber,
      exampleOrganisms,
      selectExample,
      nucleotideData,
      sortedAminoAcids,
      expandedRows,
      toggleRowExpansion,
      getSortedCodons,
      // 上传相关
      resultUploadRef,
      uploadUrl,
      uploadHeaders,
      beforeResultUpload,
      handleResultUploadSuccess,
      handleResultUploadError
    };
  }
}
</script>


<style scoped>
.codon-card-view {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.title {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #1a56db;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.search-container {
  margin-bottom: 24px;
  display: flex;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
}

.upload-wrapper {
  flex-shrink: 0;
}

.search-wrapper {
  position: relative;
  flex: 1;
  min-width: 300px;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  padding: 0 16px;
  max-width: 500px;
}

.search-icon {
  color: #606266;
  margin-right: 8px;
}

.search-select {
  width: 100%;
}

.data-card {
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  padding: 24px;
}

.loading {
  padding: 20px;
}

.content-container {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.codon-info h3 {
  color: #1a56db;
  margin-bottom: 20px;
  font-size: 20px;
}

/* 统计信息区域 */
.stats-section {
  margin-bottom: 40px;
}

.section-header {
  text-align: center;
  margin-bottom: 40px;
  padding-bottom: 20px;
  border-bottom: 2px solid #f0f2f5;
}

.section-header h4 {
  color: #1a56db;
  margin: 0 0 8px 0;
  font-size: 24px;
  font-weight: 700;
}

.section-subtitle {
  color: #606266;
  font-size: 14px;
  margin: 0;
  font-style: italic;
}

.subsection-title {
  color: #303133;
  margin: 0 0 20px 0;
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e4e7ed;
}

/* 核苷酸组成可视化 */
.nucleotide-composition {
  background: white;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 30px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  border: 1px solid #e4e7ed;
}

.nucleotide-chart {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 30px;
  align-items: center;
}

.nucleotide-bars {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.nucleotide-bar {
  display: flex;
  align-items: center;
  gap: 16px;
}

.nucleotide-info {
  display: flex;
  flex-direction: column;
  min-width: 60px;
}

.nucleotide-name {
  font-weight: 600;
  color: #303133;
  font-size: 14px;
}

.nucleotide-value {
  font-size: 12px;
  color: #909399;
}

.nucleotide-bar-container {
  flex: 1;
  height: 20px;
  background: #f5f7fa;
  border-radius: 10px;
  overflow: hidden;
  position: relative;
}

.nucleotide-bar-fill {
  height: 100%;
  border-radius: 10px;
  transition: width 0.8s ease;
  position: relative;
}

.nucleotide-summary {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  color: white;
}

.gc-content {
  text-align: center;
  width: 100%;
}

.gc-label {
  display: block;
  font-size: 14px;
  margin-bottom: 8px;
  opacity: 0.9;
}

.gc-value {
  display: block;
  font-size: 28px;
  font-weight: bold;
  margin-bottom: 12px;
}

.gc-bar {
  width: 100%;
  height: 8px;
  background: rgba(255,255,255,0.3);
  border-radius: 4px;
  overflow: hidden;
}

.gc-bar-fill {
  height: 100%;
  background: white;
  border-radius: 4px;
  transition: width 0.8s ease;
}

/* 密码子偏好性指标 */
.bias-indicators {
  background: white;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 30px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  border: 1px solid #e4e7ed;
}

.indicators-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
}

.indicator-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  text-align: center;
  transition: all 0.3s ease;
  cursor: help;
  border: 2px solid transparent;
  position: relative;
  overflow: hidden;
}

.indicator-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  transition: all 0.3s ease;
}

.cai-card {
  border-color: #e8f4fd;
  background: linear-gradient(135deg, #f8fbff 0%, #e8f4fd 100%);
}

.cai-card::before {
  background: linear-gradient(90deg, #1890ff, #40a9ff);
}

.cbi-card {
  border-color: #f0f9e8;
  background: linear-gradient(135deg, #f9fff6 0%, #f0f9e8 100%);
}

.cbi-card::before {
  background: linear-gradient(90deg, #52c41a, #73d13d);
}

.fop-card {
  border-color: #fff7e6;
  background: linear-gradient(135deg, #fffbf0 0%, #fff7e6 100%);
}

.fop-card::before {
  background: linear-gradient(90deg, #fa8c16, #ffa940);
}

.nc-card {
  border-color: #f9f0ff;
  background: linear-gradient(135deg, #fefbff 0%, #f9f0ff 100%);
}

.nc-card::before {
  background: linear-gradient(90deg, #722ed1, #9254de);
}

.indicator-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.12);
}

.indicator-header {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.indicator-name {
  font-size: 18px;
  font-weight: bold;
  color: #303133;
}

.indicator-value {
  font-size: 32px;
  font-weight: 700;
  color: #1a56db;
  margin-bottom: 8px;
  line-height: 1;
}

.indicator-description {
  font-size: 12px;
  color: #606266;
  margin-bottom: 16px;
}

.indicator-progress {
  width: 100%;
  height: 6px;
  background: rgba(0,0,0,0.1);
  border-radius: 3px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  border-radius: 3px;
  transition: width 0.8s ease;
}

.cai-progress {
  background: linear-gradient(90deg, #1890ff, #40a9ff);
}

.cbi-progress {
  background: linear-gradient(90deg, #52c41a, #73d13d);
}

.fop-progress {
  background: linear-gradient(90deg, #fa8c16, #ffa940);
}

.nc-progress {
  background: linear-gradient(90deg, #722ed1, #9254de);
}

/* 其他统计指标 */
.additional-stats {
  background: white;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 30px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  border: 1px solid #e4e7ed;
}

.stats-compact-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 16px;
}

.compact-stat-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
  text-align: center;
  border: 1px solid #e9ecef;
  transition: all 0.2s ease;
  cursor: help;
  position: relative;
}

.compact-stat-card:hover {
  background: #e9ecef;
  transform: translateY(-2px);
  border-color: #1a56db;
  box-shadow: 0 4px 12px rgba(26, 86, 219, 0.15);
}

.compact-stat-label {
  font-size: 12px;
  color: #606266;
  margin-bottom: 8px;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.compact-stat-value {
  font-size: 18px;
  font-weight: bold;
  color: #1a56db;
}

.help-icon-small {
  color: #909399;
  font-size: 12px;
  opacity: 0.6;
  transition: all 0.2s ease;
}

.compact-stat-card:hover .help-icon-small {
  color: #1a56db;
  opacity: 1;
}

/* Tooltip样式 */
.tooltip-content {
  max-width: 300px;
  line-height: 1.5;
  font-size: 13px;
}

.tooltip-content strong {
  color: #409eff;
  display: block;
  margin-bottom: 6px;
}

.tooltip-content em {
  color: #67c23a;
  font-style: normal;
  font-size: 12px;
  display: block;
  margin-top: 6px;
}

.help-icon {
  color: #909399;
  font-size: 16px;
  opacity: 0.7;
  transition: all 0.2s ease;
}

.indicator-card:hover .help-icon {
  color: #1a56db;
  opacity: 1;
}

.amino-acids-section h4 {
  color: #303133;
  margin-bottom: 15px;
  font-size: 16px;
}

/* 自定义氨基酸表格样式 */
.custom-amino-acid-table {
  background: white;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #e4e7ed;
}

.table-header {
  display: flex;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
  font-weight: 600;
  color: #606266;
  font-size: 14px;
}

.header-cell {
  padding: 12px 16px;
  border-right: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: center;
}

.header-cell:last-child {
  border-right: none;
}

.expand-cell {
  width: 50px;
  flex-shrink: 0;
}

.name-cell {
  width: 100px;
  flex-shrink: 0;
}

.count-cell {
  width: 150px;
  flex-shrink: 0;
}

.codon-count-cell {
  width: 120px;
  flex-shrink: 0;
}

.frequency-cell {
  flex: 1;
  min-width: 200px;
}

.table-body {
  max-height: 600px;
  overflow-y: auto;
}

.amino-acid-row-group {
  border-bottom: 1px solid #e4e7ed;
}

.amino-acid-row-group:last-child {
  border-bottom: none;
}

.amino-acid-row {
  display: flex;
  cursor: pointer;
  transition: all 0.2s ease;
  background: white;
}

.amino-acid-row:hover {
  background: #f5f7fa;
}

.amino-acid-row.expanded {
  background: #e8f4fd;
}

.row-cell {
  padding: 12px 16px;
  border-right: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: center;
}

.row-cell:last-child {
  border-right: none;
}

.expand-icon {
  transition: transform 0.2s ease;
  color: #909399;
}

.expand-icon.expanded {
  transform: rotate(90deg);
  color: #1a56db;
}

.expand-content {
  background: #fafbfc;
  border-top: 1px solid #e4e7ed;
  padding: 20px;
}

.expand-header h5 {
  color: #1a56db;
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: 600;
}

.codon-details-table {
  background: white;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid #e4e7ed;
}

.codon-header {
  display: flex;
  background: #f8f9fa;
  border-bottom: 1px solid #e4e7ed;
  font-weight: 600;
  color: #606266;
  font-size: 13px;
}

.codon-header-cell {
  flex: 1;
  padding: 10px 12px;
  text-align: center;
  border-right: 1px solid #e4e7ed;
}

.codon-header-cell:last-child {
  border-right: none;
}

.codon-header-cell .tooltip-trigger {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  cursor: help;
}

.codon-header-cell .help-icon-small {
  color: #909399;
  font-size: 12px;
  opacity: 0.6;
  transition: all 0.2s ease;
}

.codon-header-cell:hover .help-icon-small {
  color: #1a56db;
  opacity: 1;
}

.codon-row {
  display: flex;
  border-bottom: 1px solid #f0f2f5;
}

.codon-row:last-child {
  border-bottom: none;
}

.codon-row:hover {
  background: #f5f7fa;
}

.codon-cell {
  flex: 1;
  padding: 8px 12px;
  text-align: center;
  font-size: 13px;
  color: #606266;
  border-right: 1px solid #f0f2f5;
}

.codon-cell:last-child {
  border-right: none;
}

.codon-cell:first-child {
  font-weight: 600;
  color: #303133;
}

.expand-content {
  padding: 20px;
  background-color: #fafafa;
  border-radius: 4px;
}

.expand-content h5 {
  margin: 0 0 15px 0;
  color: #1a56db;
  font-size: 14px;
}

.frequency-bar {
  position: relative;
  width: 100%;
  height: 20px;
  background-color: #e4e7ed;
  border-radius: 10px;
  overflow: hidden;
}

.frequency-fill {
  height: 100%;
  background: linear-gradient(90deg, #409eff, #67c23a);
  transition: width 0.3s ease;
}

.frequency-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 12px;
  font-weight: bold;
  color: #303133;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: bold;
  font-size: 16px;
}

.stats-overview .stat-card {
  text-align: center;
  padding: 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 8px;
  box-shadow: 0 4px 8px rgba(0,0,0,0.1);
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  margin-bottom: 8px;
}

.stat-label {
  font-size: 14px;
  opacity: 0.9;
}

.expand-content {
  padding: 20px;
  background-color: #fafafa;
  border-radius: 4px;
}

.frequency-bar {
  position: relative;
  width: 100%;
  height: 20px;
  background-color: #e4e7ed;
  border-radius: 10px;
  overflow: hidden;
}

.frequency-fill {
  height: 100%;
  background: linear-gradient(90deg, #409eff, #67c23a);
  transition: width 0.3s ease;
}

.frequency-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 12px;
  font-weight: bold;
  color: #303133;
}

.el-card {
  margin-bottom: 20px;
}

.el-card:last-child {
  margin-bottom: 0;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .codon-card {
    padding: 10px;
  }

  .page-header {
    flex-direction: column;
    gap: 15px;
  }

  .stats-overview .el-col {
    margin-bottom: 15px;
  }

  #codon-heatmap, #amino-acid-chart {
    height: 300px !important;
  }
}

/* 表格样式优化 */
.el-table {
  border-radius: 8px;
  overflow: hidden;
}

.el-table .el-table__header-wrapper th {
  background-color: #f8f9fa;
  color: #495057;
  font-weight: 600;
}

.el-table .el-table__row:hover > td {
  background-color: #f5f7fa;
}

/* 标签样式 */
.el-tag {
  font-weight: bold;
  border-radius: 4px;
}

/* 按钮样式 */
.el-button {
  border-radius: 6px;
}

/* 加载动画 */
.is-loading {
  animation: rotating 2s linear infinite;
}

@keyframes rotating {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

/* 欢迎页面样式 */
.welcome-container {
  padding: 40px 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.welcome-content {
  text-align: center;
}

.welcome-header {
  margin-bottom: 50px;
}

.welcome-icon {
  font-size: 80px;
  margin-bottom: 20px;
  opacity: 0.8;
}

.welcome-header h2 {
  color: #1a56db;
  font-size: 32px;
  font-weight: 600;
  margin-bottom: 12px;
}

.welcome-subtitle {
  color: #606266;
  font-size: 18px;
  margin: 0;
  line-height: 1.6;
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 24px;
  margin-bottom: 50px;
}

.feature-card {
  background: white;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  padding: 30px 20px;
  text-align: center;
  transition: all 0.3s ease;
  box-shadow: 0 2px 4px rgba(0,0,0,0.04);
}

.feature-card:hover {
  border-color: #1a56db;
  box-shadow: 0 8px 24px rgba(26, 86, 219, 0.12);
  transform: translateY(-4px);
}

.feature-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.8;
}

.feature-card h4 {
  color: #303133;
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 12px;
}

.feature-card p {
  color: #606266;
  font-size: 14px;
  line-height: 1.6;
  margin: 0;
}

.usage-guide {
  background: #f8f9fa;
  border-radius: 12px;
  padding: 30px;
  margin-bottom: 40px;
  text-align: left;
  max-width: 600px;
  margin-left: auto;
  margin-right: auto;
  margin-bottom: 40px;
}

.usage-guide h3 {
  color: #1a56db;
  font-size: 20px;
  margin-bottom: 20px;
  text-align: center;
}

.guide-steps {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.step {
  display: flex;
  align-items: center;
  gap: 16px;
}

.step-number {
  background: #1a56db;
  color: white;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 14px;
  flex-shrink: 0;
}

.step-text {
  color: #606266;
  font-size: 15px;
  line-height: 1.5;
}

.example-section {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  padding: 30px;
  color: white;
}

.example-section h3 {
  color: white;
  font-size: 20px;
  margin-bottom: 12px;
}

.example-section p {
  color: rgba(255,255,255,0.9);
  font-size: 15px;
  margin-bottom: 20px;
}

.example-organisms {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: center;
}

.example-organisms .el-button {
  background: rgba(255,255,255,0.2);
  border-color: rgba(255,255,255,0.3);
  color: white;
}

.example-organisms .el-button:hover {
  background: rgba(255,255,255,0.3);
  border-color: rgba(255,255,255,0.5);
  color: white;
}

/* 无数据状态样式 */
.no-data-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
  padding: 40px;
}

.no-codon-data, .no-selection {
  text-align: center;
  max-width: 500px;
}

.no-data-icon {
  font-size: 64px;
  margin-bottom: 20px;
  opacity: 0.6;
}

.no-codon-data h3, .no-selection h3 {
  color: #606266;
  font-size: 24px;
  margin-bottom: 16px;
  font-weight: 500;
}

.no-data-message {
  color: #909399;
  font-size: 16px;
  line-height: 1.6;
  margin-bottom: 24px;
}

.no-data-details {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 24px;
  text-align: left;
}

.no-data-details p {
  color: #606266;
  font-weight: 500;
  margin-bottom: 12px;
}

.no-data-details ul {
  color: #909399;
  padding-left: 20px;
  margin: 0;
}

.no-data-details li {
  margin-bottom: 8px;
  line-height: 1.5;
}

.no-data-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
}

.error-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  text-align: center;
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .nucleotide-chart {
    grid-template-columns: 1fr;
    gap: 20px;
  }

  .indicators-grid {
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
  }

  .stats-compact-grid {
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  }
}

@media (max-width: 768px) {
  .section-header h4 {
    font-size: 20px;
  }

  .nucleotide-composition,
  .bias-indicators,
  .additional-stats {
    padding: 16px;
    margin-bottom: 20px;
  }

  .nucleotide-bars {
    gap: 8px;
  }

  .nucleotide-bar {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .nucleotide-info {
    min-width: auto;
    flex-direction: row;
    gap: 8px;
  }

  .indicators-grid {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .indicator-card {
    padding: 16px;
  }

  .indicator-value {
    font-size: 24px;
  }

  .stats-compact-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }

  .compact-stat-card {
    padding: 12px;
  }

  .compact-stat-value {
    font-size: 16px;
  }

  /* 自定义表格响应式 */
  .custom-amino-acid-table {
    overflow-x: auto;
  }

  .table-header,
  .amino-acid-row {
    min-width: 600px;
  }

  .expand-content {
    padding: 12px;
  }

  .codon-details-table {
    overflow-x: auto;
  }

  .codon-header,
  .codon-row {
    min-width: 400px;
  }

  /* 欢迎页面响应式 */
  .welcome-container {
    padding: 20px 10px;
  }

  .welcome-header h2 {
    font-size: 24px;
  }

  .welcome-subtitle {
    font-size: 16px;
  }

  .welcome-icon {
    font-size: 60px;
  }

  .feature-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .feature-card {
    padding: 20px 16px;
  }

  .feature-icon {
    font-size: 36px;
  }

  .usage-guide {
    padding: 20px;
    margin-bottom: 30px;
  }

  .guide-steps {
    gap: 12px;
  }

  .step {
    flex-direction: column;
    text-align: center;
    gap: 8px;
  }

  .example-section {
    padding: 20px;
  }

  .example-organisms {
    flex-direction: column;
    align-items: center;
  }

  .example-organisms .el-button {
    width: 200px;
  }

  .no-data-actions {
    flex-direction: column;
  }

  .no-data-actions .el-button {
    width: 100%;
  }
}
</style>
