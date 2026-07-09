import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const repoRoot = process.cwd()
const viewPath = resolve(repoRoot, 'src/views/TranscriptomeOverviewView.vue')
const source = readFileSync(viewPath, 'utf8')

assert.match(source, /转录组表/, 'Transcriptome overview title should be 转录组表')
assert.match(source, /query\/transcriptome-list\//, 'Transcriptome list should load rows from transcriptome-list endpoint')
assert.match(source, /query\/transcriptome-files\//, 'Transcriptome list should load drawer files from transcriptome-files endpoint')
assert.match(source, /搜索物种 \/ Accession \/ 品种/, 'Transcriptome list should expose the required search placeholder')
assert.match(source, /参考基因组版本/, 'Transcriptome filter/table should include reference assembly version')
assert.match(source, /样本类型/, 'Transcriptome filter/table should include sample type')
assert.match(source, /数据大小/, 'Transcriptome table should include data size')
assert.match(source, /查看详情/, 'Transcriptome rows should provide a detail action')
assert.match(source, /查看文件/, 'Transcriptome rows should provide a view files action')
assert.match(source, /fileDrawerVisible/, 'Transcriptome list should have a file drawer')
assert.match(source, /data-files/, 'Transcriptome downloads should use DataFile download URLs')

for (const matrixColumn of ['label="all"', 'label="leaf"', 'label="panicles"', 'label="shoot"', 'label="stem"', 'label="root"']) {
  assert.doesNotMatch(source, new RegExp(matrixColumn), `Transcriptome page must not keep old matrix column ${matrixColumn}`)
}

assert.doesNotMatch(source, /download-transcriptome/, 'Transcriptome page must not call the old transcriptome download endpoint')
assert.doesNotMatch(source, /\/gd\/api\/files\/genome-files\//, 'Transcriptome page must not reference old genome-files download URLs')
assert.doesNotMatch(source, /legacy_genomefile/, 'Transcriptome page must not reference legacy source names')
assert.doesNotMatch(source, /organism_fallback/, 'Transcriptome page must not reference organism fallback')

console.log('transcriptome list view source checks passed')
