import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const repoRoot = process.cwd()
const routerSource = readFileSync(resolve(repoRoot, 'src/router/index.js'), 'utf8')
const navSource = readFileSync(resolve(repoRoot, 'src/config/topNavConfig.mjs'), 'utf8')
const viewPath = resolve(repoRoot, 'src/views/RawDataView.vue')
const source = readFileSync(viewPath, 'utf8')

assert.match(routerSource, /path:\s*'\/raw-data'/, 'router should expose /raw-data')
assert.match(navSource, /path:\s*'\/raw-data'/, 'top navigation raw data entry should target /raw-data')

assert.match(source, /原始数据 Raw Data/, 'RawDataView should render the Raw Data title')
assert.match(source, /query\/raw-data\//, 'RawDataView should call the raw-data API')
assert.match(source, /原始数据文件列表/, 'RawDataView should render the file list title')
assert.match(source, /原始数据详情/, 'RawDataView should render the detail drawer title')
assert.match(source, /复制路径/, 'RawDataView should support copying file paths')
assert.match(source, /复制 MD5/, 'RawDataView should support copying md5 values')
assert.ok(
  source.includes('搜索 Accession / Sample / 文件名 / 路径 / MD5'),
  'RawDataView should expose the requested search placeholder'
)
assert.match(source, /statusMap/, 'RawDataView should map check statuses')
assert.doesNotMatch(source, /GenomeFile/, 'RawDataView must not reference GenomeFile')
assert.doesNotMatch(source, /genome-files/, 'RawDataView must not reference old genome file download URLs')
assert.doesNotMatch(source, /legacy_genomefile/, 'RawDataView must not reference legacy source names')
assert.doesNotMatch(source, /organism_fallback/, 'RawDataView must not reference organism fallback')
assert.match(source, /:class="\['content-grid', \{ 'drawer-open': drawerOpen \}\]"/, 'RawDataView should expand its grid only while details are open')
assert.match(source, /<aside v-if="drawerOpen" class="detail-drawer">/, 'RawDataView should hide details until a row is selected')
assert.match(source, /@click="openDrawer\(row\)"/, 'RawDataView rows should open the detail drawer')
assert.match(source, /const closeDrawer = \(\) => \{\s*drawerOpen\.value = false\s*selectedRow\.value = null/, 'Closing details should clear the drawer and selected row')
assert.doesNotMatch(source, /selectedRow\.value = rows\.value\[0\]/, 'RawDataView must not select the first row automatically')

console.log('raw-data page source checks passed')
