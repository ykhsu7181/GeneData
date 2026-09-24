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

assert.match(source, /page\.rawData\.breadcrumb/, 'RawDataView should localize the breadcrumb')
assert.match(source, /page\.rawData\.title/, 'RawDataView should localize the title')
assert.match(source, /page\.rawData\.subtitle/, 'RawDataView should localize the subtitle')
assert.match(source, /query\/raw-data\//, 'RawDataView should call the raw-data API')
assert.match(source, /page\.rawData\.fileList/, 'RawDataView should localize the file list title')
assert.match(source, /page\.rawData\.detailsTitle/, 'RawDataView should localize the detail drawer title')
assert.match(source, /page\.rawData\.copyPath/, 'RawDataView should support localized path copying')
assert.match(source, /page\.rawData\.copyChecksum/, 'RawDataView should support localized md5 copying')
assert.match(source, /page\.rawData\.searchPlaceholder/, 'RawDataView should localize the search placeholder')
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
