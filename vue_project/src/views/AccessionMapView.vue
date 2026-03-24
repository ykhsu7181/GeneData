<template>
  <div class="accession-map-view">
    <!-- 复用数据一览表的标题样式 -->
    <div class="page-header">
      <h2 class="title">{{ $t('page.accessionMap.title') }}</h2>
      <div class="header-actions">
        <el-tooltip :content="$t('page.accessionMap.refreshData')" placement="top">
          <el-button circle size="small" @click="fetchData" :loading="loading">
            <el-icon><Refresh /></el-icon>
          </el-button>
        </el-tooltip>
      </div>
    </div>

    <!-- 搜索框 - 复用数据一览表样式 -->
    <div class="search-container">
      <div class="search-wrapper">
        <el-icon class="search-icon"><Search /></el-icon>
        <el-select
          v-model="selectedOrganism"
          filterable
          remote
          :placeholder="$t('page.accessionMap.searchPlaceholder')"
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
      </div>
    </div>

    <!-- 亚群筛选和可视化选项 -->
    <div class="filter-panel">
      <div class="filter-section">
        <span class="filter-label">{{ $t('page.accessionMap.subPopulationFilter') }}</span>
        <el-checkbox-group v-model="selectedSubPopulations" @change="handleSubPopulationChange" class="subpop-checkboxes">
          <el-checkbox 
            v-for="subPop in allSubPopulations" 
            :key="subPop" 
            :label="subPop">
            <span :class="['sub-population', getSubPopulationClass(subPop)]">
              {{ subPop }}
            </span>
          </el-checkbox>
        </el-checkbox-group>
      </div>
      
      <div class="viz-section">
        <span class="filter-label">{{ $t('page.accessionMap.markerSize') }}：</span>
        <el-slider 
          v-model="pointSize" 
          :min="5" 
          :max="25" 
          @change="updateMap"
          :show-tooltip="true"
          style="width: 120px;">
        </el-slider>
      </div>
    </div>

    <!-- 专业科研风格地图卡片 -->
    <div class="research-map-card">


      <!-- 地图主体 -->
      <div class="map-body">
        <div v-if="loading" class="loading-state">
          <div class="loading-spinner">
            <div class="spinner"></div>
            <p>{{ $t('page.accessionMap.loadingGeographicData') }}</p>
          </div>
        </div>

        <div v-else class="map-wrapper">
          <!-- 地图容器 -->
          <div ref="mapContainer" class="echarts-map"></div>




        </div>
      </div>


    </div>

    <!-- 科研风格的数据摘要 -->
    <div class="data-summary">
      <h3 class="summary-title">{{ $t('page.accessionMap.dataOverview') }}</h3>
      <div class="summary-grid">
        <div class="summary-item">
          <div class="summary-icon">🌾</div>
          <div class="summary-content">
            <div class="summary-number">{{ totalCount }}</div>
            <div class="summary-label">{{ $t('page.accessionMap.totalGermplasm') }}</div>
            <div class="summary-desc">{{ $t('page.accessionMap.totalGermplasmDesc') }}</div>
          </div>
        </div>
        <div class="summary-item">
          <div class="summary-icon">📍</div>
          <div class="summary-content">
            <div class="summary-number">{{ filteredData.length }}</div>
            <div class="summary-label">{{ $t('page.accessionMap.locatedGermplasm') }}</div>
            <div class="summary-desc">{{ $t('page.accessionMap.locatedGermplasmDesc') }}</div>
          </div>
        </div>
        <div class="summary-item">
          <div class="summary-icon">🌍</div>
          <div class="summary-content">
            <div class="summary-number">{{ uniqueCountries }}</div>
            <div class="summary-label">{{ $t('page.accessionMap.geographicRegions') }}</div>
            <div class="summary-desc">{{ $t('page.accessionMap.geographicRegionsDesc') }}</div>
          </div>
        </div>
        <div class="summary-item">
          <div class="summary-icon">🧬</div>
          <div class="summary-content">
            <div class="summary-number">{{ selectedSubPopulations.length }}</div>
            <div class="summary-label">{{ $t('page.accessionMap.activeSubPopulations') }}</div>
            <div class="summary-desc">{{ $t('page.accessionMap.activeSubPopulationsDesc') }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue';
import { Search } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { useRouter, useRoute } from 'vue-router';
import { useI18n } from 'vue-i18n';
import axios from 'axios';
import * as echarts from 'echarts';
import { worldMapData } from '@/data/worldMapData.js';

export default {
  name: 'AccessionMapView',
  components: {
    Search
  },
  setup() {
    const router = useRouter();
    const route = useRoute();
    const { t } = useI18n();
    const loading = ref(true);
    const selectedOrganism = ref('');
    const allOrganisms = ref([]);
    const organismOptions = ref([]);
    const loadingOrganisms = ref(false);
    
    // 亚群筛选相关
    const allSubPopulations = ref([]);
    const selectedSubPopulations = ref([]);
    
    // 数据相关
    const supplementaryData = ref({});
    const totalCount = ref(0);
    
    // 地图相关
    const mapContainer = ref(null);
    const mapInstance = ref(null);
    const mapMode = ref('scatter');
    const pointSize = ref(10);

    // 过滤后的数据
    const filteredData = computed(() => {
      let data = Object.entries(supplementaryData.value);

      // 只返回有经纬度信息的数据
      data = data.filter(([, info]) =>
        info.longitude !== null && info.latitude !== null
      );

      // 按生物体筛选 - 如果选择了特定的 Accession，只显示该点
      if (selectedOrganism.value) {
        data = data.filter(([accession]) =>
          accession === selectedOrganism.value
        );
      } else {
        // 只有在没有选择特定 Accession 时才应用亚群筛选
        // 如果没有选中任何亚群，则不显示任何数据点
        if (selectedSubPopulations.value.length === 0) {
          return []; // 返回空数组，不显示任何点
        }

        // 按选中的亚群筛选
        data = data.filter(([, info]) => {
          const subPop = info.sub_population || 'Unknown';
          return selectedSubPopulations.value.includes(subPop);
        });
      }

      return data;
    });

    // 涉及的国家/地区数量（简化计算）
    const uniqueCountries = computed(() => {
      const coordinates = filteredData.value.map(([, info]) => 
        `${Math.round(info.longitude)},${Math.round(info.latitude)}`
      );
      return new Set(coordinates).size;
    });

    // 获取亚群样式类名
    const getSubPopulationClass = (subPopulation) => {
      const classMap = {
        'cA': 'sub-pop-ca',
        'cB': 'sub-pop-cb',
        'GJ': 'sub-pop-gj',
        'XI': 'sub-pop-xi',
        'WILD': 'sub-pop-wild',
        'O.glaberrima': 'sub-pop-glaberrima',
        'Unknown': 'sub-pop-unknown'
      };
      return classMap[subPopulation] || 'sub-pop-default';
    };

    // 获取有地理位置的生物体列表
    const fetchOrganisms = async () => {
      try {
        loadingOrganisms.value = true;

        // 等待补充数据加载完成
        if (Object.keys(supplementaryData.value).length === 0) {
          await fetchSupplementaryData();
        }

        // 从补充数据中提取有地理位置的 Accession
        const organismsWithLocation = Object.entries(supplementaryData.value)
          .filter(([accession, info]) =>
            info.longitude !== null &&
            info.latitude !== null
          )
          .map(([accession]) => accession)
          .sort(); // 按字母顺序排序

        allOrganisms.value = organismsWithLocation;
        organismOptions.value = organismsWithLocation;
      } catch (error) {
        console.error('获取生物体列表失败:', error);
        ElMessage.error(t('messages.getOrganismsFailed'));
      } finally {
        loadingOrganisms.value = false;
      }
    };

    // 获取亚群列表
    const fetchSubPopulations = async () => {
      try {
        const response = await axios.get('/files/genome-files/sub_populations/');
        // 将后端返回的"未知亚群"替换为"Unknown"
        const subPopulations = (response.data || []).map(subPop =>
          subPop === '未知亚群' ? 'Unknown' : subPop
        );
        allSubPopulations.value = subPopulations;
        selectedSubPopulations.value = [...allSubPopulations.value]; // 默认全选
      } catch (error) {
        console.error('获取亚群列表失败:', error);
        ElMessage.error(t('messages.getSubPopulationsFailed'));
      }
    };

    // 获取补充数据
    const fetchSupplementaryData = async () => {
      try {
        const response = await axios.get('/files/genome-files/supplementary_data/');
        const rawData = response.data || {};

        // 转换补充数据中的亚群信息，将"未知亚群"替换为"Unknown"
        const processedData = {};
        Object.keys(rawData).forEach(key => {
          const item = rawData[key];
          if (item.sub_population === '未知亚群') {
            item.sub_population = 'Unknown';
          }
          processedData[key] = item;
        });

        supplementaryData.value = processedData;
        totalCount.value = Object.keys(supplementaryData.value).length;
      } catch (error) {
        console.error('获取补充数据失败:', error);
        ElMessage.error(t('messages.getSupplementaryDataFailed'));
      }
    };

    // 获取所有数据
    const fetchData = async () => {
      try {
        loading.value = true;
        // 先获取补充数据，再获取生物体列表（因为生物体列表依赖补充数据）
        await fetchSupplementaryData();
        await Promise.all([
          fetchOrganisms(),
          fetchSubPopulations()
        ]);
      } catch (error) {
        console.error('获取数据失败:', error);
        ElMessage.error(t('messages.getDataFailed'));
      } finally {
        loading.value = false;
      }
    };

    // 搜索生物体（只在有地理位置的 Accession 中搜索）
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
    const handleOrganismChange = (value) => {
      selectedOrganism.value = value;

      console.log('Selected organism:', value);
      console.log('Filtered data length:', filteredData.value.length);

      // 触发地图更新以应用新的筛选
      nextTick(() => {
        updateMap();

        // 如果选择了特定的 Accession，自动调整地图视图到该点
        if (value && supplementaryData.value[value]) {
          const info = supplementaryData.value[value];
          if (info.longitude !== null && info.latitude !== null) {
            if (mapInstance.value) {
              // 将地图中心移动到选中的点，并适当放大
              setTimeout(() => {
                mapInstance.value.setOption({
                  geo: {
                    center: [info.longitude, info.latitude],
                    zoom: 4 // 放大到合适的级别
                  }
                });
              }, 100);
            }
          }
        } else if (!value) {
          // 如果清空选择，恢复到全局视图
          if (mapInstance.value) {
            mapInstance.value.setOption({
              geo: {
                center: [20, 10],
                zoom: 1.3
              }
            });
          }
        }
      });
    };

    // 亚群筛选变化
    const handleSubPopulationChange = () => {
      // 筛选逻辑已在 computed 中处理
      updateMap();
    };

    // 初始化地图
    const initMap = async () => {
      if (!mapContainer.value) return;

      try {
        // 注册世界地图（使用导入的世界地图数据）
        echarts.registerMap('world', worldMapData);

        // 创建地图实例 - 启用高分辨率渲染
        mapInstance.value = echarts.init(mapContainer.value, null, {
          devicePixelRatio: window.devicePixelRatio || 2, // 高分辨率支持
          renderer: 'canvas', // 使用 canvas 渲染器获得更好性能
          useDirtyRect: false, // 禁用脏矩形优化以获得更好质量
          width: mapContainer.value.clientWidth,
          height: mapContainer.value.clientHeight
        });

        // 设置地图配置
        updateMap();

        // 监听窗口大小变化
        window.addEventListener('resize', () => {
          if (mapInstance.value) {
            mapInstance.value.resize();
          }
        });

      } catch (error) {
        console.error('地图初始化失败:', error);
        ElMessage.error(t('messages.mapLoadFailed'));
      }
    };

    // 更新地图
    const updateMap = () => {
      if (!mapInstance.value) return;

      console.log('Updating map with filtered data:', filteredData.value.length, 'points');

      const mapData = filteredData.value.map(([accession, info]) => {
        const subPop = info.sub_population || 'Unknown';
        return {
          name: accession,
          value: [info.longitude, info.latitude, 1],
          subPopulation: subPop,
          itemStyle: {
            color: getSubPopulationColor(subPop)
          }
        };
      });

      console.log('Map data points:', mapData.length);

      const option = {
        backgroundColor: '#f8fafc',
        tooltip: {
          trigger: 'item',
          triggerOn: 'mousemove|click', // 支持鼠标移动和点击触发
          backgroundColor: 'rgba(255, 255, 255, 0.96)',
          borderColor: '#e2e8f0',
          borderWidth: 1,
          borderRadius: 12,
          shadowBlur: 20,
          shadowColor: 'rgba(0, 0, 0, 0.12)',
          shadowOffsetX: 0,
          shadowOffsetY: 8,
          textStyle: {
            color: '#1e293b',
            fontSize: 14,
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
          },
          formatter: function(params) {
            if (params.data) {
              return `
                <div style="padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; min-width: 280px; max-width: 320px;">
                  <div style="display: flex; align-items: center; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 2px solid #f1f5f9;">
                    <div style="width: 12px; height: 12px; border-radius: 50%; background: ${params.data.itemStyle.color}; margin-right: 12px; box-shadow: 0 0 0 3px ${params.data.itemStyle.color}20;"></div>
                    <div style="font-weight: 700; color: #0f172a; font-size: 16px; letter-spacing: -0.025em;">${params.data.name}</div>
                  </div>
                  <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px;">
                    <div style="background: #f8fafc; padding: 8px 12px; border-radius: 8px; border-left: 3px solid ${params.data.itemStyle.color};">
                      <div style="font-size: 11px; color: #64748b; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 2px;">Subpopulation</div>
                      <div style="font-weight: 700; color: #1e293b; font-size: 13px;">${params.data.subPopulation}</div>
                    </div>
                    <div style="background: #f8fafc; padding: 8px 12px; border-radius: 8px;">
                      <div style="font-size: 11px; color: #64748b; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 2px;">Coordinates</div>
                      <div style="font-weight: 600; color: #1e293b; font-size: 12px; font-family: 'SF Mono', Monaco, monospace;">${params.data.value[0].toFixed(3)}°, ${params.data.value[1].toFixed(3)}°</div>
                    </div>
                  </div>
                  <div style="font-size: 11px; color: #94a3b8; text-align: center; font-style: italic; margin-top: 8px; padding: 6px 12px; background: #f1f5f9; border-radius: 6px; border: 1px solid #e2e8f0;">
                    <span style="color: #3b82f6; font-weight: 600;">💡 Click to view detailed information</span>
                  </div>
                </div>
              `;
            }
            return '';
          }
        },
        geo: {
          map: 'world',
          roam: true,
          zoom: 1.3,
          center: [20, 10],
          left: 30,
          right: 30,
          top: 30,
          bottom: 30,
          boundingCoords: [[-180, -90], [180, 90]],
          zlevel: 1, // 设置较低的层级
          itemStyle: {
            areaColor: '#f1f5f9',
            borderColor: '#cbd5e1',
            borderWidth: 1
          },
          emphasis: {
            itemStyle: {
              areaColor: '#e2e8f0',
              borderColor: '#94a3b8'
            }
          },
          silent: false,
          triggerEvent: true, // 启用事件触发
          regions: [
            {
              name: 'Antarctica',
              itemStyle: {
                areaColor: '#f8fafc'
              }
            }
          ]
        },
        series: [{
          type: 'scatter',
          coordinateSystem: 'geo',
          data: mapData,
          symbol: 'circle',
          symbolSize: function(val) {
            return Math.max(pointSize.value + 3, 8);
          },
          zlevel: 2, // 设置较高的层级
          itemStyle: {
            opacity: 0.8
          },
          emphasis: {
            itemStyle: {
              opacity: 1,
              scale: 1.3
            },
            focus: 'none', // 不聚焦，保持地图区域的交互
            blurScope: 'none' // 不模糊其他元素
          },
          // 允许事件穿透到底层地图
          silent: false,
          animation: true,
          animationDuration: 800,
          animationEasing: 'cubicOut',
          animationDelay: function(idx) {
            return idx * 5;
          },
          progressive: 0,
          progressiveThreshold: 3000
        }]
      };

      mapInstance.value.setOption(option, false); // 使用 false 来合并配置而不是替换

      // 添加事件监听器来处理散点和地图区域的交互
      setupMapInteraction();

      // 添加点击事件监听器
      setupClickEvents();
    };

    // 获取亚群颜色 - 更专业的科研配色
    const getSubPopulationColor = (subPopulation) => {
      const colorMap = {
        'cA': '#2563eb',      // 科研蓝
        'cB': '#dc2626',      // 科研红
        'GJ': '#16a34a',      // 科研绿
        'XI': '#9333ea',      // 科研紫
        'WILD': '#ea580c',    // 科研橙
        'O.glaberrima': '#db2777', // 科研粉
        'Unknown': '#64748b'  // 科研灰
      };
      return colorMap[subPopulation] || '#64748b';
    };

    // 获取亚群数量
    const getSubPopulationCount = (subPopulation) => {
      return filteredData.value.filter(([, info]) =>
        (info.sub_population || 'Unknown') === subPopulation
      ).length;
    };

    // 切换亚群显示
    const toggleSubPopulation = (subPopulation) => {
      const index = selectedSubPopulations.value.indexOf(subPopulation);
      if (index > -1) {
        selectedSubPopulations.value.splice(index, 1);
      } else {
        selectedSubPopulations.value.push(subPopulation);
      }
      updateMap();
    };



    // 设置地图交互逻辑
    const setupMapInteraction = () => {
      if (!mapInstance.value) return;

      // 设置地图容器的CSS，确保事件能够正确传递
      const mapDom = mapInstance.value.getDom();
      if (mapDom) {
        mapDom.style.pointerEvents = 'auto';
        // 为散点添加鼠标指针样式
        mapDom.style.cursor = 'default';
      }
    };

    // 设置点击事件
    const setupClickEvents = () => {
      if (!mapInstance.value) return;

      // 清除之前的事件监听器
      mapInstance.value.off('click');
      mapInstance.value.off('mouseover');
      mapInstance.value.off('mouseout');

      // 监听散点的点击事件
      mapInstance.value.on('click', { seriesType: 'scatter' }, function(params) {
        if (params.data && params.data.name) {
          const accessionId = params.data.name;

          // 跳转到 Accession 页面，传递 organism 参数
          router.push({
            path: '/accession-card',
            query: {
              organism: accessionId
            }
          });

          // 显示跳转提示
          ElMessage.success(t('messages.jumpingToDetailsPage', { accession: accessionId }));
        }
      });

      // 监听散点的鼠标悬停事件，改变指针样式
      mapInstance.value.on('mouseover', { seriesType: 'scatter' }, function(params) {
        const mapDom = mapInstance.value.getDom();
        if (mapDom) {
          mapDom.style.cursor = 'pointer';
        }
      });

      // 监听散点的鼠标离开事件，恢复指针样式
      mapInstance.value.on('mouseout', { seriesType: 'scatter' }, function(params) {
        const mapDom = mapInstance.value.getDom();
        if (mapDom) {
          mapDom.style.cursor = 'default';
        }
      });
    };

    onMounted(async () => {
      // 检查URL查询参数中是否有organism
      const organismFromQuery = route.query.organism;
      if (organismFromQuery) {
        selectedOrganism.value = organismFromQuery;
      }

      await fetchData();
      await nextTick();
      initMap();
    });

    onUnmounted(() => {
      if (mapInstance.value) {
        mapInstance.value.dispose();
      }
      window.removeEventListener('resize', () => {});
    });

    return {
      loading,
      selectedOrganism,
      organismOptions,
      loadingOrganisms,
      allSubPopulations,
      selectedSubPopulations,
      filteredData,
      totalCount,
      uniqueCountries,
      mapContainer,
      mapMode,
      pointSize,
      getSubPopulationClass,
      getSubPopulationColor,
      getSubPopulationCount,
      toggleSubPopulation,
      setupMapInteraction,
      setupClickEvents,
      searchOrganisms,
      handleOrganismChange,
      handleSubPopulationChange,
      updateMap,
      fetchData
    };
  }
};
</script>

<style scoped>
.accession-map-view {
  padding: 0;
}

/* 复用数据一览表的标题样式 */
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

/* 复用数据一览表的搜索样式 */
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
  max-width: 500px;
}

