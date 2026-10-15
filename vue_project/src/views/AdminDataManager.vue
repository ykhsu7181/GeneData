<template>
  <div class="admin-data-manager">
    <div class="page-header">
      <h2>{{ $t('page.admin.dataManagement') }}</h2>
      <div class="header-stats">
        <span>{{ $t('page.admin.totalRecords', { count: totalCount }) }}</span>
        <span v-if="tableData.length > 0">
          {{ $t('page.admin.currentPageRecords', { count: tableData.length }) }}
        </span>
        <span v-if="selectedRows.length > 0" class="selected-info">
          {{ $t('page.admin.selectedRecords', { count: selectedRows.length }) }}
        </span>
      </div>
    </div>

    <!-- 操作工具栏 -->
    <div class="toolbar-container">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-select
            v-model="searchAccession"
            :placeholder="$t('page.admin.selectAccession')"
            filterable
            clearable
            style="width: 250px; margin-right: 10px;"
            @change="handleAccessionChange"
            @clear="handleAccessionClear">
            <el-option
              v-for="accession in allAccessionOptions"
              :key="accession"
              :label="accession"
              :value="accession" />
          </el-select>

          <el-select
            v-model="selectedSubPopulations"
            :placeholder="$t('page.admin.selectSubpopulation')"
            multiple
            collapse-tags
            collapse-tags-tooltip
            clearable
            style="width: 300px; margin-right: 10px;"
            @change="handleSubPopulationFilterChange">
            <el-option
              v-for="option in subPopulationOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value" />
          </el-select>

          <el-button @click="resetFilters">
            <el-icon><Refresh /></el-icon>
            {{ $t('page.admin.resetFilters') }}
          </el-button>
        </div>

        <div class="toolbar-right">
          <el-button
            type="danger"
            :disabled="selectedRows.length === 0"
            @click="handleBatchDelete">
            <el-icon><Delete /></el-icon>
            {{ $t('page.admin.batchDelete', { count: selectedRows.length }) }}
          </el-button>
          <el-button type="primary" @click="showAddDialog = true">
            <el-icon><Plus /></el-icon>
            {{ $t('page.admin.addAccession') }}
          </el-button>
          <el-button type="success" @click="handleUpdateData">
            <el-icon><Refresh /></el-icon>
            {{ $t('page.admin.updateData') }}
          </el-button>
        </div>
      </div>
    </div>

    <!-- 数据表格 -->
    <el-table
      :data="tableData"
      v-loading="loading"
      border
      stripe
      style="width: 100%"
      :header-cell-style="{ background: '#f0f5ff', color: '#1a56db', fontWeight: 'bold' }"
      @selection-change="handleSelectionChange">

      <!-- 多选框列 -->
      <el-table-column type="selection" width="55" fixed="left" />

      <el-table-column prop="accession" label="Accession" width="150" fixed="left" />
      <el-table-column prop="subPopulation" label="SubPopulation" width="150" />
      <el-table-column prop="seqData" label="SeqData" width="400">
        <template #default="scope">
          <a v-if="scope.row.seqData && scope.row.seqData !== '-'" 
             :href="scope.row.seqData" 
             target="_blank" 
             class="data-link">
            {{ scope.row.seqData }}
          </a>
          <span v-else class="data-empty">-</span>
        </template>
      </el-table-column>
      <el-table-column prop="longitude" label="Longitude" width="100" />
      <el-table-column prop="latitude" label="Latitude" width="100" />

      <!-- 文件显示列 -->
      <el-table-column label="Genome" width="150">
        <template #default="scope">
          <span v-if="scope.row.genomeFile"
                class="file-link"
                @click="downloadFile(scope.row.accession, 'genome')"
                :title="scope.row.genomeFile">
            {{ scope.row.genomeFile }}
          </span>
          <span v-else class="file-empty">-</span>
        </template>
      </el-table-column>

      <el-table-column label="Annotation" width="150">
        <template #default="scope">
          <span v-if="scope.row.annotationFile"
                class="file-link"
                @click="downloadFile(scope.row.accession, 'annotation')"
                :title="scope.row.annotationFile">
            {{ scope.row.annotationFile }}
          </span>
          <span v-else class="file-empty">-</span>
        </template>
      </el-table-column>



      <el-table-column label="Codon" width="150">
        <template #default="scope">
          <span v-if="scope.row.codonFile"
                class="file-link"
                @click="downloadFile(scope.row.accession, 'codon')"
                :title="scope.row.codonFile">
            {{ scope.row.codonFile }}
          </span>
          <span v-else class="file-empty">-</span>
        </template>
      </el-table-column>

      <el-table-column label="Centromere" width="150">
        <template #default="scope">
          <span v-if="scope.row.centromereFile"
                class="file-link"
                @click="downloadFile(scope.row.accession, 'centromere')"
                :title="scope.row.centromereFile">
            {{ scope.row.centromereFile }}
          </span>
          <span v-else class="file-empty">-</span>
        </template>
      </el-table-column>

      <el-table-column label="TEs" width="150">
        <template #default="scope">
          <span v-if="scope.row.tesFile"
                class="file-link"
                @click="downloadFile(scope.row.accession, 'TEs')"
                :title="scope.row.tesFile">
            {{ scope.row.tesFile }}
          </span>
          <span v-else class="file-empty">-</span>
        </template>
      </el-table-column>

      <el-table-column label="CoreBlocks" width="150">
        <template #default="scope">
          <span v-if="scope.row.coreBlocksFile"
                class="file-link"
                @click="downloadFile(scope.row.accession, 'coreBlocks')"
                :title="scope.row.coreBlocksFile">
            {{ scope.row.coreBlocksFile }}
          </span>
          <span v-else class="file-empty">-</span>
        </template>
      </el-table-column>

      <el-table-column label="miRNA" width="150">
        <template #default="scope">
          <span v-if="scope.row.miRNAFile"
                class="file-link"
                @click="downloadFile(scope.row.accession, 'miRNA')"
                :title="scope.row.miRNAFile">
            {{ scope.row.miRNAFile }}
          </span>
          <span v-else class="file-empty">-</span>
        </template>
      </el-table-column>

      <el-table-column label="tRNA" width="150">
        <template #default="scope">
          <span v-if="scope.row.tRNAFile"
                class="file-link"
                @click="downloadFile(scope.row.accession, 'tRNA')"
                :title="scope.row.tRNAFile">
            {{ scope.row.tRNAFile }}
          </span>
          <span v-else class="file-empty">-</span>
        </template>
      </el-table-column>

      <el-table-column label="rRNA" width="150">
        <template #default="scope">
          <span v-if="scope.row.rRNAFile"
                class="file-link"
                @click="downloadFile(scope.row.accession, 'rRNA')"
                :title="scope.row.rRNAFile">
            {{ scope.row.rRNAFile }}
          </span>
          <span v-else class="file-empty">-</span>
        </template>
      </el-table-column>

      <!-- 转录组相关列 -->
      <el-table-column label="Transcriptome.all" width="150">
        <template #default="scope">
          <span v-if="scope.row.transcriptomeAllFile"
                class="file-link"
                @click="downloadFile(scope.row.accession, 'transcriptome.all')"
                :title="scope.row.transcriptomeAllFile">
            {{ scope.row.transcriptomeAllFile }}
          </span>
          <span v-else class="file-empty">-</span>
        </template>
      </el-table-column>

      <el-table-column label="Transcriptome.leaf" width="150">
        <template #default="scope">
          <span v-if="scope.row.transcriptomeLeafFile"
                class="file-link"
                @click="downloadFile(scope.row.accession, 'transcriptome.leaf')"
                :title="scope.row.transcriptomeLeafFile">
            {{ scope.row.transcriptomeLeafFile }}
          </span>
          <span v-else class="file-empty">-</span>
        </template>
      </el-table-column>

      <el-table-column label="Transcriptome.panicles" width="150">
        <template #default="scope">
          <span v-if="scope.row.transcriptomePaniclesFile"
                class="file-link"
                @click="downloadFile(scope.row.accession, 'transcriptome.panicles')"
                :title="scope.row.transcriptomePaniclesFile">
            {{ scope.row.transcriptomePaniclesFile }}
          </span>
          <span v-else class="file-empty">-</span>
        </template>
      </el-table-column>

      <el-table-column label="Transcriptome.shoot" width="150">
        <template #default="scope">
          <span v-if="scope.row.transcriptomeShootFile"
                class="file-link"
                @click="downloadFile(scope.row.accession, 'transcriptome.shoot')"
                :title="scope.row.transcriptomeShootFile">
            {{ scope.row.transcriptomeShootFile }}
          </span>
          <span v-else class="file-empty">-</span>
        </template>
      </el-table-column>

      <el-table-column label="Transcriptome.stem" width="150">
        <template #default="scope">
          <span v-if="scope.row.transcriptomeStemFile"
                class="file-link"
                @click="downloadFile(scope.row.accession, 'transcriptome.stem')"
                :title="scope.row.transcriptomeStemFile">
            {{ scope.row.transcriptomeStemFile }}
          </span>
          <span v-else class="file-empty">-</span>
        </template>
      </el-table-column>

      <el-table-column label="Transcriptome.root" width="150">
        <template #default="scope">
          <span v-if="scope.row.transcriptomeRootFile"
                class="file-link"
                @click="downloadFile(scope.row.accession, 'transcriptome.root')"
                :title="scope.row.transcriptomeRootFile">
            {{ scope.row.transcriptomeRootFile }}
          </span>
          <span v-else class="file-empty">-</span>
        </template>
      </el-table-column>

      <el-table-column :label="$t('common.actions')" width="150" fixed="right">
        <template #default="scope">
          <el-button type="primary" size="small" @click="editRow(scope.row)">{{ $t('common.edit') }}</el-button>
          <el-button type="danger" size="small" @click="deleteRow(scope.row)">{{ $t('common.delete') }}</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="pagination-container">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[20, 50, 100]"
        :total="totalCount"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>

    <!-- 新增/编辑对话框 - 专业版 -->
    <el-dialog
      v-model="showAddDialog"
      :title="editingRow ? $t('page.admin.editAccession') : $t('page.admin.addAccession')"
      width="900px"
      class="accession-dialog"
      @close="resetForm">
      
      <el-form :model="formData" :rules="formRules" ref="formRef" label-width="140px" class="professional-form">
        <!-- 基本信息卡片 -->
        <el-card class="form-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span class="header-title">{{ $t('common.basicInformation') }}</span>
            </div>
          </template>
          
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="Accession" prop="accession">
                <el-input 
                  v-model="formData.accession" 
                  :disabled="editingRow"
                  :placeholder="$t('page.admin.accessionPlaceholder')"
                  clearable />
                <div class="field-hint">{{ editingRow ? $t('page.admin.accessionImmutable') : $t('page.admin.accessionRequiredHint') }}</div>
              </el-form-item>
            </el-col>
            
            <el-col :span="12">
              <el-form-item label="SubPopulation" prop="subPopulation">
                <el-select
                  v-model="formData.subPopulation"
                  :placeholder="$t('page.admin.subpopulationPlaceholder')"
                  filterable
                  allow-create
                  default-first-option
                  :reserve-keyword="false"
                  style="width: 100%"
                  @change="handleSubPopulationChange">
                  <el-option
                    v-for="option in subPopulationOptions"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value" />
                </el-select>
                <div class="field-hint">{{ $t('page.admin.subpopulationHint') }}</div>
              </el-form-item>
            </el-col>
          </el-row>
          
          <el-row :gutter="20">
            <el-col :span="24">
              <el-form-item label="SeqData URL" prop="seqData">
                <el-input 
                  v-model="formData.seqData" 
                  :placeholder="$t('page.admin.seqDataPlaceholder')"
                  clearable />
                <div class="field-hint">{{ $t('page.admin.optionalHint') }}</div>
              </el-form-item>
            </el-col>
          </el-row>
          
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item :label="$t('page.admin.longitude')" prop="longitude">
                <el-input-number 
                  v-model="formData.longitude" 
                  :precision="6"
                  :min="-180"
                  :max="180"
                  :step="0.1"
                  controls-position="right"
                  style="width: 100%"
                  placeholder="-180 ~ 180" />
              </el-form-item>
            </el-col>
            
            <el-col :span="12">
              <el-form-item :label="$t('page.admin.latitude')" prop="latitude">
                <el-input-number 
                  v-model="formData.latitude" 
                  :precision="6"
                  :min="-90"
                  :max="90"
                  :step="0.1"
                  controls-position="right"
                  style="width: 100%"
                  placeholder="-90 ~ 90" />
              </el-form-item>
            </el-col>
          </el-row>
        </el-card>

        <!-- 文件管理卡片 -->
        <el-card class="form-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span class="header-title">{{ $t('page.admin.fileManagement') }}</span>
            </div>
          </template>

          <!-- 基因组文件组 -->
          <div class="file-group">
            <div class="file-group-header">
              <span>{{ $t('page.admin.genomeFiles') }}</span>
            </div>
            <el-row :gutter="15">
              <el-col :span="12">
                <div class="file-field">
                  <div class="file-label">
                    <span class="label-text">Genome</span>
                    <el-tag v-if="formData.files.genome" size="small" type="success">{{ $t('page.admin.uploaded') }}</el-tag>
                    <el-tag v-else size="small" type="info">{{ $t('page.admin.notUploaded') }}</el-tag>
                  </div>
                  <div class="file-content">
                    <span v-if="formData.files.genome" class="file-name" :title="formData.files.genome">{{ formData.files.genome }}</span>
                    <span v-else class="no-file-text">{{ $t('page.admin.noFileSelected') }}</span>
                  </div>
                  <div class="file-actions">
                    <el-button size="small" type="primary" @click="selectFile('genome')">{{ $t('common.select') }}</el-button>
                    <el-button v-if="formData.files.genome" size="small" type="danger" plain @click="removeFile('genome')">{{ $t('common.delete') }}</el-button>
                  </div>
                  <div class="file-format-hint">.fasta / .fa / .fas</div>
                </div>
              </el-col>
              
              <el-col :span="12">
                <div class="file-field">
                  <div class="file-label">
                    <span class="label-text">Annotation</span>
                    <el-tag v-if="formData.files.annotation" size="small" type="success">{{ $t('page.admin.uploaded') }}</el-tag>
                    <el-tag v-else size="small" type="info">{{ $t('page.admin.notUploaded') }}</el-tag>
                  </div>
                  <div class="file-content">
                    <span v-if="formData.files.annotation" class="file-name" :title="formData.files.annotation">{{ formData.files.annotation }}</span>
                    <span v-else class="no-file-text">{{ $t('page.admin.noFileSelected') }}</span>
                  </div>
                  <div class="file-actions">
                    <el-button size="small" type="primary" @click="selectFile('annotation')">{{ $t('common.select') }}</el-button>
                    <el-button v-if="formData.files.annotation" size="small" type="danger" plain @click="removeFile('annotation')">{{ $t('common.delete') }}</el-button>
                  </div>
                  <div class="file-format-hint">.gff / .gff3</div>
                </div>
              </el-col>
            </el-row>
          </div>

          <!-- 转录组文件组 -->
          <div class="file-group">
            <div class="file-group-header">
              <span>{{ $t('page.admin.transcriptomeFiles') }}</span>
            </div>
            <el-row :gutter="15">
              <el-col :span="8" v-for="transcriptType in transcriptomeTypes" :key="transcriptType.key">
                <div class="file-field compact">
                  <div class="file-label">
                    <span class="label-text">{{ transcriptType.label }}</span>
                    <el-tag v-if="formData.files[transcriptType.key]" size="small" type="success">{{ $t('page.admin.uploaded') }}</el-tag>
                    <el-tag v-else size="small" type="info">{{ $t('page.admin.notUploaded') }}</el-tag>
                  </div>
                  <div class="file-content compact">
                    <span v-if="formData.files[transcriptType.key]" class="file-name" :title="formData.files[transcriptType.key]">{{ formData.files[transcriptType.key] }}</span>
                    <span v-else class="no-file-text">{{ $t('page.admin.noSelection') }}</span>
                  </div>
                  <div class="file-actions">
                    <el-button size="small" type="primary" plain @click="selectFile(transcriptType.key)">{{ $t('common.select') }}</el-button>
                    <el-button v-if="formData.files[transcriptType.key]" size="small" type="danger" plain @click="removeFile(transcriptType.key)">{{ $t('common.delete') }}</el-button>
                  </div>
                  <div class="file-format-hint">.tar.gz</div>
                </div>
              </el-col>
            </el-row>
          </div>

          <!-- 其他文件组 -->
          <div class="file-group">
            <div class="file-group-header">
              <span>{{ $t('page.admin.otherFiles') }}</span>
            </div>
            <el-row :gutter="15">
              <el-col :span="8" v-for="otherType in otherFileTypes" :key="otherType.key">
                <div class="file-field compact">
                  <div class="file-label">
                    <span class="label-text">{{ otherType.label }}</span>
                    <el-tag v-if="formData.files[otherType.key]" size="small" type="success">{{ $t('page.admin.uploaded') }}</el-tag>
                    <el-tag v-else size="small" type="info">{{ $t('page.admin.notUploaded') }}</el-tag>
                  </div>
                  <div class="file-content compact">
                    <span v-if="formData.files[otherType.key]" class="file-name" :title="formData.files[otherType.key]">{{ formData.files[otherType.key] }}</span>
                    <span v-else class="no-file-text">{{ $t('page.admin.noSelection') }}</span>
                  </div>
                  <div class="file-actions">
                    <el-button size="small" type="primary" plain @click="selectFile(otherType.key)">{{ $t('common.select') }}</el-button>
                    <el-button v-if="formData.files[otherType.key]" size="small" type="danger" plain @click="removeFile(otherType.key)">{{ $t('common.delete') }}</el-button>
                  </div>
                  <div class="file-format-hint">{{ otherType.format }}</div>
                </div>
              </el-col>
            </el-row>
          </div>
        </el-card>
      </el-form>
      
      <template #footer>
        <div class="dialog-footer-professional">
          <div class="footer-hint">{{ $t('page.admin.uploadAfterSave') }}</div>
          <div class="footer-actions">
            <el-button @click="showAddDialog = false">{{ $t('common.cancel') }}</el-button>
            <el-button type="primary" @click="saveData" :loading="saving">{{ saving ? $t('page.admin.saving') : $t('common.save') }}</el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Delete } from '@element-plus/icons-vue'
