import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const repoRoot = process.cwd()
const viewPath = resolve(repoRoot, 'src/views/GenomeCard.vue')
const source = readFileSync(viewPath, 'utf8')

assert.match(source, /可视化视图/, 'Genome page should keep a visualization view switch')
assert.match(source, /数据列表/, 'Genome page should add a data list view switch')
assert.match(source, /activeView/, 'Genome page should switch between visualization and list views')
assert.match(source, /query\/genome-list\//, 'Genome list view should load rows from the new genome-list endpoint')
assert.match(source, /query\/genome-files\//, 'Genome list view should load drawer files from the new genome-files endpoint')
assert.match(source, /选择物种/, 'Genome list filter should include species selector placeholder')
assert.match(source, /选择品种/, 'Genome list filter should include accession selector placeholder')
assert.match(source, /选择组装级别/, 'Genome list filter should include assembly level selector placeholder')
assert.match(source, /Chromosome/, 'Genome list should expose Chromosome assembly level')
assert.match(source, /Scaffold/, 'Genome list should expose Scaffold assembly level')
assert.match(source, /Contig/, 'Genome list should expose Contig assembly level')
assert.match(source, /查看文件/, 'Genome list rows should provide a view files action')
assert.match(source, /downloadGenomeRow/, 'Genome list rows should provide download behavior')
assert.match(source, /fileDrawerVisible/, 'Genome list should have a file drawer')
assert.match(source, /data-files/, 'Genome downloads should use DataFile download URLs')
assert.doesNotMatch(source, /\/gd\/api\/files\/genome-files\//, 'GenomeCard must not reference old genome-files download URLs')
assert.doesNotMatch(source, /legacy_genomefile/, 'GenomeCard must not reference legacy source names')
assert.doesNotMatch(source, /organism_fallback/, 'GenomeCard must not reference organism fallback')

console.log('genome list view source checks passed')
