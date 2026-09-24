<template>
  <div class="codonw-tool">
    <div class="page-header">
      <h2 class="title">{{ $t('page.codonw.title') }}</h2>
      <div class="header-actions">
        <el-tooltip :content="$t('page.codonw.refreshData')" placement="top">
          <el-button circle size="small" @click="refreshPage">
            <el-icon><Refresh /></el-icon>
          </el-button>
        </el-tooltip>
      </div>
    </div>

    <!-- 工具说明 -->
    <div class="tool-description">
      <el-card>
        <template #header>
          <span>{{ $t('page.codonw.aboutCodonW') }}</span>
        </template>
        <p>{{ $t('page.codonw.description') }}</p>
        <ul>
          <li>{{ $t('page.codonw.codonUsageFrequency') }}</li>
          <li>{{ $t('page.codonw.effectiveNumberOfCodons') }}</li>
          <li>{{ $t('page.codonw.codonAdaptationIndex') }}</li>
          <li>{{ $t('page.codonw.codonBiasIndex') }}</li>
          <li>{{ $t('page.codonw.gcContentAnalysis') }}</li>
        </ul>
      </el-card>
    </div>

    <!-- 分析方式选择 -->
    <div class="analysis-type-section">
      <el-card>
        <template #header>
          <span>{{ $t('page.codonw.selectAnalysisType') }}</span>
        </template>
        <el-radio-group v-model="analysisType" @change="handleAnalysisTypeChange">
          <el-radio value="genomic" size="large">
            <div class="radio-content">
              <div class="radio-title">{{ $t('page.codonw.genomicAnalysis') }}</div>
              <div class="radio-description">{{ $t('page.codonw.genomicAnalysisDesc') }}</div>
            </div>
          </el-radio>
          <el-radio value="cds" size="large">
            <div class="radio-content">
              <div class="radio-title">{{ $t('page.codonw.cdsAnalysis') }}</div>
              <div class="radio-description">{{ $t('page.codonw.cdsAnalysisDesc') }}</div>
            </div>
          </el-radio>
        </el-radio-group>
      </el-card>
    </div>

    <!-- 基因组分析上传区域 -->
    <div class="upload-section" v-if="analysisType === 'genomic'">
      <el-card>
        <template #header>
          <span>{{ $t('page.codonw.genomicFileUpload') }}</span>
        </template>

        <div class="genomic-upload-container">
          <div class="upload-item">
            <h4>{{ $t('page.codonw.genomeFile') }} <span class="required">{{ $t('page.codonw.required') }}</span></h4>
            <el-upload
              ref="genomeUploadRef"
              class="upload-demo"
              drag
              :action="uploadUrl"
              :headers="uploadHeaders"
              :data="genomeUploadData"
              :on-success="handleGenomeUploadSuccess"
              :on-error="handleUploadError"
              :on-progress="handleUploadProgress"
              :before-upload="beforeGenomeUpload"
              :on-change="handleGenomeFileChange"
              :file-list="genomeFileList"
              accept=".fasta,.fa,.fas,.fna"
              :auto-upload="false"
            >
              <el-icon class="el-icon--upload"><upload-filled /></el-icon>
              <div class="el-upload__text">
                {{ $t('page.codonw.dragGenomeFile') }}<em>{{ $t('page.codonw.clickUpload') }}</em>
              </div>
              <template #tip>
                <div class="el-upload__tip">
                  {{ $t('page.codonw.genomeFileFormats') }}
                </div>
              </template>
            </el-upload>
          </div>

          <div class="upload-item">
            <h4>{{ $t('page.codonw.annotationFile') }} <span class="required">{{ $t('page.codonw.required') }}</span></h4>
            <el-upload
              ref="gffUploadRef"
              class="upload-demo"
              drag
              :action="uploadUrl"
              :headers="uploadHeaders"
              :data="getGffUploadData"
              :on-success="handleGffUploadSuccess"
              :on-error="handleUploadError"
              :on-progress="handleUploadProgress"
              :before-upload="beforeGffUpload"
              :on-change="handleGffFileChange"
              :file-list="gffFileList"
              accept=".gff,.gff3"
              :auto-upload="false"
            >
              <el-icon class="el-icon--upload"><upload-filled /></el-icon>
              <div class="el-upload__text">
                {{ $t('page.codonw.dragAnnotationFile') }}<em>{{ $t('page.codonw.clickUpload') }}</em>
              </div>
              <template #tip>
                <div class="el-upload__tip">
                  {{ $t('page.codonw.annotationFileFormats') }}
                </div>
              </template>
            </el-upload>
          </div>
        </div>

        <div class="upload-actions" v-if="genomeFileList.length > 0 && gffFileList.length > 0">
          <el-button type="primary" @click="submitGenomicAnalysis" :loading="uploading">
            <el-icon><Upload /></el-icon>
            {{ $t('page.codonw.startGenomicAnalysis') }}
          </el-button>
          <el-button @click="clearGenomicFiles">{{ $t('page.codonw.clearFiles') }}</el-button>
        </div>
      </el-card>
    </div>

    <!-- CDS分析上传区域 -->
    <div class="upload-section" v-if="analysisType === 'cds'">
      <el-card>
        <template #header>
          <span>{{ $t('page.codonw.cdsFileUpload') }}</span>
        </template>

        <el-upload
          ref="cdsUploadRef"
          class="upload-demo"
          drag
          :action="uploadUrl"
          :headers="uploadHeaders"
          :data="cdsUploadData"
          :on-success="handleCdsUploadSuccess"
          :on-error="handleUploadError"
          :on-progress="handleUploadProgress"
          :before-upload="beforeCdsUpload"
          :on-change="handleCdsFileChange"
          :file-list="cdsFileList"
          accept=".fasta,.fa,.fas,.fna,.txt"
          :auto-upload="false"
        >
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">
            {{ $t('page.codonw.dragCdsFile') }}<em>{{ $t('page.codonw.clickUpload') }}</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">
              {{ $t('page.codonw.cdsFileFormats') }}
            </div>
          </template>
        </el-upload>

        <div class="upload-actions" v-if="cdsFileList.length > 0">
          <el-button type="primary" @click="submitCdsAnalysis" :loading="uploading">
            <el-icon><Upload /></el-icon>
            {{ $t('page.codonw.startCdsAnalysis') }}
          </el-button>
          <el-button @click="clearCdsFiles">{{ $t('page.codonw.clearFiles') }}</el-button>
        </div>
      </el-card>
    </div>

    <!-- 分析进度 -->
    <div class="progress-section" v-if="analyzing">
      <el-card>
        <template #header>
          <span>{{ $t('page.codonw.analysisProgress') }}</span>
        </template>
        <el-progress 
          :percentage="analysisProgress" 
          :status="analysisStatus"
          :stroke-width="8"
        />
        <p class="progress-text">{{ progressText }}</p>
      </el-card>
    </div>

    <!-- 分析历史 -->
    <div class="history-section">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>
              {{ $t('page.codonw.analysisHistory') }}
              <el-tooltip
                :content="$t('page.codonw.historyTooltip')"
                placement="top"
                effect="dark"
              >
                <el-icon style="margin-left: 8px; color: #909399; cursor: help;">
                  <InfoFilled />
                </el-icon>
              </el-tooltip>
            </span>
            <el-button size="small" @click="fetchAnalysisHistory">
              <el-icon><Refresh /></el-icon>
              {{ $t('page.codonw.refresh') }}
            </el-button>
          </div>
        </template>

        <el-table
          :data="analysisHistory"
          v-loading="loadingHistory"
          stripe
          style="width: 100%"
        >
          <el-table-column prop="id" :label="$t('page.codonw.taskId')" width="100" />
          <el-table-column prop="filename" :label="$t('page.codonw.fileName')" min-width="200" />
          <el-table-column prop="status" :label="$t('page.codonw.status')" width="120">
            <template #default="scope">
              <el-tag 
                :type="getStatusType(scope.row.status)"
                size="small"
              >
                {{ getStatusText(scope.row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" :label="$t('page.codonw.submitTime')" width="180">
            <template #default="scope">
              {{ formatTime(scope.row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column prop="completed_at" :label="$t('page.codonw.completionTime')" width="180">
            <template #default="scope">
              {{ scope.row.completed_at ? formatTime(scope.row.completed_at) : '-' }}
            </template>
          </el-table-column>
          <el-table-column :label="$t('page.codonw.operations')" width="300">
            <template #default="scope">
              <el-button-group>
                <el-button 
                  size="small" 
                  type="primary"
                  :disabled="scope.row.status !== 'completed'"
                  @click="downloadResults(scope.row)"
                >
                  <el-icon><Download /></el-icon>
                  {{ $t('page.codonw.downloadResults') }}
                </el-button>
                <el-button 
                  size="small" 
                  type="success"
                  :disabled="scope.row.status !== 'completed'"
                  @click="viewDetails(scope.row)"
                >
                  <el-icon><View /></el-icon>
                  {{ $t('page.codonw.viewDetails') }}
                </el-button>
                <el-button 
                  size="small" 
                  type="danger"
                  @click="deleteAnalysis(scope.row)"
                >
                  <el-icon><Delete /></el-icon>
                  {{ $t('page.codonw.delete') }}
                </el-button>
              </el-button-group>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-wrapper" v-if="total > 0">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50, 100]"
            :total="total"
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="handleSizeChange"
            @current-change="handleCurrentChange"
          />
        </div>
      </el-card>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { ElMessage, ElMessageBox } from 'element-plus';
import {
  Refresh,
  UploadFilled,
  Upload,
  Download,
  View,
  Delete,
  InfoFilled
} from '@element-plus/icons-vue';
import axios from 'axios';

export default {
  name: 'CodonWTool',
  components: {
    Refresh,
    UploadFilled,
    Upload,
    Download,
    View,
    Delete,
    InfoFilled
  },
  setup() {
    const router = useRouter();
    const { t } = useI18n();

    // 响应式数据
    const analysisType = ref('genomic'); // 'genomic' 或 'cds'

    // 基因组分析相关
    const genomeUploadRef = ref(null);
    const gffUploadRef = ref(null);
    const genomeFileList = ref([]);
    const gffFileList = ref([]);

    // CDS分析相关
    const cdsUploadRef = ref(null);
    const cdsFileList = ref([]);

    // 通用状态
    const uploading = ref(false);
    const analyzing = ref(false);
    const analysisProgress = ref(0);
    const analysisStatus = ref('');
    const progressText = ref('');
    const analysisHistory = ref([]);
    const loadingHistory = ref(false);
    const currentPage = ref(1);
    const pageSize = ref(10);
    const total = ref(0);

    // 客户端ID管理
    const getClientId = () => {
      let clientId = localStorage.getItem('codonw_client_id');
      if (!clientId) {
        clientId = 'client_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        localStorage.setItem('codonw_client_id', clientId);
      }
      return clientId;
    };

    // 上传配置
    const uploadUrl = computed(() => {
      // Element Plus的上传组件需要完整的URL，不会自动使用axios的baseURL
      const fullUrl = axios.defaults.baseURL + '/files/codonw/analysis/';
      console.log('上传完整URL:', fullUrl);
      return fullUrl;
    });
    const uploadHeaders = computed(() => {
      const headers = {
        'X-CSRFToken': getCsrfToken(),
        'X-Client-ID': getClientId()
      };
      console.log('上传头部:', headers);
      return headers;
    });

    // 基因组分析上传数据
    const genomeUploadData = computed(() => ({
      client_id: getClientId(),
      analysis_type: 'genomic',
      file_type: 'genome'
    }));

    const gffUploadData = computed(() => ({
      client_id: getClientId(),
      analysis_type: 'genomic',
      file_type: 'gff'
    }));

    // 动态获取GFF上传数据，包含task_id
    const getGffUploadData = () => ({
      client_id: getClientId(),
      analysis_type: 'genomic',
      file_type: 'gff',
      task_id: genomicAnalysisState.taskId
    });

    // CDS分析上传数据
    const cdsUploadData = computed(() => ({
      client_id: getClientId(),
      analysis_type: 'cds',
      file_type: 'cds'
    }));

    // 获取CSRF Token
    const getCsrfToken = () => {
      // 首先尝试从meta标签获取
      const metaToken = document.querySelector('meta[name="csrf-token"]');
      if (metaToken) {
        return metaToken.getAttribute('content');
      }

      // 然后尝试从cookie获取
      const cookies = document.cookie.split(';');
      for (let cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'csrftoken') {
          return value;
        }
      }

      console.warn('未找到CSRF token');
      return '';
    };

    // 刷新页面
    const refreshPage = () => {
      window.location.reload();
    };

    // 分析方式变化处理
    const handleAnalysisTypeChange = (value) => {
      console.log('分析方式变化:', value);
      // 清空所有文件列表
      clearAllFiles();
    };

    // 基因组文件变化处理
    const handleGenomeFileChange = (file, fileListParam) => {
      console.log('基因组文件变化:', file, fileListParam);
      // 只保留最新的文件，实现覆盖效果
      if (fileListParam.length > 1) {
        ElMessage.info(t('page.codonw.newFileReplaced', { type: t('page.codonw.genomeFileType') }));
        genomeFileList.value = [fileListParam[fileListParam.length - 1]];
      } else {
        genomeFileList.value = fileListParam;
      }
    };

    const handleGffFileChange = (file, fileListParam) => {
      console.log('GFF文件变化:', file, fileListParam);
      // 只保留最新的文件，实现覆盖效果
      if (fileListParam.length > 1) {
        ElMessage.info(t('page.codonw.newFileReplaced', { type: t('page.codonw.annotationFileType') }));
        gffFileList.value = [fileListParam[fileListParam.length - 1]];
      } else {
        gffFileList.value = fileListParam;
      }
    };

    const handleCdsFileChange = (file, fileListParam) => {
      console.log('CDS文件变化:', file, fileListParam);
      // 只保留最新的文件，实现覆盖效果
      if (fileListParam.length > 1) {
        ElMessage.info(t('page.codonw.newFileReplaced', { type: t('page.codonw.cdsFileType') }));
        cdsFileList.value = [fileListParam[fileListParam.length - 1]];
      } else {
        cdsFileList.value = fileListParam;
      }
    };

    // 文件上传前检查
    const beforeGenomeUpload = (file) => {
      console.log('基因组文件上传前检查:', file);
      const isValidType = ['fasta', 'fa', 'fas', 'fna'].some(ext =>
        file.name.toLowerCase().endsWith('.' + ext)
      );
      const isLt10G = file.size / 1024 / 1024 / 1024 < 10;

      if (!isValidType) {
        ElMessage.error(t('page.codonw.uploadGenomeFileError'));
        return false;
      }
      if (!isLt10G) {
        ElMessage.error(t('page.codonw.fileSizeError'));
        return false;
      }
      return true;
    };

    const beforeGffUpload = (file) => {
      console.log('GFF文件上传前检查:', file);
      const isValidType = ['gff', 'gff3'].some(ext =>
        file.name.toLowerCase().endsWith('.' + ext)
      );
      const isLt10G = file.size / 1024 / 1024 / 1024 < 10;

      if (!isValidType) {
        ElMessage.error(t('page.codonw.uploadAnnotationFileError'));
        return false;
      }
      if (!isLt10G) {
        ElMessage.error(t('page.codonw.fileSizeError'));
        return false;
      }
      return true;
    };

    const beforeCdsUpload = (file) => {
      console.log('CDS文件上传前检查:', file);
      const isValidType = ['fasta', 'fa', 'fas', 'fna', 'txt'].some(ext =>
        file.name.toLowerCase().endsWith('.' + ext)
      );
      const isLt10G = file.size / 1024 / 1024 / 1024 < 10;

      if (!isValidType) {
        ElMessage.error(t('page.codonw.uploadCdsFileError'));
        return false;
      }
      if (!isLt10G) {
        ElMessage.error(t('page.codonw.fileSizeError'));
        return false;
      }
      return true;
    };

    // 提交分析
    const submitGenomicAnalysis = () => {
      if (genomeFileList.value.length === 0 || gffFileList.value.length === 0) {
        ElMessage.warning(t('page.codonw.uploadBothFilesWarning'));
        return;
      }

      uploading.value = true;
      console.log('开始基因组分析...');

      // 先上传基因组文件，然后上传GFF文件
      genomeUploadRef.value.submit();
    };

    const submitCdsAnalysis = () => {
      if (cdsFileList.value.length === 0) {
        ElMessage.warning(t('page.codonw.selectCdsFileWarning'));
        return;
      }

      uploading.value = true;
      console.log('开始CDS分析...');
      cdsUploadRef.value.submit();
    };

    // 清空文件
    const clearGenomicFiles = () => {
      genomeUploadRef.value?.clearFiles();
      gffUploadRef.value?.clearFiles();
      genomeFileList.value = [];
      gffFileList.value = [];
    };

    const clearCdsFiles = () => {
      cdsUploadRef.value?.clearFiles();
      cdsFileList.value = [];
    };

    const clearAllFiles = () => {
      clearGenomicFiles();
      clearCdsFiles();
    };

    // 上传进度
    const handleUploadProgress = (event, file) => {
      console.log('上传进度:', event, file);
      uploading.value = true;
    };

    // 基因组分析上传成功处理
    let genomicAnalysisState = {
      genomeUploaded: false,
      gffUploaded: false,
      taskId: null
    };

    const handleGenomeUploadSuccess = (response) => {
      console.log('基因组文件上传成功:', response);
      genomicAnalysisState.genomeUploaded = true;

      if (response && response.task_id) {
        genomicAnalysisState.taskId = response.task_id;
      }

      // 如果基因组文件上传成功，继续上传GFF文件
      if (gffFileList.value.length > 0) {
        console.log('准备上传GFF文件，task_id:', genomicAnalysisState.taskId);
        gffUploadRef.value.submit();
      }
    };

    const handleGffUploadSuccess = (response) => {
      console.log('GFF文件上传成功:', response);
      genomicAnalysisState.gffUploaded = true;

      // 如果两个文件都上传成功，开始分析
      if (genomicAnalysisState.genomeUploaded && genomicAnalysisState.gffUploaded) {
        uploading.value = false;
        analyzing.value = true;
        analysisProgress.value = 0;
        progressText.value = t('page.codonw.genomicAnalysisStarted');

        ElMessage.success(t('page.codonw.uploadSuccessGenomicAnalysis'));

        // 开始轮询分析状态
        if (genomicAnalysisState.taskId) {
          pollAnalysisStatus(genomicAnalysisState.taskId);
        } else if (response && response.task_id) {
          pollAnalysisStatus(response.task_id);
        } else {
          ElMessage.error(t('page.codonw.serverResponseError'));
          analyzing.value = false;
        }

        // 刷新历史记录
        fetchAnalysisHistory();

        // 清空文件列表和状态
        clearGenomicFiles();
        genomicAnalysisState = { genomeUploaded: false, gffUploaded: false, taskId: null };
      }
    };

    const handleCdsUploadSuccess = (response) => {
      console.log('CDS文件上传成功:', response);
      uploading.value = false;
      analyzing.value = true;
      analysisProgress.value = 0;
      progressText.value = t('page.codonw.cdsAnalysisStarted');

      ElMessage.success(t('page.codonw.uploadSuccessCdsAnalysis'));

      // 开始轮询分析状态
      if (response && response.task_id) {
        pollAnalysisStatus(response.task_id);
      } else {
        ElMessage.error(t('page.codonw.serverResponseError'));
        analyzing.value = false;
      }

      // 刷新历史记录
      fetchAnalysisHistory();

      // 清空文件列表
      clearCdsFiles();
    };

    // 上传失败
    const handleUploadError = (error) => {
      console.error('上传失败:', error);
      uploading.value = false;

      ElMessage.error(t('page.codonw.uploadFailedError'));
    };

    // 轮询分析状态
    const pollAnalysisStatus = (taskId) => {
      const poll = async () => {
        try {
          const response = await axios.get(`/files/codonw/status/${taskId}/`);
          const { status, progress, message } = response.data;

          analysisProgress.value = progress || 0;
          progressText.value = message || t('page.codonw.analysisStarted');

          if (status === 'completed') {
            analyzing.value = false;
            analysisStatus.value = 'success';
            progressText.value = t('page.codonw.analysisCompleted');
            ElMessage.success(t('page.codonw.analysisCompleted'));
            fetchAnalysisHistory();
          } else if (status === 'failed') {
            analyzing.value = false;
            analysisStatus.value = 'exception';
            progressText.value = t('page.codonw.analysisFailed', { message });
            ElMessage.error(t('page.codonw.analysisFailed', { message }));
            fetchAnalysisHistory();
          } else {
            // 继续轮询
            setTimeout(poll, 2000);
          }
        } catch (error) {
          console.error('轮询状态失败:', error);
          setTimeout(poll, 5000); // 出错时延长轮询间隔
        }
      };
      poll();
    };

    // 获取分析历史
    const fetchAnalysisHistory = async () => {
      try {
        loadingHistory.value = true;
        const response = await axios.get('/files/codonw/history/', {
          params: {
            page: currentPage.value,
            page_size: pageSize.value,
            client_id: getClientId()
          }
        });

        analysisHistory.value = response.data.results || [];
        total.value = response.data.count || 0;
      } catch (error) {
        console.error('获取分析历史失败:', error);
        ElMessage.error(t('page.codonw.getHistoryFailed'));
      } finally {
        loadingHistory.value = false;
      }
    };

    // 状态类型映射
    const getStatusType = (status) => {
      const statusMap = {
        'pending': 'info',
        'running': 'warning',
        'completed': 'success',
        'failed': 'danger'
      };
      return statusMap[status] || 'info';
    };

    // 状态文本映射
    const getStatusText = (status) => {
      const statusMap = {
        'pending': t('page.codonw.statusPending'),
        'running': t('page.codonw.statusRunning'),
        'completed': t('page.codonw.statusCompleted'),
        'failed': t('page.codonw.statusFailed')
      };
      return statusMap[status] || status;
    };

    // 格式化时间
    const formatTime = (timeStr) => {
      if (!timeStr) return '-';
      return new Date(timeStr).toLocaleString('zh-CN');
    };

    // 下载结果
    const downloadResults = async (row) => {
      try {
        const response = await axios.get(`/files/codonw/download/${row.id}/`, {
          responseType: 'blob'
        });

        // 创建下载链接
        const blob = new Blob([response.data]);
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `codonw_results_${row.id}.zip`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);

        ElMessage.success(t('page.codonw.downloadSuccess'));
      } catch (error) {
        console.error('下载失败:', error);
        ElMessage.error(t('page.codonw.downloadFailed'));
      }
    };

    // 查看详情
    const viewDetails = (row) => {
      // 跳转到codon-card页面，并传递任务ID
      router.push({
        path: '/codon-card',
        query: { taskId: row.id, source: 'codonw-tool' }
      });
    };

    // 删除分析
    const deleteAnalysis = async (row) => {
      try {
        await ElMessageBox.confirm(
          t('page.codonw.confirmDelete'),
          t('page.codonw.confirmDeleteTitle'),
          {
            confirmButtonText: t('page.codonw.confirm'),
            cancelButtonText: t('page.codonw.cancel'),
            type: 'warning',
          }
        );

        await axios.delete(`/files/codonw/delete/${row.id}/`, {
          params: { client_id: getClientId() },
          headers: { 'X-Client-ID': getClientId() }
        });
        ElMessage.success(t('page.codonw.deleteSuccess'));
        fetchAnalysisHistory();
      } catch (error) {
        if (error !== 'cancel') {
          console.error('删除失败:', error);
          if (error.response?.status === 403) {
            ElMessage.error(t('page.codonw.deleteNoPermission'));
          } else {
            ElMessage.error(t('page.codonw.deleteFailed'));
          }
        }
      }
    };

    // 分页处理
    const handleSizeChange = (val) => {
      pageSize.value = val;
      currentPage.value = 1;
      fetchAnalysisHistory();
    };

    const handleCurrentChange = (val) => {
      currentPage.value = val;
      fetchAnalysisHistory();
    };

    // 组件挂载时获取历史记录
    onMounted(() => {
      fetchAnalysisHistory();
    });

    return {
      // 分析类型
      analysisType,
      handleAnalysisTypeChange,

      // 基因组分析
      genomeUploadRef,
      gffUploadRef,
      genomeFileList,
      gffFileList,
      genomeUploadData,
      gffUploadData,
      getGffUploadData,
      handleGenomeFileChange,
      handleGffFileChange,
      beforeGenomeUpload,
      beforeGffUpload,
      submitGenomicAnalysis,
      clearGenomicFiles,
      handleGenomeUploadSuccess,
      handleGffUploadSuccess,

      // CDS分析
      cdsUploadRef,
      cdsFileList,
      cdsUploadData,
      handleCdsFileChange,
      beforeCdsUpload,
      submitCdsAnalysis,
      clearCdsFiles,
      handleCdsUploadSuccess,

      // 通用状态和方法
      uploading,
      analyzing,
      analysisProgress,
      analysisStatus,
      progressText,
      analysisHistory,
      loadingHistory,
      currentPage,
      pageSize,
      total,
      uploadUrl,
      uploadHeaders,
      refreshPage,
      handleUploadProgress,
      handleUploadError,
      pollAnalysisStatus,
      fetchAnalysisHistory,
      getStatusType,
      getStatusText,
      formatTime,
      downloadResults,
      viewDetails,
      deleteAnalysis,
      handleSizeChange,
      handleCurrentChange
    };
  }
};
</script>

<style scoped>
.codonw-tool {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.title {
  margin: 0;
  color: #303133;
}

.tool-description {
  margin-bottom: 20px;
}

.tool-description ul {
  margin: 10px 0;
  padding-left: 20px;
}

.tool-description li {
  margin: 5px 0;
}

.analysis-type-section {
  margin-bottom: 20px;
}

.analysis-type-section .el-radio {
  display: block;
  margin-bottom: 15px;
  margin-right: 0;
}

.radio-content {
  margin-left: 10px;
}

.radio-title {
  font-weight: bold;
  font-size: 16px;
  color: #303133;
  margin-bottom: 5px;
}

.radio-description {
  font-size: 14px;
  color: #606266;
  line-height: 1.4;
}

.upload-section {
  margin-bottom: 20px;
}

.genomic-upload-container {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 20px;
}

.upload-item h4 {
  margin: 0 0 15px 0;
  color: #303133;
  font-size: 16px;
}

.required {
  color: #f56c6c;
}

.upload-actions {
  margin-top: 20px;
  text-align: center;
}

.upload-actions .el-button {
  margin: 0 10px;
}

.progress-section {
  margin-bottom: 20px;
}

.progress-text {
  text-align: center;
  margin-top: 10px;
  color: #606266;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pagination-wrapper {
  margin-top: 20px;
  text-align: center;
}
</style>