import axios from 'axios'
import { useI18n } from 'vue-i18n'

export default {
  name: 'AdminDataManager',
  components: {
    Plus,
    Refresh,
    Delete
  },
  setup() {
    const { t } = useI18n()
    const loading = ref(false)
    const saving = ref(false)
    const tableData = ref([])
    const currentPage = ref(1)
    const pageSize = ref(20)
    const totalCount = ref(0)

    const showAddDialog = ref(false)
    const editingRow = ref(null)
    const formRef = ref(null)

    // 搜索和筛选相关
    const searchAccession = ref('')
    const selectedSubPopulations = ref([])
    const allAccessionOptions = ref([])
    const loadingAccessions = ref(false)

    // 多选相关
    const selectedRows = ref([])

    const subPopulationOptions = ref([
      { label: 'cA', value: 'cA' },
      { label: 'cB', value: 'cB' },
      { label: 'GJ', value: 'GJ' },
      { label: 'XI', value: 'XI' },
      { label: 'WILD', value: 'WILD' },
      { label: 'O.glaberrima', value: 'O.glaberrima' },
      { label: t('page.admin.unknown'), value: '-' }
    ])

    // 转录组文件类型
    const transcriptomeTypes = ref([
      { key: 'transcriptomeAll', label: 'All' },
      { key: 'transcriptomeLeaf', label: 'Leaf' },
      { key: 'transcriptomePanicles', label: 'Panicles' },
      { key: 'transcriptomeShoot', label: 'Shoot' },
      { key: 'transcriptomeStem', label: 'Stem' },
      { key: 'transcriptomeRoot', label: 'Root' }
    ])

    // 其他文件类型
    const otherFileTypes = ref([
      { key: 'codon', label: 'Codon', format: '.tar.gz' },
      { key: 'centromere', label: 'Centromere', format: '.bed' },
      { key: 'TEs', label: 'TEs', format: '.tar.gz' },
      { key: 'coreBlocks', label: 'CoreBlocks', format: '.bed' },
      { key: 'miRNA', label: 'miRNA', format: '.bed' },
      { key: 'tRNA', label: 'tRNA', format: '.bed' },
      { key: 'rRNA', label: 'rRNA', format: '.bed' }
    ])
    
    const formData = reactive({
      accession: '',
      subPopulation: '',
      seqData: '',
      longitude: null,
      latitude: null,
      files: {
        genome: '',
        annotation: '',
        transcriptomeAll: '',
        transcriptomeLeaf: '',
        transcriptomePanicles: '',
        transcriptomeShoot: '',
        transcriptomeStem: '',
        transcriptomeRoot: '',
        codon: '',
        centromere: '',
        TEs: '',
        coreBlocks: '',
        miRNA: '',
        tRNA: '',
        rRNA: ''
      },
      filesToUpload: {} // 存储待上传的文件
    })
    
    const formRules = {
      accession: [
        { required: true, message: t('page.admin.accessionRequired'), trigger: 'blur' }
      ]
    }

    // 加载亚群选项
    const loadSubPopulationOptions = async () => {
      try {
        const response = await axios.get('/admin/data-management/list/', {
          params: { page: 1, page_size: 1000 } // 获取所有数据来提取亚群
        })

        if (response.data.success && response.data.data) {
          // 提取所有唯一的亚群
          const existingSubPopulations = new Set()
          response.data.data.forEach(item => {
            if (item.subPopulation && item.subPopulation !== '-') {
              existingSubPopulations.add(item.subPopulation)
            }
          })

          // 合并默认选项和已存在的亚群
          const defaultOptions = [
            { label: 'cA', value: 'cA' },
            { label: 'cB', value: 'cB' },
            { label: 'GJ', value: 'GJ' },
            { label: 'XI', value: 'XI' },
            { label: 'WILD', value: 'WILD' },
            { label: 'O.glaberrima', value: 'O.glaberrima' },
            { label: t('page.admin.unknown'), value: '-' }
          ]

          const defaultValues = new Set(defaultOptions.map(opt => opt.value))
          const additionalOptions = Array.from(existingSubPopulations)
            .filter(value => !defaultValues.has(value))
            .map(value => ({ label: value, value: value }))

          subPopulationOptions.value = [...defaultOptions, ...additionalOptions]
        }
      } catch (error) {
        console.error('加载亚群选项失败:', error)
      }
    }

    // 加载数据
    const loadData = async () => {
      try {
        loading.value = true
        const params = {
          page: currentPage.value,
          page_size: pageSize.value
        }

        // 添加搜索参数
        if (searchAccession.value) {
          params.search = searchAccession.value
        }

        // 添加亚群筛选参数
        if (selectedSubPopulations.value.length > 0) {
          params.sub_populations = selectedSubPopulations.value.join(',')
        }

        const response = await axios.get('/admin/data-management/list/', { params })
        const data = response.data

        if (data.success) {
          tableData.value = data.data || []
          totalCount.value = data.total || 0

          // 调试信息：检查第一条记录的文件状态
          if (data.data && data.data.length > 0) {
            console.log('第一条记录的文件状态:', data.data[0])
          }
        } else {
          throw new Error(data.message || '获取数据失败')
        }

      } catch (error) {
        console.error('加载数据失败:', error)
        ElMessage.error(t('page.admin.dataLoadFailed'))
      } finally {
        loading.value = false
      }
    }

    // 刷新数据
    const refreshData = () => {
      loadData()
    }

    // 处理亚群变化（表单中的）
    const handleSubPopulationChange = (value) => {
      // 如果是新输入的亚群，添加到选项列表中
      if (value && !subPopulationOptions.value.find(opt => opt.value === value)) {
        subPopulationOptions.value.push({
          label: value,
          value: value
        })
      }
    }

    // 加载所有Accession选项
    const loadAllAccessions = async () => {
      try {
        loadingAccessions.value = true
        const response = await axios.get('/admin/data-management/list/', {
          params: {
            page: 1,
            page_size: 1000  // 获取所有数据
          }
        })

        if (response.data.success) {
          allAccessionOptions.value = response.data.data.map(item => item.accession).sort()
        }
      } catch (error) {
        console.error('加载Accession选项失败:', error)
      } finally {
        loadingAccessions.value = false
      }
    }

    // 处理Accession选择变化
    const handleAccessionChange = (value) => {
      searchAccession.value = value
      currentPage.value = 1
      loadData()
    }

    // 清除Accession搜索
    const handleAccessionClear = () => {
      searchAccession.value = ''
      currentPage.value = 1
      loadData()
    }

    // 处理SubPopulation筛选变化
    const handleSubPopulationFilterChange = () => {
      currentPage.value = 1
      loadData()
    }

    // 重置筛选
    const resetFilters = () => {
      searchAccession.value = ''
      selectedSubPopulations.value = []
      currentPage.value = 1
      loadData()
    }

    // 处理表格选择变化
    const handleSelectionChange = (selection) => {
      selectedRows.value = selection
    }

    // 批量删除
    const handleBatchDelete = async () => {
      if (selectedRows.value.length === 0) {
        ElMessage.warning(t('page.admin.selectRecordsToDelete'))
        return
      }

      try {
        const accessions = selectedRows.value.map(row => row.accession)
        const message = t('page.admin.batchRecordDeleteConfirm', { count: accessions.length, accessions: accessions.join(', ') })

        await ElMessageBox.confirm(message, t('page.admin.batchDeleteTitle'), {
          confirmButtonText: t('common.confirm'),
          cancelButtonText: t('common.cancel'),
          type: 'warning',
          dangerouslyUseHTMLString: false
        })

        // 调用批量删除API
        const response = await axios.post('/admin/data-management/batch-delete/', {
          accessions: accessions
        })

        if (response.data.success) {
          ElMessage.success(t('page.admin.recordsDeleted', { count: accessions.length }))
          selectedRows.value = [] // 清空选择
          loadData()
          loadAllAccessions() // 重新加载Accession选项
        } else {
          ElMessage.error(t('page.admin.batchDeleteFailed'))
        }

      } catch (error) {
        if (error !== 'cancel') {
          console.error('批量删除失败:', error)
          ElMessage.error(t('page.admin.batchDeleteFailed'))
        }
      }
    }

    // 更新数据（重新扫描文件）
    const handleUpdateData = async () => {
      try {
        loading.value = true
        const response = await axios.post('/admin/rescan/')

        if (response.data.success) {
          ElMessage.success(t('messages.dataRefreshed'))
          loadData()
        } else {
          ElMessage.error(t('page.admin.dataUpdateFailed'))
        }
      } catch (error) {
        console.error('更新数据失败:', error)
        ElMessage.error(t('page.admin.dataUpdateFailed'))
      } finally {
        loading.value = false
      }
    }

    // 分页处理
    const handleSizeChange = (size) => {
      pageSize.value = size
      currentPage.value = 1
      loadData()
    }

    const handleCurrentChange = (page) => {
      currentPage.value = page
      loadData()
    }

    // 编辑行
    const editRow = (row) => {
      editingRow.value = row
      formData.accession = row.accession
      formData.subPopulation = row.subPopulation || ''
      formData.seqData = row.seqData === '-' ? '' : (row.seqData || '')
      formData.longitude = row.longitude
      formData.latitude = row.latitude

      // 加载文件信息
      formData.files.genome = row.genomeFile || ''
      formData.files.annotation = row.annotationFile || ''
      formData.files.transcriptomeAll = row.transcriptomeAllFile || ''
      formData.files.transcriptomeLeaf = row.transcriptomeLeafFile || ''
      formData.files.transcriptomePanicles = row.transcriptomePaniclesFile || ''
      formData.files.transcriptomeShoot = row.transcriptomeShootFile || ''
      formData.files.transcriptomeStem = row.transcriptomeStemFile || ''
      formData.files.transcriptomeRoot = row.transcriptomeRootFile || ''
      formData.files.codon = row.codonFile || ''
      formData.files.centromere = row.centromereFile || ''
      formData.files.TEs = row.tesFile || ''
      formData.files.coreBlocks = row.coreBlocksFile || ''
      formData.files.miRNA = row.miRNAFile || ''
      formData.files.tRNA = row.tRNAFile || ''
      formData.files.rRNA = row.rRNAFile || ''

      formData.filesToUpload = {} // 清空待上传文件
      showAddDialog.value = true
    }

    // 删除行
    const deleteRow = async (row) => {
      try {
        await ElMessageBox.confirm(
          t('page.admin.recordDeleteConfirm', { accession: row.accession }),
          t('page.admin.deleteConfirmTitle'),
          {
            confirmButtonText: t('common.confirm'),
            cancelButtonText: t('common.cancel'),
            type: 'warning'
          }
        )
        
        // 调用删除API
        await axios.delete(`/admin/data-management/accession/${row.accession}/delete/`)
        
        ElMessage.success(t('page.admin.deleteSuccess'))
        loadData()
        loadAllAccessions() // 重新加载Accession选项
        
      } catch (error) {
        if (error !== 'cancel') {
          console.error('删除失败:', error)
          ElMessage.error(t('page.admin.deleteFailed'))
        }
      }
    }

    // 保存数据
    const saveData = async () => {
      try {
        await formRef.value.validate()

        saving.value = true

        const data = {
          accession: formData.accession,
          subPopulation: formData.subPopulation || '-',
          seqData: formData.seqData || '-',
          longitude: formData.longitude,
          latitude: formData.latitude
        }

        // 先保存基本信息
        if (editingRow.value) {
          // 编辑
          await axios.put(`/admin/data-management/accession/${editingRow.value.accession}/update/`, data)
        } else {
          // 新增
          await axios.post('/admin/data-management/accession/', data)
        }

        // 处理文件上传
        const accession = formData.accession

        // 文件类型映射：前端字段名 -> API参数
        const fileTypeMapping = {
          'genome': 'genome',
          'annotation': 'annotation',
          'transcriptomeAll': 'transcriptome.all',
          'transcriptomeLeaf': 'transcriptome.leaf',
          'transcriptomePanicles': 'transcriptome.panicles',
          'transcriptomeShoot': 'transcriptome.shoot',
          'transcriptomeStem': 'transcriptome.stem',
          'transcriptomeRoot': 'transcriptome.root',
          'codon': 'codon',
          'centromere': 'centromere',
          'TEs': 'TEs',
          'coreBlocks': 'coreBlocks',
          'miRNA': 'miRNA',
          'tRNA': 'tRNA',
          'rRNA': 'rRNA'
        }

        for (const [frontendFileType, file] of Object.entries(formData.filesToUpload)) {
          if (file) {
            try {
              const apiFileType = fileTypeMapping[frontendFileType] || frontendFileType
              const fileFormData = new FormData()
              fileFormData.append('file', file)
              fileFormData.append('accession', accession)
              fileFormData.append('fileType', apiFileType)

              await axios.post('/admin/data-management/upload-file/', fileFormData, {
                headers: {
                  'Content-Type': 'multipart/form-data'
                }
              })
            } catch (fileError) {
              console.error(`文件 ${frontendFileType} 上传失败:`, fileError)
              ElMessage.warning(t('page.admin.fileOperationFailed', { type: frontendFileType }))
            }
          }
        }

        // 处理文件删除（如果文件名被清空但原来有文件）
        if (editingRow.value) {
          const fileTypeMappings = [
            { formKey: 'genome', apiKey: 'genome', originalKey: 'genomeFile' },
            { formKey: 'annotation', apiKey: 'annotation', originalKey: 'annotationFile' },
            { formKey: 'transcriptomeAll', apiKey: 'transcriptome.all', originalKey: 'transcriptomeAllFile' },
            { formKey: 'transcriptomeLeaf', apiKey: 'transcriptome.leaf', originalKey: 'transcriptomeLeafFile' },
            { formKey: 'transcriptomePanicles', apiKey: 'transcriptome.panicles', originalKey: 'transcriptomePaniclesFile' },
            { formKey: 'transcriptomeShoot', apiKey: 'transcriptome.shoot', originalKey: 'transcriptomeShootFile' },
            { formKey: 'transcriptomeStem', apiKey: 'transcriptome.stem', originalKey: 'transcriptomeStemFile' },
            { formKey: 'transcriptomeRoot', apiKey: 'transcriptome.root', originalKey: 'transcriptomeRootFile' },
            { formKey: 'codon', apiKey: 'codon', originalKey: 'codonFile' },
            { formKey: 'centromere', apiKey: 'centromere', originalKey: 'centromereFile' },
            { formKey: 'TEs', apiKey: 'TEs', originalKey: 'tesFile' },
            { formKey: 'coreBlocks', apiKey: 'coreBlocks', originalKey: 'coreBlocksFile' },
            { formKey: 'miRNA', apiKey: 'miRNA', originalKey: 'miRNAFile' },
            { formKey: 'tRNA', apiKey: 'tRNA', originalKey: 'tRNAFile' },
            { formKey: 'rRNA', apiKey: 'rRNA', originalKey: 'rRNAFile' }
          ]

          for (const mapping of fileTypeMappings) {
            const originalFile = editingRow.value[mapping.originalKey]
            const currentFile = formData.files[mapping.formKey]

            // 如果原来有文件，现在没有，且没有新上传的文件，则删除
            if (originalFile && !currentFile && !formData.filesToUpload[mapping.formKey]) {
              try {
                await axios.delete(`/admin/data-management/delete-file/${accession}/${mapping.apiKey}/`)
              } catch (deleteError) {
                console.error(`文件 ${mapping.apiKey} 删除失败:`, deleteError)
              }
            }
          }
        }

        ElMessage.success(editingRow.value ? t('page.admin.updateSuccess') : t('page.admin.createSuccess'))
        showAddDialog.value = false
        loadData()
        loadSubPopulationOptions() // 重新加载亚群选项
        loadAllAccessions() // 重新加载Accession选项

      } catch (error) {
        console.error('保存失败:', error)
        ElMessage.error(t('page.admin.saveFailed'))
      } finally {
        saving.value = false
      }
    }

    // 重置表单
    const resetForm = () => {
      editingRow.value = null
      formData.accession = ''
      formData.subPopulation = ''
      formData.seqData = ''
      formData.longitude = null
      formData.latitude = null

      // 重置文件信息
      formData.files = {
        genome: '',
        annotation: '',
        transcriptomeAll: '',
        transcriptomeLeaf: '',
        transcriptomePanicles: '',
        transcriptomeShoot: '',
        transcriptomeStem: '',
        transcriptomeRoot: '',
        codon: '',
        centromere: '',
        TEs: '',
        coreBlocks: '',
        miRNA: '',
        tRNA: '',
        rRNA: ''
      }
      formData.filesToUpload = {}

      if (formRef.value) {
        formRef.value.clearValidate()
      }
    }

    // 文件选择方法（用于编辑对话框）
    const selectFile = (fileType) => {
      const input = document.createElement('input')
      input.type = 'file'

      // 根据文件类型设置接受的文件格式
      const fileExtensions = {
        'genome': '.fasta,.fa,.fas',
        'annotation': '.gff,.gff3',
        'transcriptomeAll': '.tar.gz',
        'transcriptomeLeaf': '.tar.gz',
        'transcriptomePanicles': '.tar.gz',
        'transcriptomeShoot': '.tar.gz',
        'transcriptomeStem': '.tar.gz',
        'transcriptomeRoot': '.tar.gz',
        'codon': '.tar.gz',
        'centromere': '.bed',
        'TEs': '.tar.gz',
        'coreBlocks': '.bed',
        'miRNA': '.bed',
        'tRNA': '.bed',
        'rRNA': '.bed'
      }

      input.accept = fileExtensions[fileType] || '*'

      input.onchange = (event) => {
        const file = event.target.files[0]
        if (file) {
          formData.files[fileType] = file.name
          formData.filesToUpload[fileType] = file
        }
      }

      input.click()
    }

    // 移除文件方法（用于编辑对话框）
    const removeFile = (fileType) => {
      formData.files[fileType] = ''
      delete formData.filesToUpload[fileType]
    }

    // 文件操作方法（用于表格中的下载）
    const uploadFile = (accession, fileType) => {
      // 创建文件输入元素
      const input = document.createElement('input')
      input.type = 'file'

      // 根据文件类型设置接受的文件格式
      const fileExtensions = {
        'genome': '.fasta,.fa,.fas',
        'annotation': '.gff,.gff3',
        'transcriptome.all': '.tar.gz',
        'transcriptome.leaf': '.tar.gz',
        'transcriptome.panicles': '.tar.gz',
        'transcriptome.shoot': '.tar.gz',
        'transcriptome.stem': '.tar.gz',
        'transcriptome.root': '.tar.gz',
        'codon': '.tar.gz',
        'centromere': '.bed',
        'TEs': '.tar.gz',
        'coreBlocks': '.bed',
        'miRNA': '.bed',
        'tRNA': '.bed',
        'rRNA': '.bed'
      }

      input.accept = fileExtensions[fileType] || '*'

      input.onchange = async (event) => {
        const file = event.target.files[0]
        if (!file) return

        try {
          const formData = new FormData()
          formData.append('file', file)
          formData.append('accession', accession)
          formData.append('fileType', fileType)

          const response = await axios.post('/admin/data-management/upload-file/', formData, {
            headers: {
              'Content-Type': 'multipart/form-data'
            }
          })

          if (response.data.success) {
            ElMessage.success(t('page.admin.fileUploadSuccess', { name: file.name }))
            loadData() // 刷新数据
          } else {
            ElMessage.error(t('page.admin.fileUploadFailed', { name: file.name }))
          }
        } catch (error) {
          console.error('文件上传失败:', error)
          ElMessage.error(t('page.admin.fileUploadFailed', { name: file.name }))
        }
      }

      input.click()
    }

    const downloadFile = async (accession, fileType) => {
      try {
        const response = await axios.get(`/admin/data-management/download-file/${accession}/${fileType}/`, {
          responseType: 'blob'
        })

        // 创建下载链接
        const url = window.URL.createObjectURL(new Blob([response.data]))
        const link = document.createElement('a')
        link.href = url

        // 根据文件类型设置文件名
        const extensions = {
          'genome': 'fasta',
          'annotation': 'gff',
          'transcriptome': 'tar.gz',
          'codon': 'tar.gz',
          'centromere': 'bed',
          'TEs': 'tar.gz',
          'coreBlocks': 'bed',
          'miRNA': 'bed',
          'tRNA': 'bed',
          'rRNA': 'bed'
        }

        link.download = `${fileType}.${accession}.${extensions[fileType]}`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        window.URL.revokeObjectURL(url)

      } catch (error) {
        console.error('文件下载失败:', error)
        ElMessage.error(t('page.admin.fileDownloadFailed'))
      }
    }

    const deleteFile = async (accession, fileType) => {
      try {
        await ElMessageBox.confirm(
          t('page.admin.fileDeleteConfirm', { accession, type: fileType }),
          t('page.admin.deleteConfirmTitle'),
          {
            confirmButtonText: t('common.confirm'),
            cancelButtonText: t('common.cancel'),
            type: 'warning'
          }
        )

        const response = await axios.delete(`/admin/data-management/delete-file/${accession}/${fileType}/`)

        if (response.data.success) {
          ElMessage.success(t('page.admin.fileDeleted', { type: fileType }))
          loadData() // 刷新数据
        } else {
          ElMessage.error(t('page.admin.deleteFailed'))
        }

      } catch (error) {
        if (error !== 'cancel') {
          console.error('文件删除失败:', error)
          ElMessage.error(t('page.admin.fileOperationFailed', { type: fileType }))
        }
      }
    }

    onMounted(() => {
      loadData()
      loadSubPopulationOptions()
      loadAllAccessions()
    })

    return {
      loading,
      saving,
      tableData,
      currentPage,
      pageSize,
      totalCount,
      showAddDialog,
      editingRow,
      formRef,
      formData,
      formRules,
      subPopulationOptions,
      transcriptomeTypes,
      otherFileTypes,
      // 搜索和筛选相关
      searchAccession,
      selectedSubPopulations,
      allAccessionOptions,
      loadingAccessions,
      loadAllAccessions,
      handleAccessionChange,
      handleAccessionClear,
      handleSubPopulationFilterChange,
      handleSubPopulationChange,
      resetFilters,
      // 多选相关
      selectedRows,
      handleSelectionChange,
      handleBatchDelete,
      // 原有方法
      loadData,
      refreshData,
      handleUpdateData,
      handleSizeChange,
      handleCurrentChange,
      editRow,
      deleteRow,
      saveData,
      resetForm,
      selectFile,
      removeFile,
      uploadFile,
      downloadFile,
      deleteFile
    }
  }
}
</script>

