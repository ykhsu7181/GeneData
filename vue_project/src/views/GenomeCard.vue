<template>
  <div class="genome-card-view">
    <div class="page-header">
      <h2 class="title">Genome</h2>
      <div class="header-actions">
        <el-tooltip :content="$t('page.genomeCard.refreshData')" placement="top">
          <el-button circle size="small" @click="fetchFiles">
            <el-icon><Refresh /></el-icon>
          </el-button>
        </el-tooltip>
      </div>
    </div>
    
    <!-- 搜索框 -->
    <div class="search-container">
      <div class="search-wrapper">
        <el-icon class="search-icon"><Search /></el-icon>
        <el-select
          v-model="selectedOrganism"
          filterable
          remote
          :placeholder="$t('page.genomeCard.searchPlaceholder')"
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
        
        <div class="divider"></div>
        
        <!-- 染色体选择框 -->
        <div class="chromosome-select">
          <span class="select-label">{{ $t('page.genomeCard.chromosome') }}</span>
          <el-select
            v-model="selectedChromosome"
          :placeholder="$t('page.genomeCard.selectChromosome')"
          class="chromosome-dropdown"
          :loading="loadingChromosomes"
          clearable
          >
            <el-option
              v-for="item in chromosomeOptions"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
        </div>
      </div>
    </div>
    
    <div class="data-card">
      <div v-if="loading" class="loading">
        <el-skeleton :rows="6" animated />
      </div>
      
      <div v-else class="content-container">
        <div class="visualization-container">
          <!-- 控制面板 -->
          <div class="control-panel">
            <div class="display-title">display</div>
            <el-checkbox v-model="displayTEs" :label="'TEs'" size="small" checked>
              <span class="checkbox-color te-color"></span> TEs
            </el-checkbox>
            <el-checkbox v-model="displayCentromere" :label="'Centromere'" size="small">
              <span class="checkbox-color centromere-color"></span> Centromere
            </el-checkbox>
            <el-checkbox v-model="displayRRNA" :label="'rRNA'" size="small">
              <span class="checkbox-color rrna-color"></span> rRNA
            </el-checkbox>
            <el-checkbox v-model="displayMiRNA" :label="'miRNA'" size="small">
              <span class="checkbox-color mirna-color"></span> miRNA
            </el-checkbox>
            <el-checkbox v-model="displayTRNA" :label="'tRNA'" size="small">
              <span class="checkbox-color trna-color"></span> tRNA
            </el-checkbox>
            <el-checkbox v-model="displayCoreBlocks" :label="'CoreBlocks'" size="small">
              <span class="checkbox-color coreblocks-color"></span> CoreBlocks
            </el-checkbox>

            <!-- 设置按钮 -->
            <div class="settings-section">
              <el-popover
                placement="bottom-end"
                :width="300"
                trigger="click"
                v-model:visible="showSettings"
              >
                <template #reference>
                  <el-button size="small" circle>
                    <el-icon><Setting /></el-icon>
                  </el-button>
                </template>

                <div class="settings-panel">
                  <div class="setting-item">
                    <label>每行长度 (Mb):</label>
                    <el-input-number
                      v-model="segmentLengthMb"
                      :min="0.1"
                      :max="50"
                      :step="0.1"
                      :precision="1"
                      size="small"
                      @change="handleSegmentLengthChange"
                    />
                  </div>

                  <div class="setting-item">
                    <el-button size="small" type="primary" @click="downloadVisualization">
                      <el-icon><Download /></el-icon>
                      下载图片
                    </el-button>
                  </div>
                </div>
              </el-popover>
            </div>
          </div>

          <!-- 染色体可视化区域 -->
          <div class="chromosome-visualization">
            <div v-if="loadingVisualization" class="loading-visualization">
              <div class="loading-content">
                <el-icon class="is-loading"><Loading /></el-icon>
                <span>正在加载可视化数据...</span>
              </div>
            </div>
            <div v-else-if="!selectedOrganism || !selectedChromosome" class="empty-state">
              <el-empty description="请选择生物体和染色体以查看可视化" />
            </div>
            <div v-else ref="chromosomeContainer" class="chromosome-container"></div>

          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, computed, watch } from 'vue';
import * as d3 from 'd3';
import axios from 'axios';
import { ElMessage } from 'element-plus';
import { Search, Refresh, Loading, Setting, Download } from '@element-plus/icons-vue';
import { useRoute, useRouter } from 'vue-router';

const normalizeQueryValue = (value) => {
  if (Array.isArray(value)) {
    return value[0] || '';
  }
  return value ? String(value).trim() : '';
};

