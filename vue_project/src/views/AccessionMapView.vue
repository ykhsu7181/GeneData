<template>
  <div class="accession-map-view">
    <!-- 澶嶇敤鏁版嵁涓€瑙堣〃鐨勬爣棰樻牱寮?-->
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

    <!-- 鎼滅储妗?- 澶嶇敤鏁版嵁涓€瑙堣〃鏍峰紡 -->
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

    <!-- 浜氱兢绛涢€夊拰鍙鍖栭€夐」 -->
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
        <span class="filter-label">{{ $t('page.accessionMap.markerSize') }}</span>
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

    <!-- 涓撲笟绉戠爺椋庢牸鍦板浘鍗＄墖 -->
    <div class="research-map-card">


      <!-- 鍦板浘涓讳綋 -->
      <div class="map-body">
        <div v-if="loading" class="loading-state">
          <div class="loading-spinner">
            <div class="spinner"></div>
            <p>{{ $t('page.accessionMap.loadingGeographicData') }}</p>
          </div>
        </div>

        <div v-else class="map-wrapper">
          <!-- 鍦板浘瀹瑰櫒 -->
          <div ref="mapContainer" class="echarts-map"></div>




        </div>
      </div>


    </div>

    <!-- 绉戠爺椋庢牸鐨勬暟鎹憳瑕?-->
    <div class="data-summary">
      <h3 class="summary-title">{{ $t('page.accessionMap.dataOverview') }}</h3>
      <div class="summary-grid">
        <div class="summary-item">
          <div class="summary-icon">馃尵</div>
          <div class="summary-content">
            <div class="summary-number">{{ totalCount }}</div>
            <div class="summary-label">{{ $t('page.accessionMap.totalGermplasm') }}</div>
            <div class="summary-desc">{{ $t('page.accessionMap.totalGermplasmDesc') }}</div>
          </div>
        </div>
        <div class="summary-item">
          <div class="summary-icon">馃搷</div>
          <div class="summary-content">
            <div class="summary-number">{{ filteredData.length }}</div>
            <div class="summary-label">{{ $t('page.accessionMap.locatedGermplasm') }}</div>
            <div class="summary-desc">{{ $t('page.accessionMap.locatedGermplasmDesc') }}</div>
          </div>
        </div>
        <div class="summary-item">
          <div class="summary-icon">馃實</div>
          <div class="summary-content">
            <div class="summary-number">{{ uniqueCountries }}</div>
            <div class="summary-label">{{ $t('page.accessionMap.geographicRegions') }}</div>
            <div class="summary-desc">{{ $t('page.accessionMap.geographicRegionsDesc') }}</div>
          </div>
        </div>
        <div class="summary-item">
          <div class="summary-icon">馃К</div>
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
import { ref, onMounted, onUnmounted, computed, nextTick, watch } from 'vue';
import { Search, Refresh } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { useRouter, useRoute } from 'vue-router';
import { useI18n } from 'vue-i18n';
import axios from 'axios';
import * as echarts from 'echarts';
import { worldMapData } from '@/data/worldMapData.js';