.search-icon {
  color: #606266;
  margin-right: 8px;
}

.search-select {
  width: 100%;
}

/* 筛选面板样式 */
.filter-panel {
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  padding: 20px;
  margin-bottom: 24px;
}

.filter-section {
  display: flex;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 20px;
}

.filter-section:last-child {
  margin-bottom: 0;
}

.viz-section {
  display: flex;
  align-items: center;
  gap: 16px;
}

.filter-label {
  font-weight: 500;
  color: #606266;
  white-space: nowrap;
  margin-top: 4px;
}

.subpop-checkboxes {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

/* 亚群标签样式 - 复用数据一览表样式 */
.sub-population {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  text-align: center;
  white-space: nowrap;
  border: none !important;
}

.sub-pop-ca {
  background-color: #e0f2fe;
  color: #0369a1;
}

.sub-pop-cb {
  background-color: #fef3c7;
  color: #d97706;
}

.sub-pop-gj {
  background-color: #ecfdf5;
  color: #059669;
}

.sub-pop-xi {
  background-color: #f3f0ff;
  color: #7c3aed;
}

.sub-pop-wild {
  background-color: #fef2f2;
  color: #dc2626;
}

.sub-pop-glaberrima {
  background-color: #fdf4ff;
  color: #c026d3;
}

.sub-pop-unknown {
  background-color: #f3f4f6;
  color: #6b7280;
}

.sub-pop-default {
  background-color: #f9fafb;
  color: #6b7280;
}

/* 专业科研风格地图卡片 */
.research-map-card {
  background: #ffffff;
  border-radius: 20px;
  box-shadow:
    0 10px 15px -3px rgba(0, 0, 0, 0.15),
    0 4px 6px -2px rgba(0, 0, 0, 0.08),
    0 0 0 1px rgba(0, 0, 0, 0.08);
  border: 2px solid #e5e7eb;
  overflow: hidden;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  margin-bottom: 32px;
}

.research-map-card:hover {
  box-shadow:
    0 25px 50px -12px rgba(0, 0, 0, 0.2),
    0 10px 10px -5px rgba(0, 0, 0, 0.08),
    0 0 0 1px rgba(59, 130, 246, 0.1);
  border-color: #cbd5e1;
  transform: translateY(-2px);
}



/* 地图主体 */
.map-body {
  position: relative;
  min-height: 800px;
  background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
  transition: all 0.3s ease;
}



.loading-state {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 800px;
  background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
}

.loading-spinner {
  text-align: center;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #e2e8f0;
  border-top: 4px solid #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 16px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.loading-spinner p {
  color: #64748b;
  font-size: 14px;
  font-weight: 500;
}

.map-wrapper {
  position: relative;
  height: 800px;
  background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
}

.echarts-map {
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
  /* 确保高清渲染 */
  image-rendering: -webkit-optimize-contrast;
  image-rendering: crisp-edges;
  image-rendering: pixelated;
  /* 防止模糊 */
  transform: translateZ(0);
  -webkit-transform: translateZ(0);
  /* 硬件加速 */
  will-change: transform;
  /* 确保清晰的文本渲染 */
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}











/* 动画效果 */

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 数据摘要样式 */
.data-summary {
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
  padding: 32px;
  border: 1px solid #e2e8f0;
}

.summary-title {
  margin: 0 0 24px 0;
  font-size: 20px;
  font-weight: 600;
  color: #1e293b;
  font-family: 'Microsoft YaHei', 'PingFang SC', 'Hiragino Sans GB', sans-serif;
  border-bottom: 2px solid #e2e8f0;
  padding-bottom: 12px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 24px;
}

.summary-item {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 20px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  transition: all 0.3s ease;
}

.summary-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
  border-color: #cbd5e1;
}

.summary-icon {
  font-size: 24px;
  flex-shrink: 0;
  margin-top: 4px;
}

.summary-content {
  flex: 1;
}

.summary-number {
  font-size: 32px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 4px;
  font-family: 'Microsoft YaHei', 'PingFang SC', 'Hiragino Sans GB', sans-serif;
}

.summary-label {
  font-size: 16px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 4px;
}

.summary-desc {
  font-size: 13px;
  color: #64748b;
  line-height: 1.4;
}

/* Element Plus 样式覆盖 */
:deep(.el-select) {
  width: 100%;
}

:deep(.el-select .el-input__wrapper) {
  box-shadow: none;
  border: none;
}

:deep(.el-checkbox-group) {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

:deep(.el-checkbox) {
  margin-right: 0;
}

:deep(.el-checkbox__label) {
  padding-left: 8px;
}

/* 筛选容器样式 */
.filter-container {
  display: inline-block;
}
</style>