export default {
  name: 'GenomeCard',
  components: {
    Search,
    Refresh,
    Loading,
    Setting,
    Download
  },
  setup() {
    const route = useRoute();
    const router = useRouter();
    const loading = ref(true);
    const selectedOrganism = ref('');
    const organismOptions = ref([]);
    const loadingOrganisms = ref(false);
    const allOrganisms = ref([]);
    const contextAccession = ref('');
    const contextAssemblyId = ref('');
    const routeSyncInProgress = ref(false);
    
    // 染色体相关数据
    const selectedChromosome = ref('');
    const chromosomeOptions = ref([]);
    const loadingChromosomes = ref(false);
    // 可视化相关数据
    const displayTEs = ref(true);
    const displayCentromere = ref(false);
    const displayRRNA = ref(false);
    const displayMiRNA = ref(false);
    const displayTRNA = ref(false);
    const displayCoreBlocks = ref(false);
    const loadingVisualization = ref(false);
    const chromosomeContainer = ref(null);

    // 可视化数据
    const tesData = ref([]);
    const centromereData = ref([]);
    const rRNAData = ref([]);
    const miRNAData = ref([]);
    const tRNAData = ref([]);
    const coreBlocksData = ref([]);
    const chromosomeLength = ref(0);

    // 可视化设置
    const segmentLength = ref(5000000); // 每行显示的长度，默认5Mb
    const showSettings = ref(false);

    // 计算属性：以Mb为单位的分段长度
    const segmentLengthMb = computed({
      get: () => Math.round(segmentLength.value / 1000000 * 10) / 10, // 保留一位小数
      set: (value) => {
        segmentLength.value = Math.round(value * 1000000); // 转换为bp并四舍五入
      }
    });

    const buildNormalizedQuery = ({ accession, assembly }) => {
      const query = {};
      if (accession) {
        query.accession = accession;
      }
      if (assembly) {
        query.assembly = String(assembly);
      }
      return query;
    };

    const replaceRouteQuery = async (query) => {
      const currentAccession = normalizeQueryValue(route.query.accession);
      const currentAssembly = normalizeQueryValue(route.query.assembly);
      const targetAccession = normalizeQueryValue(query.accession);
      const targetAssembly = normalizeQueryValue(query.assembly);
      const routeHasLegacyOrganism = Boolean(normalizeQueryValue(route.query.organism));

      if (
        currentAccession === targetAccession &&
        currentAssembly === targetAssembly &&
        !routeHasLegacyOrganism
      ) {
        return;
      }

      routeSyncInProgress.value = true;
      try {
        await router.replace({
          path: route.path,
          query
        });
      } finally {
        routeSyncInProgress.value = false;
      }
    };

    const buildGenomeContextParams = ({ includeOrganismFallback = false } = {}) => {
      const params = {};

      if (contextAssemblyId.value) {
        params.assembly_id = contextAssemblyId.value;
      }
      if (contextAccession.value) {
        params.accession = contextAccession.value;
      }
      if (!contextAssemblyId.value && !contextAccession.value && selectedOrganism.value) {
        params.organism = selectedOrganism.value;
      } else if (includeOrganismFallback && selectedOrganism.value) {
        params.organism = selectedOrganism.value;
      }

      return params;
    };

    // 处理分段长度变化
    const handleSegmentLengthChange = () => {
      if (selectedOrganism.value && selectedChromosome.value) {
        drawChromosomeVisualization();
      }
    };

    // 下载可视化图片
    const downloadVisualization = () => {
      const svg = d3.select(chromosomeContainer.value).select('svg');
      if (svg.empty()) {
        ElMessage.warning('没有可下载的图片');
        return;
      }

      try {
        // 获取SVG元素
        const svgElement = svg.node();
        const serializer = new XMLSerializer();
        const svgString = serializer.serializeToString(svgElement);

        // 创建下载链接
        const blob = new Blob([svgString], { type: 'image/svg+xml' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${selectedOrganism.value}_${selectedChromosome.value}_visualization.svg`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);

        ElMessage.success('图片下载成功');
      } catch (error) {
        console.error('下载失败:', error);
        ElMessage.error('下载失败');
      }
    };

    // 获取TEs数据
    const fetchTEsData = async (organism, chromosome) => {
      try {
        const response = await axios.get('/files/query/tes/', {
          params: {
            ...buildGenomeContextParams({ includeOrganismFallback: true }),
            chromosome
          }
        });
        tesData.value = response.data || [];
      } catch (error) {
        console.error('获取TEs数据失败:', error);
        tesData.value = [];
      }
    };

    // 获取centromere数据
    const fetchCentromereData = async (organism, chromosome) => {
      try {
        const response = await axios.get('/files/query/centromere/', {
          params: {
            ...buildGenomeContextParams({ includeOrganismFallback: true }),
            chromosome
          }
        });
        centromereData.value = response.data || [];
      } catch (error) {
        console.error('获取centromere数据失败:', error);
        centromereData.value = [];
      }
    };

    // 获取RNA数据的通用函数
    const fetchRNAData = async (organism, chromosome, rnaType) => {
      try {
        const response = await axios.get('/files/query/rna-data/', {
          params: {
            ...buildGenomeContextParams({ includeOrganismFallback: true }),
            chromosome,
            type: rnaType
          }
        });
        return response.data || [];
      } catch (error) {
        console.error(`获取${rnaType}数据失败:`, error);
        return [];
      }
    };

    // 获取rRNA数据
    const fetchRRNAData = async (organism, chromosome) => {
      rRNAData.value = await fetchRNAData(organism, chromosome, 'rRNA');
    };

    // 获取miRNA数据
    const fetchMiRNAData = async (organism, chromosome) => {
      miRNAData.value = await fetchRNAData(organism, chromosome, 'miRNA');
    };

    // 获取tRNA数据
    const fetchTRNAData = async (organism, chromosome) => {
      tRNAData.value = await fetchRNAData(organism, chromosome, 'tRNA');
    };

    // 获取coreBlocks数据
    const fetchCoreBlocksData = async (organism, chromosome) => {
      try {
        const response = await axios.get('/files/query/core-blocks/', {
          params: {
            ...buildGenomeContextParams({ includeOrganismFallback: true }),
            chromosome
          }
        });
        coreBlocksData.value = response.data || [];
      } catch (error) {
        console.error('获取coreBlocks数据失败:', error);
        coreBlocksData.value = [];
      }
    };

    // 获取染色体长度
    const getChromosomeLength = async (organism, chromosome) => {
      try {
        const response = await axios.get('/files/query/chromosome-length/', {
          params: {
            ...buildGenomeContextParams(),
            chromosome
          }
        });
        chromosomeLength.value = Number(response.data?.length) || 50000000;
      } catch (error) {
        console.error('获取染色体长度失败:', error);
        chromosomeLength.value = 50000000;
      }
    };

    // 绘制染色体可视化
    const drawChromosomeVisualization = () => {
      if (!chromosomeContainer.value || !selectedOrganism.value || !selectedChromosome.value) {
        return;
      }

      // 清除之前的内容
      d3.select(chromosomeContainer.value).selectAll("*").remove();

      const container = d3.select(chromosomeContainer.value);
      const containerRect = chromosomeContainer.value.getBoundingClientRect();
      const width = Math.max(800, containerRect.width);

      // 计算实际的染色体长度（基于数据）
      let maxPosition = chromosomeLength.value;
      if (tesData.value && tesData.value.length > 0) {
        try {
          const maxTE = Math.max(...tesData.value.map(d => d.end));
          maxPosition = Math.max(maxPosition, maxTE);
        } catch (e) {
          console.warn('计算TEs最大位置失败:', e);
        }
      }
      if (centromereData.value && centromereData.value.length > 0) {
        try {
          const maxCentromere = Math.max(...centromereData.value.map(d => d.end));
          maxPosition = Math.max(maxPosition, maxCentromere);
        } catch (e) {
          console.warn('计算centromere最大位置失败:', e);
        }
      }

      // 计算RNA数据的最大位置
      [rRNAData.value, miRNAData.value, tRNAData.value].forEach((rnaData, index) => {
        const rnaTypes = ['rRNA', 'miRNA', 'tRNA'];
        if (rnaData && rnaData.length > 0) {
          try {
            const maxRNA = Math.max(...rnaData.map(d => d.end));
            maxPosition = Math.max(maxPosition, maxRNA);
          } catch (e) {
            console.warn(`计算${rnaTypes[index]}最大位置失败:`, e);
          }
        }
      });

      // 计算coreBlocks数据的最大位置
      if (coreBlocksData.value && coreBlocksData.value.length > 0) {
        try {
          const maxCoreBlocks = Math.max(...coreBlocksData.value.map(d => d.end));
          maxPosition = Math.max(maxPosition, maxCoreBlocks);
        } catch (e) {
          console.warn('计算coreBlocks最大位置失败:', e);
        }
      }

      // 计算分段参数
      const segmentLen = segmentLength.value;
      const numSegments = Math.ceil(maxPosition / segmentLen);
      const margin = { top: 50, right: 50, bottom: 50, left: 50 }; // 减少左边距
      const segmentWidth = width - margin.left - margin.right;
      const segmentHeight = 20;
      const segmentSpacing = 80; // 每行之间的间距，增加以容纳RNA元素
      const height = margin.top + margin.bottom + numSegments * (segmentHeight + segmentSpacing);

      console.log(`可视化参数: 染色体长度=${maxPosition}, 分段长度=${segmentLen}, 分段数=${numSegments}`);

      const svg = container.append("svg")
        .attr("width", width)
        .attr("height", height)
        .style("background", "#fafafa");

      // 为每个分段创建比例尺和绘制染色体
      for (let i = 0; i < numSegments; i++) {
        const segmentStart = i * segmentLen;
        const segmentEnd = Math.min((i + 1) * segmentLen, maxPosition);
        const segmentY = margin.top + i * (segmentHeight + segmentSpacing);

        console.log(`分段 ${i}: ${segmentStart}-${segmentEnd}, Y=${segmentY}`);

        // 创建该分段的比例尺
        const xScale = d3.scaleLinear()
          .domain([segmentStart, segmentEnd])
          .range([margin.left, margin.left + segmentWidth]);

        // 绘制染色体分段主体
        svg.append("rect")
          .attr("x", margin.left)
          .attr("y", segmentY)
          .attr("width", segmentWidth)
          .attr("height", segmentHeight)
          .attr("fill", "#e8e8e8")
          .attr("stroke", "#ccc")
          .attr("stroke-width", 1)
          .attr("rx", 10);



        // 绘制该分段的TEs
        if (displayTEs.value && tesData.value.length > 0) {
          const segmentTEs = tesData.value.filter(d =>
            // 检查TEs是否与当前分段有重叠
            d.start < segmentEnd && d.end > segmentStart
          );

          svg.selectAll(`.te-element-${i}`)
            .data(segmentTEs)
            .enter()
            .append("rect")
            .attr("class", `te-element te-element-${i}`)
            .attr("x", d => xScale(Math.max(d.start, segmentStart)))
            .attr("y", segmentY + 2)
            .attr("width", d => Math.max(2, xScale(Math.min(d.end, segmentEnd)) - xScale(Math.max(d.start, segmentStart))))
            .attr("height", segmentHeight - 4)
            .attr("fill", "#1a56db")
            .attr("opacity", 0.8)
            .style("cursor", "pointer");
        }

        // 绘制该分段的centromere
        if (displayCentromere.value && centromereData.value.length > 0) {
          const segmentCentromeres = centromereData.value.filter(d =>
            // 检查centromere是否与当前分段有重叠
            d.start < segmentEnd && d.end > segmentStart
          );

          svg.selectAll(`.centromere-element-${i}`)
            .data(segmentCentromeres)
            .enter()
            .append("rect")
            .attr("class", `centromere-element centromere-element-${i}`)
            .attr("x", d => xScale(Math.max(d.start, segmentStart)))
            .attr("y", segmentY - 3)
            .attr("width", d => Math.max(3, xScale(Math.min(d.end, segmentEnd)) - xScale(Math.max(d.start, segmentStart))))
            .attr("height", segmentHeight + 6)
            .attr("fill", "#f56c6c")
            .attr("opacity", 0.9)
            .style("cursor", "pointer");
        }

        // 绘制该分段的rRNA
        if (displayRRNA.value && rRNAData.value.length > 0) {
          const segmentRRNAs = rRNAData.value.filter(d =>
            d.start < segmentEnd && d.end > segmentStart
          );

          svg.selectAll(`.rrna-element-${i}`)
            .data(segmentRRNAs)
            .enter()
            .append("rect")
            .attr("class", `rrna-element rrna-element-${i}`)
            .attr("x", d => xScale(Math.max(d.start, segmentStart)))
            .attr("y", segmentY + segmentHeight + 2)
            .attr("width", d => Math.max(2, xScale(Math.min(d.end, segmentEnd)) - xScale(Math.max(d.start, segmentStart))))
            .attr("height", 4)
            .attr("fill", "#67c23a")
            .attr("opacity", 0.8)
            .style("cursor", "pointer");
        }

        // 绘制该分段的miRNA
        if (displayMiRNA.value && miRNAData.value.length > 0) {
          const segmentMiRNAs = miRNAData.value.filter(d =>
            d.start < segmentEnd && d.end > segmentStart
          );

          svg.selectAll(`.mirna-element-${i}`)
            .data(segmentMiRNAs)
            .enter()
            .append("rect")
            .attr("class", `mirna-element mirna-element-${i}`)
            .attr("x", d => xScale(Math.max(d.start, segmentStart)))
            .attr("y", segmentY + segmentHeight + 8)
            .attr("width", d => Math.max(2, xScale(Math.min(d.end, segmentEnd)) - xScale(Math.max(d.start, segmentStart))))
            .attr("height", 4)
            .attr("fill", "#e6a23c")
            .attr("opacity", 0.8)
            .style("cursor", "pointer");
        }

        // 绘制该分段的tRNA
        if (displayTRNA.value && tRNAData.value.length > 0) {
          const segmentTRNAs = tRNAData.value.filter(d =>
            d.start < segmentEnd && d.end > segmentStart
          );

          svg.selectAll(`.trna-element-${i}`)
            .data(segmentTRNAs)
            .enter()
            .append("rect")
            .attr("class", `trna-element trna-element-${i}`)
            .attr("x", d => xScale(Math.max(d.start, segmentStart)))
            .attr("y", segmentY + segmentHeight + 14)
            .attr("width", d => Math.max(2, xScale(Math.min(d.end, segmentEnd)) - xScale(Math.max(d.start, segmentStart))))
            .attr("height", 4)
            .attr("fill", "#909399")
            .attr("opacity", 0.8)
            .style("cursor", "pointer");
        }

        // 绘制该分段的coreBlocks
        if (displayCoreBlocks.value && coreBlocksData.value.length > 0) {
          const segmentCoreBlocks = coreBlocksData.value.filter(d =>
            d.start < segmentEnd && d.end > segmentStart
          );

          svg.selectAll(`.coreblocks-element-${i}`)
            .data(segmentCoreBlocks)
            .enter()
            .append("rect")
            .attr("class", `coreblocks-element coreblocks-element-${i}`)
            .attr("x", d => xScale(Math.max(d.start, segmentStart)))
            .attr("y", segmentY + segmentHeight + 20)
            .attr("width", d => Math.max(2, xScale(Math.min(d.end, segmentEnd)) - xScale(Math.max(d.start, segmentStart))))
            .attr("height", 6)
            .attr("fill", "#722ed1")
            .attr("opacity", 0.8)
            .style("cursor", "pointer");
        }

        // 添加该分段的比例尺
        const tickCount = 5;
        const tickValues = [];
        for (let j = 0; j <= tickCount; j++) {
          const tickPos = segmentStart + (segmentEnd - segmentStart) * j / tickCount;
          if (tickPos <= segmentEnd) {
            tickValues.push(tickPos);
          }
        }

        // 添加刻度线
        svg.selectAll(`.tick-line-${i}`)
          .data(tickValues)
          .enter()
          .append("line")
          .attr("class", `tick-line tick-line-${i}`)
          .attr("x1", d => xScale(d))
          .attr("x2", d => xScale(d))
          .attr("y1", segmentY + segmentHeight + 5)
          .attr("y2", segmentY + segmentHeight + 10)
          .attr("stroke", "#666")
          .attr("stroke-width", 1);

        // 添加刻度标签
        svg.selectAll(`.tick-label-${i}`)
          .data(tickValues)
          .enter()
          .append("text")
          .attr("class", `tick-label tick-label-${i}`)
          .attr("x", d => xScale(d))
          .attr("y", segmentY + segmentHeight + 25)
          .attr("text-anchor", "middle")
          .attr("font-size", "9px")
          .attr("fill", "#666")
          .text(d => {
            if (d >= 1000000) {
              return (d / 1000000).toFixed(1) + 'M';
            } else if (d >= 1000) {
              return (d / 1000).toFixed(0) + 'K';
            } else {
              return d.toString();
            }
          });
      }

      // 创建tooltip div
      let tooltip = d3.select("body").select(".chromosome-tooltip");
      if (tooltip.empty()) {
        tooltip = d3.select("body").append("div")
          .attr("class", "chromosome-tooltip")
          .style("position", "absolute")
          .style("background", "rgba(0, 0, 0, 0.8)")
          .style("color", "white")
          .style("padding", "8px 12px")
          .style("border-radius", "4px")
          .style("font-size", "12px")
          .style("pointer-events", "none")
          .style("opacity", 0)
          .style("z-index", 1000)
          .style("max-width", "300px");
      }

      // 添加tooltip事件处理
      svg.selectAll(".te-element")
        .on("mouseover", function(event, d) {
          tooltip.style("opacity", 1)
            .style("left", (event.pageX + 10) + "px")
            .style("top", (event.pageY - 10) + "px")
            .html(`
              <div style="font-weight: bold; margin-bottom: 5px; padding-bottom: 5px; border-bottom: 1px solid rgba(255, 255, 255, 0.3);">TE Element</div>
              <div><strong>SeqID:</strong> ${d.seqid}</div>
              <div><strong>Start:</strong> ${d.start.toLocaleString()}</div>
              <div><strong>End:</strong> ${d.end.toLocaleString()}</div>
              <div><strong>Length:</strong> ${(d.end - d.start).toLocaleString()} bp</div>
              <div><strong>Sequence Ontology:</strong> ${d.sequence_ontology}</div>
              <div><strong>Score:</strong> ${d.score}</div>
              <div><strong>Strand:</strong> ${d.strand}</div>
              <div><strong>Phase:</strong> ${d.phase}</div>
              ${d.attributes.Classification ? `<div><strong>Classification:</strong> ${d.attributes.Classification}</div>` : ''}
              ${d.attributes.Identity ? `<div><strong>Identity:</strong> ${d.attributes.Identity}</div>` : ''}
            `);
        })
        .on("mouseout", function() {
          tooltip.style("opacity", 0);
        });

      svg.selectAll(".centromere-element")
        .on("mouseover", function(event, d) {
          tooltip.style("opacity", 1)
            .style("left", (event.pageX + 10) + "px")
            .style("top", (event.pageY - 10) + "px")
            .html(`
              <div style="font-weight: bold; margin-bottom: 5px; padding-bottom: 5px; border-bottom: 1px solid rgba(255, 255, 255, 0.3);">Centromere</div>
              <div><strong>SeqID:</strong> ${d.seqid}</div>
              <div><strong>Start:</strong> ${d.start.toLocaleString()}</div>
              <div><strong>End:</strong> ${d.end.toLocaleString()}</div>
              <div><strong>Length:</strong> ${(d.end - d.start).toLocaleString()} bp</div>
            `);
        })
        .on("mouseout", function() {
          tooltip.style("opacity", 0);
        });

      // 添加rRNA tooltip事件
      svg.selectAll(".rrna-element")
        .on("mouseover", function(event, d) {
          tooltip.style("opacity", 1)
            .style("left", (event.pageX + 10) + "px")
            .style("top", (event.pageY - 10) + "px")
            .html(`
              <div style="font-weight: bold; margin-bottom: 5px; padding-bottom: 5px; border-bottom: 1px solid rgba(255, 255, 255, 0.3);">rRNA</div>
              <div><strong>SeqID:</strong> ${d.seqid}</div>
              <div><strong>Start:</strong> ${d.start.toLocaleString()}</div>
              <div><strong>End:</strong> ${d.end.toLocaleString()}</div>
              <div><strong>Length:</strong> ${(d.end - d.start).toLocaleString()} bp</div>
              ${d.name ? `<div><strong>Name:</strong> ${d.name}</div>` : ''}
            `);
        })
        .on("mouseout", function() {
          tooltip.style("opacity", 0);
        });

      // 添加miRNA tooltip事件
      svg.selectAll(".mirna-element")
        .on("mouseover", function(event, d) {
          tooltip.style("opacity", 1)
            .style("left", (event.pageX + 10) + "px")
            .style("top", (event.pageY - 10) + "px")
            .html(`
              <div style="font-weight: bold; margin-bottom: 5px; padding-bottom: 5px; border-bottom: 1px solid rgba(255, 255, 255, 0.3);">miRNA</div>
              <div><strong>SeqID:</strong> ${d.seqid}</div>
              <div><strong>Start:</strong> ${d.start.toLocaleString()}</div>
              <div><strong>End:</strong> ${d.end.toLocaleString()}</div>
              <div><strong>Length:</strong> ${(d.end - d.start).toLocaleString()} bp</div>
              ${d.name ? `<div><strong>Name:</strong> ${d.name}</div>` : ''}
              ${d.family ? `<div><strong>Family:</strong> ${d.family}</div>` : ''}
              ${d.strand ? `<div><strong>Strand:</strong> ${d.strand}</div>` : ''}
              ${d.score ? `<div><strong>Score:</strong> ${d.score}</div>` : ''}
              ${d.e_value ? `<div><strong>E-value:</strong> ${d.e_value}</div>` : ''}
            `);
        })
        .on("mouseout", function() {
          tooltip.style("opacity", 0);
        });

      // 添加tRNA tooltip事件
      svg.selectAll(".trna-element")
        .on("mouseover", function(event, d) {
          tooltip.style("opacity", 1)
            .style("left", (event.pageX + 10) + "px")
            .style("top", (event.pageY - 10) + "px")
            .html(`
              <div style="font-weight: bold; margin-bottom: 5px; padding-bottom: 5px; border-bottom: 1px solid rgba(255, 255, 255, 0.3);">tRNA</div>
              <div><strong>SeqID:</strong> ${d.seqid}</div>
              <div><strong>Start:</strong> ${d.start.toLocaleString()}</div>
              <div><strong>End:</strong> ${d.end.toLocaleString()}</div>
              <div><strong>Length:</strong> ${(d.end - d.start).toLocaleString()} bp</div>
              ${d.name ? `<div><strong>Name:</strong> ${d.name}</div>` : ''}
            `);
        })
        .on("mouseout", function() {
          tooltip.style("opacity", 0);
        });

      // 添加coreBlocks tooltip事件
      svg.selectAll(".coreblocks-element")
        .on("mouseover", function(event, d) {
          tooltip.style("opacity", 1)
            .style("left", (event.pageX + 10) + "px")
            .style("top", (event.pageY - 10) + "px")
            .html(`
              <div style="font-weight: bold; margin-bottom: 5px; padding-bottom: 5px; border-bottom: 1px solid rgba(255, 255, 255, 0.3);">CoreBlocks</div>
              <div><strong>SeqID:</strong> ${d.seqid}</div>
              <div><strong>Start:</strong> ${d.start.toLocaleString()}</div>
              <div><strong>End:</strong> ${d.end.toLocaleString()}</div>
              <div><strong>Length:</strong> ${d.length ? d.length.toLocaleString() : (d.end - d.start).toLocaleString()} bp</div>
            `);
        })
        .on("mouseout", function() {
          tooltip.style("opacity", 0);
        });
    };

    // 加载可视化数据
    const loadVisualizationData = async () => {
      if (!selectedOrganism.value || !selectedChromosome.value) {
        console.log('缺少生物体或染色体信息，跳过加载');
        return;
      }

      console.log(`开始加载可视化数据: ${selectedOrganism.value} - ${selectedChromosome.value}`);
      loadingVisualization.value = true;
      try {
        await Promise.all([
          fetchTEsData(selectedOrganism.value, selectedChromosome.value),
          fetchCentromereData(selectedOrganism.value, selectedChromosome.value),
          fetchRRNAData(selectedOrganism.value, selectedChromosome.value),
          fetchMiRNAData(selectedOrganism.value, selectedChromosome.value),
          fetchTRNAData(selectedOrganism.value, selectedChromosome.value),
          fetchCoreBlocksData(selectedOrganism.value, selectedChromosome.value),
          getChromosomeLength(selectedOrganism.value, selectedChromosome.value)
        ]);

        console.log(`数据加载完成 - TEs: ${tesData.value.length}, Centromere: ${centromereData.value.length}, rRNA: ${rRNAData.value.length}, miRNA: ${miRNAData.value.length}, tRNA: ${tRNAData.value.length}, CoreBlocks: ${coreBlocksData.value.length}, Length: ${chromosomeLength.value}`);

        // 数据加载完成后绘制可视化
        setTimeout(() => {
          drawChromosomeVisualization();
        }, 100);
      } catch (error) {
        console.error('加载可视化数据失败:', error);
        ElMessage.error('加载可视化数据失败');
      } finally {
        loadingVisualization.value = false;
      }
    };

    // 获取所有生物体列表
    const fetchOrganisms = async () => {
      try {
        loadingOrganisms.value = true;
        const response = await axios.get('/files/query/organisms/');
        allOrganisms.value = response.data || [];
        organismOptions.value = allOrganisms.value;
      } catch (error) {
        console.error('获取生物体列表失败:', error);
        ElMessage.error('获取生物体列表失败');
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

    const fetchChromosomesForCurrentContext = async () => {
      if (!selectedOrganism.value) {
        chromosomeOptions.value = [];
        selectedChromosome.value = '';
        return;
      }

      try {
        loadingChromosomes.value = true;
        const response = await axios.get('/files/query/chromosomes/', {
          params: buildGenomeContextParams()
        });
        const nextChromosomes = response.data || [];
        chromosomeOptions.value = nextChromosomes;

        if (!nextChromosomes.length) {
          selectedChromosome.value = '';
          return;
        }

        if (!nextChromosomes.includes(selectedChromosome.value)) {
          selectedChromosome.value = nextChromosomes[0];
        }
      } catch (error) {
        console.error('获取染色体列表失败:', error);
        ElMessage.error('获取染色体列表失败');
        chromosomeOptions.value = [];
        selectedChromosome.value = '';
      } finally {
        loadingChromosomes.value = false;
      }
    };

    const syncRouteContext = async () => {
      const accession = normalizeQueryValue(route.query.accession) || normalizeQueryValue(route.query.organism);
      const assembly = normalizeQueryValue(route.query.assembly);

      selectedOrganism.value = accession;
      contextAccession.value = accession;
      contextAssemblyId.value = assembly;

      if (!accession) {
        chromosomeOptions.value = [];
        selectedChromosome.value = '';
        return;
      }

      if (allOrganisms.value.length && !allOrganisms.value.includes(accession)) {
        organismOptions.value = Array.from(new Set([accession, ...allOrganisms.value]));
      }

      await replaceRouteQuery(buildNormalizedQuery({
        accession,
        assembly
      }));

      await fetchChromosomesForCurrentContext();
    };
    
    // 生物体选择变化
    const handleOrganismChange = async (value) => {
      const accession = value || '';
      selectedOrganism.value = accession;
      contextAccession.value = accession;
      contextAssemblyId.value = '';
      chromosomeOptions.value = [];
      selectedChromosome.value = '';

      if (!accession) {
        await replaceRouteQuery({});
        return;
      }

      await replaceRouteQuery(buildNormalizedQuery({
        accession
      }));
    };

    // 监听选择变化
    watch([selectedOrganism, selectedChromosome, contextAssemblyId], () => {
      if (selectedOrganism.value && selectedChromosome.value) {
        loadVisualizationData();
      }
    });

    // 监听显示选项变化
    watch([displayTEs, displayCentromere, displayRRNA, displayMiRNA, displayTRNA, displayCoreBlocks], () => {
      if (selectedOrganism.value && selectedChromosome.value) {
        drawChromosomeVisualization();
      }
    });
    
    // 获取文件列表
    const fetchFiles = async () => {
      try {
        loading.value = true;
        // 模拟数据加载
        setTimeout(() => {
          loading.value = false;
        }, 1000);
      } catch (error) {
        console.error('获取数据失败:', error);
        ElMessage.error('获取数据失败');
      }
    };
    
    const handleRouteParams = async () => {
      await syncRouteContext();
    };

    watch(
      () => [route.query.accession, route.query.assembly, route.query.organism],
      async () => {
        if (routeSyncInProgress.value) {
          return;
        }
        await syncRouteContext();
      }
    );

    watch(allOrganisms, async (newOrganisms) => {
      if (newOrganisms.length > 0) {
        await handleRouteParams();
      }
    });

    onMounted(() => {
      fetchOrganisms();
      fetchFiles();
    });

    return {
      loading,
      selectedOrganism,
      organismOptions,
      loadingOrganisms,
      searchOrganisms,
      handleOrganismChange,
      fetchFiles,
      selectedChromosome,
      chromosomeOptions,
      loadingChromosomes,
      displayTEs,
      displayCentromere,
      displayRRNA,
      displayMiRNA,
      displayTRNA,
      displayCoreBlocks,
      loadingVisualization,
      chromosomeContainer,
      tesData,
      centromereData,
      rRNAData,
      miRNAData,
      tRNAData,
      coreBlocksData,
      chromosomeLength,
      fetchTEsData,
      fetchCentromereData,
      fetchRNAData,
      fetchRRNAData,
      fetchMiRNAData,
      fetchTRNAData,
      fetchCoreBlocksData,
      getChromosomeLength,
      drawChromosomeVisualization,
      loadVisualizationData,
      segmentLength,
      segmentLengthMb,
      showSettings,
      handleSegmentLengthChange,
      downloadVisualization,
      handleRouteParams
    };
  }
}
</script>

<style scoped>
.genome-card-view {
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
}

.search-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  padding: 0 16px;
  max-width: 700px;
}

/* 染色体选择框样式 */
.chromosome-select {
  display: flex;
  align-items: center;
  min-width: 220px;
  justify-content: flex-end;
  flex-shrink: 0;
}

.select-label {
  margin-right: 8px;
  color: #606266;
  font-size: 14px;
  white-space: nowrap;
}

.chromosome-dropdown {
  width: 140px;
}

.divider {
  height: 24px;
  width: 1px;
  background-color: #dcdfe6;
  margin: 0 16px;
  flex-shrink: 0;
}

.search-icon {
  color: #606266;
  margin-right: 8px;
  flex-shrink: 0;
}

.search-select {
  flex-grow: 1;
  min-width: 200px;
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
}

.placeholder-content {
  padding: 40px;
  text-align: center;
  color: #909399;
}

.placeholder-content h3 {
  font-size: 20px;
  margin-bottom: 16px;
  color: #1a56db;
}
.visualization-container {
  margin-top: 20px;
}

.control-panel {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
  padding: 10px 15px;
  background-color: #f5f7fa;
  border-radius: 6px;
  width: fit-content;
  gap: 15px;
}

.display-title {
  margin-right: 15px;
  font-weight: 500;
  color: #303133;
  white-space: nowrap;
}

.el-checkbox {
  margin-right: 15px;
}

.checkbox-color {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 3px;
  margin-right: 5px;
  vertical-align: middle;
}

.te-color {
  background-color: #1a56db;
}

.centromere-color {
  background-color: #f56c6c;
}

.rrna-color {
  background-color: #67c23a;
}

.mirna-color {
  background-color: #e6a23c;
}

.trna-color {
  background-color: #909399;
}

.coreblocks-color {
  background-color: #722ed1;
}

.chromosome-visualization {
  width: 100%;
  min-height: 450px;
  overflow-x: auto;
  overflow-y: visible;
  position: relative;
}

.chromosome-container {
  width: 100%;
  height: 100%;
}

.loading-visualization {
  width: 100%;
  height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: #606266;
}

.loading-content .el-icon {
  font-size: 24px;
}

.empty-state {
  width: 100%;
  height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chromosome-tooltip {
  position: absolute;
  background-color: rgba(0, 0, 0, 0.8);
  color: white;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 12px;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.2s;
  z-index: 1000;
  max-width: 300px;
}

.chromosome-tooltip div {
  margin-bottom: 3px;
}

.settings-section {
  margin-left: auto;
}

.settings-panel {
  padding: 10px 0;
}

.setting-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 15px;
  gap: 10px;
}

.setting-item:last-child {
  margin-bottom: 0;
  justify-content: center;
}

.setting-item label {
  font-size: 14px;
  color: #606266;
  white-space: nowrap;
}

@media (max-width: 768px) {
  .control-panel {
    flex-wrap: wrap;
  }

  .chromosome-visualization {
    min-height: 350px;
  }
}

</style>