export default {
  name: 'AccessionMapView',
  components: {
    Search,
    Refresh
  },
  setup() {
    const router = useRouter();
    const route = useRoute();
    const { t } = useI18n();
    const loading = ref(true);
    const selectedOrganism = ref('');
    const selectedRegion = ref('');
    const allOrganisms = ref([]);
    const organismOptions = ref([]);
    const loadingOrganisms = ref(false);
    
    // 浜氱兢绛涢€夌浉鍏?
    const allSubPopulations = ref([]);
    const selectedSubPopulations = ref([]);
    
    // 鏁版嵁鐩稿叧
    const supplementaryData = ref({});
    const totalCount = ref(0);
    
    // 鍦板浘鐩稿叧
    const mapContainer = ref(null);
    const mapInstance = ref(null);
    const mapMode = ref('scatter');
    const pointSize = ref(10);

    const syncRouteSelection = () => {
      const accessionFromQuery = route.query.accession || route.query.organism;
      selectedOrganism.value = typeof accessionFromQuery === 'string' ? accessionFromQuery : '';

      const regionFromQuery = route.query.region;
      selectedRegion.value = typeof regionFromQuery === 'string' ? regionFromQuery : '';

      const subPopulationFromQuery = route.query.sub_population;
      if (typeof subPopulationFromQuery === 'string' && subPopulationFromQuery.trim()) {
        selectedSubPopulations.value = [subPopulationFromQuery.trim()];
      } else if (allSubPopulations.value.length) {
        selectedSubPopulations.value = [...allSubPopulations.value];
      }
    };

    // 杩囨护鍚庣殑鏁版嵁
    const filteredData = computed(() => {
      let data = Object.entries(supplementaryData.value);

      // 鍙繑鍥炴湁缁忕含搴︿俊鎭殑鏁版嵁
      data = data.filter(([, info]) =>
        info.longitude !== null && info.latitude !== null
      );

      // 鎸夌敓鐗╀綋绛涢€?- 濡傛灉閫夋嫨浜嗙壒瀹氱殑 Accession锛屽彧鏄剧ず璇ョ偣
      if (selectedOrganism.value) {
        data = data.filter(([accession]) =>
          accession === selectedOrganism.value
        );
      } else {
        // 鍙湁鍦ㄦ病鏈夐€夋嫨鐗瑰畾 Accession 鏃舵墠搴旂敤浜氱兢绛涢€?
        // 濡傛灉娌℃湁閫変腑浠讳綍浜氱兢锛屽垯涓嶆樉绀轰换浣曟暟鎹偣
        if (selectedSubPopulations.value.length === 0) {
          return []; // 杩斿洖绌烘暟缁勶紝涓嶆樉绀轰换浣曠偣
        }

        // 鎸夐€変腑鐨勪簹缇ょ瓫閫?
        data = data.filter(([, info]) => {
          const subPop = info.sub_population || 'Unknown';
          return selectedSubPopulations.value.includes(subPop);
        });
      }

      if (selectedRegion.value) {
        const normalizedRegion = selectedRegion.value.toLowerCase();
        data = data.filter(([, info]) => {
          const region = (info.region || '').toLowerCase();
          const country = (info.country || '').toLowerCase();
          return region.includes(normalizedRegion) || country.includes(normalizedRegion);
        });
      }

      return data;
    });

    // 娑夊強鐨勫浗瀹?鍦板尯鏁伴噺锛堢畝鍖栬绠楋級
    const uniqueCountries = computed(() => {
      const coordinates = filteredData.value.map(([, info]) => 
        `${Math.round(info.longitude)},${Math.round(info.latitude)}`
      );
      return new Set(coordinates).size;
    });

    // 鑾峰彇浜氱兢鏍峰紡绫诲悕
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

    // 鑾峰彇鏈夊湴鐞嗕綅缃殑鐢熺墿浣撳垪琛?
    const fetchOrganisms = async () => {
      try {
        loadingOrganisms.value = true;

        // 绛夊緟琛ュ厖鏁版嵁鍔犺浇瀹屾垚
        if (Object.keys(supplementaryData.value).length === 0) {
          await fetchSupplementaryData();
        }

        // 浠庤ˉ鍏呮暟鎹腑鎻愬彇鏈夊湴鐞嗕綅缃殑 Accession
        const organismsWithLocation = Object.entries(supplementaryData.value)
          .filter(([, info]) =>
            info.longitude !== null &&
            info.latitude !== null
          )
          .map((entry) => entry[0])
          .sort(); // 鎸夊瓧姣嶉『搴忔帓搴?

        allOrganisms.value = organismsWithLocation;
        organismOptions.value = organismsWithLocation;
      } catch (error) {
        console.error('鑾峰彇鐢熺墿浣撳垪琛ㄥけ璐?', error);
        ElMessage.error(t('messages.getOrganismsFailed'));
      } finally {
        loadingOrganisms.value = false;
      }
    };

    // 鑾峰彇浜氱兢鍒楄〃
    const fetchSubPopulations = async () => {
      try {
        const response = await axios.get('/files/query/sub-populations/');
        // 灏嗗悗绔繑鍥炵殑"鏈煡浜氱兢"鏇挎崲涓?Unknown"
        const subPopulations = (response.data || []).map(subPop =>
          subPop === '鏈煡浜氱兢' ? 'Unknown' : subPop
        );
        allSubPopulations.value = subPopulations;
        selectedSubPopulations.value = [...allSubPopulations.value]; // 榛樿鍏ㄩ€?
        syncRouteSelection();
      } catch (error) {
        console.error('鑾峰彇浜氱兢鍒楄〃澶辫触:', error);
        ElMessage.error(t('messages.getSubPopulationsFailed'));
      }
    };

    // 鑾峰彇琛ュ厖鏁版嵁
    const fetchSupplementaryData = async () => {
      try {
        const response = await axios.get('/files/query/supplementary-data/');
        const rawData = response.data || {};

        // 杞崲琛ュ厖鏁版嵁涓殑浜氱兢淇℃伅锛屽皢"鏈煡浜氱兢"鏇挎崲涓?Unknown"
        const processedData = {};
        Object.keys(rawData).forEach(key => {
          const item = rawData[key];
          if (item.sub_population === '鏈煡浜氱兢') {
            item.sub_population = 'Unknown';
          }
          processedData[key] = item;
        });

        supplementaryData.value = processedData;
        totalCount.value = Object.keys(supplementaryData.value).length;
      } catch (error) {
        console.error('鑾峰彇琛ュ厖鏁版嵁澶辫触:', error);
        ElMessage.error(t('messages.getSupplementaryDataFailed'));
      }
    };

    // 鑾峰彇鎵€鏈夋暟鎹?
    const fetchData = async () => {
      try {
        loading.value = true;
        // 鍏堣幏鍙栬ˉ鍏呮暟鎹紝鍐嶈幏鍙栫敓鐗╀綋鍒楄〃锛堝洜涓虹敓鐗╀綋鍒楄〃渚濊禆琛ュ厖鏁版嵁锛?
        await fetchSupplementaryData();
        await Promise.all([
          fetchOrganisms(),
          fetchSubPopulations()
        ]);
      } catch (error) {
        console.error('鑾峰彇鏁版嵁澶辫触:', error);
        ElMessage.error(t('messages.getDataFailed'));
      } finally {
        loading.value = false;
      }
    };

    // 鎼滅储鐢熺墿浣擄紙鍙湪鏈夊湴鐞嗕綅缃殑 Accession 涓悳绱級
    const searchOrganisms = (query) => {
      if (query) {
        organismOptions.value = allOrganisms.value.filter(item =>
          item.toLowerCase().includes(query.toLowerCase())
        );
      } else {
        organismOptions.value = allOrganisms.value;
      }
    };

    // 鐢熺墿浣撻€夋嫨鍙樺寲
    const handleOrganismChange = (value) => {
      selectedOrganism.value = value;

      console.log('Selected organism:', value);
      console.log('Filtered data length:', filteredData.value.length);

      // 瑙﹀彂鍦板浘鏇存柊浠ュ簲鐢ㄦ柊鐨勭瓫閫?
      nextTick(() => {
        updateMap();

        // 濡傛灉閫夋嫨浜嗙壒瀹氱殑 Accession锛岃嚜鍔ㄨ皟鏁村湴鍥捐鍥惧埌璇ョ偣
        if (value && supplementaryData.value[value]) {
          const info = supplementaryData.value[value];
          if (info.longitude !== null && info.latitude !== null) {
            if (mapInstance.value) {
              // 灏嗗湴鍥句腑蹇冪Щ鍔ㄥ埌閫変腑鐨勭偣锛屽苟閫傚綋鏀惧ぇ
              setTimeout(() => {
                mapInstance.value.setOption({
                  geo: {
                    center: [info.longitude, info.latitude],
                    zoom: 4 // 鏀惧ぇ鍒板悎閫傜殑绾у埆
                  }
                });
              }, 100);
            }
          }
        } else if (!value) {
          // 濡傛灉娓呯┖閫夋嫨锛屾仮澶嶅埌鍏ㄥ眬瑙嗗浘
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

    // 浜氱兢绛涢€夊彉鍖?
    const handleSubPopulationChange = () => {
      // 绛涢€夐€昏緫宸插湪 computed 涓鐞?
      updateMap();
    };

    // 鍒濆鍖栧湴鍥?
    const initMap = async () => {
      if (!mapContainer.value) return;

      try {
        // 娉ㄥ唽涓栫晫鍦板浘锛堜娇鐢ㄥ鍏ョ殑涓栫晫鍦板浘鏁版嵁锛?
        echarts.registerMap('world', worldMapData);

        // 鍒涘缓鍦板浘瀹炰緥 - 鍚敤楂樺垎杈ㄧ巼娓叉煋
        mapInstance.value = echarts.init(mapContainer.value, null, {
          devicePixelRatio: window.devicePixelRatio || 2, // 楂樺垎杈ㄧ巼鏀寔
          renderer: 'canvas', // 浣跨敤 canvas 娓叉煋鍣ㄨ幏寰楁洿濂芥€ц兘
          useDirtyRect: false, // 绂佺敤鑴忕煩褰紭鍖栦互鑾峰緱鏇村ソ璐ㄩ噺
          width: mapContainer.value.clientWidth,
          height: mapContainer.value.clientHeight
        });

        // 璁剧疆鍦板浘閰嶇疆
        updateMap();

        // 鐩戝惉绐楀彛澶у皬鍙樺寲
        window.addEventListener('resize', () => {
          if (mapInstance.value) {
            mapInstance.value.resize();
          }
        });

      } catch (error) {
        console.error('鍦板浘鍒濆鍖栧け璐?', error);
        ElMessage.error(t('messages.mapLoadFailed'));
      }
    };

    // 鏇存柊鍦板浘
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
          triggerOn: 'mousemove|click', // 鏀寔榧犳爣绉诲姩鍜岀偣鍑昏Е鍙?
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
                      <div style="font-weight: 600; color: #1e293b; font-size: 12px; font-family: 'SF Mono', Monaco, monospace;">${params.data.value[0].toFixed(3)}掳, ${params.data.value[1].toFixed(3)}掳</div>
                    </div>
                  </div>
                  <div style="font-size: 11px; color: #94a3b8; text-align: center; font-style: italic; margin-top: 8px; padding: 6px 12px; background: #f1f5f9; border-radius: 6px; border: 1px solid #e2e8f0;">
                    <span style="color: #3b82f6; font-weight: 600;">馃挕 Click to view detailed information</span>
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
          zlevel: 1, // 璁剧疆杈冧綆鐨勫眰绾?
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
          triggerEvent: true, // 鍚敤浜嬩欢瑙﹀彂
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
          symbolSize: function() {
            return Math.max(pointSize.value + 3, 8);
          },
          zlevel: 2, // 璁剧疆杈冮珮鐨勫眰绾?
          itemStyle: {
            opacity: 0.8
          },
          emphasis: {
            itemStyle: {
              opacity: 1,
              scale: 1.3
            },
            focus: 'none', // 涓嶈仛鐒︼紝淇濇寔鍦板浘鍖哄煙鐨勪氦浜?
            blurScope: 'none' // 涓嶆ā绯婂叾浠栧厓绱?
          },
          // 鍏佽浜嬩欢绌块€忓埌搴曞眰鍦板浘
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

      mapInstance.value.setOption(option, false); // 浣跨敤 false 鏉ュ悎骞堕厤缃€屼笉鏄浛鎹?

      // 娣诲姞浜嬩欢鐩戝惉鍣ㄦ潵澶勭悊鏁ｇ偣鍜屽湴鍥惧尯鍩熺殑浜や簰
      setupMapInteraction();

      // 娣诲姞鐐瑰嚮浜嬩欢鐩戝惉鍣?
      setupClickEvents();
    };

    // 鑾峰彇浜氱兢棰滆壊 - 鏇翠笓涓氱殑绉戠爺閰嶈壊
    const getSubPopulationColor = (subPopulation) => {
      const colorMap = {
        'cA': '#2563eb',      // 绉戠爺钃?
        'cB': '#dc2626',      // 绉戠爺绾?
        'GJ': '#16a34a',      // 绉戠爺缁?
        'XI': '#9333ea',      // 绉戠爺绱?
        'WILD': '#ea580c',    // 绉戠爺姗?
        'O.glaberrima': '#db2777', // 绉戠爺绮?
        'Unknown': '#64748b'  // 绉戠爺鐏?
      };
      return colorMap[subPopulation] || '#64748b';
    };

    // 鑾峰彇浜氱兢鏁伴噺
    const getSubPopulationCount = (subPopulation) => {
      return filteredData.value.filter(([, info]) =>
        (info.sub_population || 'Unknown') === subPopulation
      ).length;
    };

    // 鍒囨崲浜氱兢鏄剧ず
    const toggleSubPopulation = (subPopulation) => {
      const index = selectedSubPopulations.value.indexOf(subPopulation);
      if (index > -1) {
        selectedSubPopulations.value.splice(index, 1);
      } else {
        selectedSubPopulations.value.push(subPopulation);
      }
      updateMap();
    };



    // 璁剧疆鍦板浘浜や簰閫昏緫
    const setupMapInteraction = () => {
      if (!mapInstance.value) return;

      // 璁剧疆鍦板浘瀹瑰櫒鐨凜SS锛岀‘淇濅簨浠惰兘澶熸纭紶閫?
      const mapDom = mapInstance.value.getDom();
      if (mapDom) {
        mapDom.style.pointerEvents = 'auto';
        // 涓烘暎鐐规坊鍔犻紶鏍囨寚閽堟牱寮?
        mapDom.style.cursor = 'default';
      }
    };

    // 璁剧疆鐐瑰嚮浜嬩欢
    const setupClickEvents = () => {
      if (!mapInstance.value) return;

      // 娓呴櫎涔嬪墠鐨勪簨浠剁洃鍚櫒
      mapInstance.value.off('click');
      mapInstance.value.off('mouseover');
      mapInstance.value.off('mouseout');

      // 鐩戝惉鏁ｇ偣鐨勭偣鍑讳簨浠?
      mapInstance.value.on('click', { seriesType: 'scatter' }, function(params) {
        if (params.data && params.data.name) {
          const accessionId = params.data.name;

          // 璺宠浆鍒?Accession 椤甸潰锛屼紶閫?organism 鍙傛暟
          router.push({
            path: '/accession-card',
            query: {
              accession: accessionId
            }
          });

          // 鏄剧ず璺宠浆鎻愮ず
          ElMessage.success(t('messages.jumpingToDetailsPage', { accession: accessionId }));
        }
      });

      // 鐩戝惉鏁ｇ偣鐨勯紶鏍囨偓鍋滀簨浠讹紝鏀瑰彉鎸囬拡鏍峰紡
      mapInstance.value.on('mouseover', { seriesType: 'scatter' }, function() {
        const mapDom = mapInstance.value.getDom();
        if (mapDom) {
          mapDom.style.cursor = 'pointer';
        }
      });

      // 鐩戝惉鏁ｇ偣鐨勯紶鏍囩寮€浜嬩欢锛屾仮澶嶆寚閽堟牱寮?
      mapInstance.value.on('mouseout', { seriesType: 'scatter' }, function() {
        const mapDom = mapInstance.value.getDom();
        if (mapDom) {
          mapDom.style.cursor = 'default';
        }
      });
    };

    onMounted(async () => {
      syncRouteSelection();
      await fetchData();
      await nextTick();
      initMap();
    });

    watch(
      () => route.query,
      async () => {
        syncRouteSelection();
        await nextTick();
        updateMap();
      }
    );

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

/* 澶嶇敤鏁版嵁涓€瑙堣〃鐨勬爣棰樻牱寮?*/
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

/* 澶嶇敤鏁版嵁涓€瑙堣〃鐨勬悳绱㈡牱寮?*/
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

/* 绛涢€夐潰鏉挎牱寮?*/
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

/* 浜氱兢鏍囩鏍峰紡 - 澶嶇敤鏁版嵁涓€瑙堣〃鏍峰紡 */
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

/* 涓撲笟绉戠爺椋庢牸鍦板浘鍗＄墖 */
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



/* 鍦板浘涓讳綋 */
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
  /* 纭繚楂樻竻娓叉煋 */
  image-rendering: -webkit-optimize-contrast;
  image-rendering: crisp-edges;
  image-rendering: pixelated;
  /* 闃叉妯＄硦 */
  transform: translateZ(0);
  -webkit-transform: translateZ(0);
  /* 纭欢鍔犻€?*/
  will-change: transform;
  /* 纭繚娓呮櫚鐨勬枃鏈覆鏌?*/
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}











/* 鍔ㄧ敾鏁堟灉 */

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

/* 鏁版嵁鎽樿鏍峰紡 */
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

/* Element Plus 鏍峰紡瑕嗙洊 */
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

/* 绛涢€夊鍣ㄦ牱寮?*/
.filter-container {
  display: inline-block;
}
</style>