<style scoped>
.admin-data-manager {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0 0 10px 0;
  color: #1a56db;
  font-size: 24px;
  font-weight: 600;
}

.header-stats {
  color: #666;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 15px;
}

.header-stats span {
  white-space: nowrap;
}

.selected-info {
  color: #409eff;
  font-weight: 500;
}

/* 工具栏样式 */
.toolbar-container {
  background: white;
  padding: 15px 20px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  margin-bottom: 20px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.file-link {
  color: #1a56db;
  cursor: pointer;
  text-decoration: none;
  word-break: break-all;
  font-size: 12px;
}

.file-link:hover {
  text-decoration: underline;
}

/* 表单样式 */
.accession-dialog :deep(.el-dialog__body) {
  padding: 20px;
  max-height: 70vh;
  overflow-y: auto;
}

.professional-form {
  margin-top: 0;
}

.form-card {
  margin-bottom: 20px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  background: #ffffff;
}

.form-card:last-child {
  margin-bottom: 0;
}

.form-card :deep(.el-card__header) {
  background: #f0f5ff;
  padding: 12px 20px;
  border-bottom: 1px solid #e4e7ed;
}

.card-header {
  color: #409eff;
}

.header-title {
  font-size: 14px;
  font-weight: 600;
  color: #409eff;
}

.field-hint {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
}

/* 文件管理样式 */
.file-group {
  margin-bottom: 24px;
}

.file-group:last-child {
  margin-bottom: 0;
}

.file-group-header {
  font-size: 14px;
  font-weight: 600;
  color: #409eff;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e4e7ed;
}

.file-field {
  background: #fafafa;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 12px;
}

.file-field.compact {
  padding: 10px;
}

.file-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.label-text {
  font-weight: 600;
  color: #303133;
  font-size: 13px;
}

.file-content {
  min-height: 32px;
  margin-bottom: 8px;
  padding: 6px 10px;
  background: white;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  display: flex;
  align-items: center;
}

.file-content.compact {
  min-height: 28px;
  padding: 4px 8px;
}

.file-name {
  font-size: 12px;
  color: #67c23a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.no-file-text {
  font-size: 12px;
  color: #c0c4cc;
}

.file-actions {
  display: flex;
  gap: 8px;
}

.file-format-hint {
  margin-top: 6px;
  font-size: 11px;
  color: #909399;
  text-align: right;
}

/* 对话框底部样式 */
.dialog-footer-professional {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0 0 0;
}

.footer-hint {
  font-size: 12px;
  color: #909399;
}

.footer-actions {
  display: flex;
  gap: 10px;
}

.data-link {
  color: #1a56db;
  text-decoration: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: inline-block;
  max-width: 100%;
}

.data-link:hover {
  text-decoration: underline;
}

.data-empty {
  color: #999;
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
