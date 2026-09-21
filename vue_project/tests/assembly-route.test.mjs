import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'
import assert from 'node:assert/strict'

const routerSource = readFileSync(join(process.cwd(), 'src', 'router', 'index.js'), 'utf8')
const portalSource = readFileSync(join(process.cwd(), 'src', 'views', 'AssemblyPortalView.vue'), 'utf8')
const viewSource = readFileSync(join(process.cwd(), 'src', 'views', 'AssemblyView.vue'), 'utf8')
const drawerSource = readFileSync(join(process.cwd(), 'src', 'components', 'assembly', 'RelatedFilesDrawer.vue'), 'utf8')
const recentDrawerSource = readFileSync(join(process.cwd(), 'src', 'components', 'assembly', 'AssemblyRecentDrawer.vue'), 'utf8')

test('Assembly portal and detail have authenticated standalone routes', () => {
  assert.match(
    routerSource,
    /path:\s*'\/assembly'[\s\S]*?component:\s*\(\)\s*=>\s*import\('\.\.\/views\/AssemblyPortalView\.vue'\)[\s\S]*?requiresAuth:\s*true/
  )
  assert.match(
    routerSource,
    /path:\s*'\/assembly\/:assemblyId'[\s\S]*?name:\s*'assembly-detail'[\s\S]*?requiresAuth:\s*true/
  )
})

test('Assembly portal uses the list API and keeps detail navigation separate', () => {
  assert.match(portalSource, /axios\.get\('\/files\/assemblies\/'/)
  assert.match(portalSource, /name:\s*'assembly-detail'/)
  assert.match(portalSource, /name:\s*'accession-card'/)
  assert.match(portalSource, /recordRecentAssembly\(row\)/)
  assert.match(portalSource, /page\.assembly\.searchTitle/)
  assert.doesNotMatch(portalSource, /<h2 id="assembly-search-title">/)
  assert.match(portalSource, /class="search-card" role="search" :aria-label="\$t\('page\.assembly\.searchTitle'\)"/)
  assert.doesNotMatch(portalSource, /page\.assembly\.portalSubtitle/)
  assert.match(portalSource, /\.portal-hero\s*\{[\s\S]*?margin-bottom:\s*12px;[\s\S]*?padding-top:\s*4px;/)
  assert.match(portalSource, /grid-template-columns:\s*minmax\(0, 1fr\) 134px/)
  assert.match(portalSource, /min-height:\s*46px;[\s\S]*?border-radius:\s*0 9px 9px 0/)
})

test('Assembly recently viewed is service-backed and exposes a clearable drawer', () => {
  assert.match(portalSource, /<AssemblyRecentDrawer/)
  assert.match(portalSource, /getRecentAssemblies/)
  assert.match(portalSource, /removeRecentAssembly\(id\)/)
  assert.match(portalSource, /clearRecentAssemblies\(\)/)
  assert.match(portalSource, /drawerTrigger\?\.focus\?\.\(\)/)
  assert.match(recentDrawerSource, /<el-drawer/)
  assert.match(recentDrawerSource, /\$emit\('remove', item\.id\)/)
  assert.match(recentDrawerSource, /\$emit\('clear'\)/)
  assert.match(recentDrawerSource, /page\.assembly\.removeRecent/)
})

test('Assembly list keeps five default columns and exposes optional statistics through More', () => {
  assert.match(portalSource, /import \{ ArrowDown, Clock, Collection, Search \} from '@element-plus\/icons-vue'/)
  assert.match(portalSource, /<Collection \/>/)
  assert.match(portalSource, /<Clock \/>/)
  assert.match(portalSource, /<Search \/>/)
  assert.match(portalSource, /page\.assembly\.totalAssemblies[\s\S]*?<el-popover[\s\S]*?page\.assembly\.moreColumns/)
  assert.match(portalSource, /prop="accession"/)
  assert.match(portalSource, /prop="assembly"/)
  assert.match(portalSource, /prop="assembly_accession"/)
  assert.match(portalSource, /prop="assembly_level"/)
  assert.match(portalSource, /prop="species"/)
  assert.match(portalSource, /const selectedStatisticColumns = ref\(\[\]\)/)
  assert.match(portalSource, /v-for="column in visibleStatisticColumns"/)
  for (const key of ['genome_size', 'chromosome_count', 'contig_count', 'n50', 'gc_content']) {
    assert.match(portalSource, new RegExp(`key: '${key}'`))
  }
  assert.doesNotMatch(portalSource, /鈱|鈻|鈼|鈫/)
})

test('Assembly portal canonicalizes query state and preserves it when opening detail', () => {
  assert.match(portalSource, /const buildPortalQuery = \(search, page = 1\)/)
  assert.match(portalSource, /router\.replace\(\{ name: 'assembly', query \}\)/)
  assert.match(portalSource, /delete query\.q|route\.query\.q/)
  assert.match(portalSource, /query:\s*\{\s*from:\s*'assembly',\s*\.\.\.buildPortalQuery\(routeSearch\.value, currentPage\.value\)\s*\}/)
})

test('Assembly detail preserves portal return context across breadcrumbs and related assembly switches', () => {
  assert.match(viewSource, /name:\s*'assembly',\s*query:\s*assemblyPortalQuery/)
  assert.match(viewSource, /const assemblyPortalQuery = computed/)
  assert.match(viewSource, /query:\s*route\.query/)
  assert.doesNotMatch(viewSource, /v-if="hasAssemblyPortalContext"/)
})

test('Assembly detail switches breadcrumbs according to its entry point', () => {
  assert.match(viewSource, /const fromAccession = computed/)
  assert.match(viewSource, /v-if="fromAccession" :to="\{ name: 'accession-card' \}"/)
  assert.match(viewSource, /v-else :to="\{ name: 'assembly', query: assemblyPortalQuery \}"/)
  assert.match(viewSource, /:to="\{ name: 'accession-card', query: accessionDetailQuery \}"/)
  assert.match(viewSource, /query:\s*route\.query/)
})

test('Assembly page loads the detail contract and renders all four required sections', () => {
  assert.match(viewSource, /\/files\/assemblies\/\$\{encodeURIComponent\(assemblyId\.value\)\}\/summary\//)
  assert.match(viewSource, /page\.assemblyDetail\.basicInformation/)
  assert.match(viewSource, /page\.assemblyDetail\.statistics/)
  assert.match(viewSource, /<AnnotationVersionTable/)
  assert.match(viewSource, /<AssemblyVersionTable/)
  assert.match(viewSource, /mode="revision"/)
})

test('Assembly statistics are split into two balanced five-item columns', () => {
  assert.match(viewSource, /class="statistics-grid"/)
  assert.match(viewSource, /v-for="\(column, index\) in statisticColumns"/)
  for (const key of [
    'genomeSize', 'n50', 'gcContent', 'atContent', 'nCountAndPercentage',
    'chromosomeCount', 'sequenceCount', 'sequenceMd5', 'gapCount', 'assemblyLevel'
  ]) {
    assert.match(viewSource, new RegExp(`statisticFields\\.${key}`))
  }
  assert.doesNotMatch(viewSource, /statisticFields\.contigCount/)
  assert.match(viewSource, /\.statistics-grid\s*\{[\s\S]*?grid-template-columns:repeat\(2, minmax\(0, 1fr\)\)/)
  assert.match(viewSource, /const formatAssemblyLevel = \(value\)/)
  assert.match(viewSource, /page\.assemblyDetail\.levelValues/)
})

test('Assembly detail header matches the Accession detail information architecture', () => {
  assert.match(viewSource, /<header class="detail-header">/)
  assert.match(viewSource, /page\.assemblyDetail\.title/)
  assert.match(viewSource, /class="heading-tag species-tag"/)
  assert.match(viewSource, /class="heading-tag population-tag"/)
  assert.match(viewSource, /class="detail-search" role="search"/)
  assert.match(viewSource, /const submitSearch = async/)
  assert.match(viewSource, /axios\.get\('\/files\/assemblies\/'/)
  assert.match(viewSource, /params: \{ assemblyId: target\.id \}/)
})

test('Assembly page exposes loading, missing ID, permission, 404, conflict, generic error and retry states', () => {
  assert.match(viewSource, /!assemblyId/)
  assert.match(viewSource, /v-else-if="loading"/)
  assert.match(viewSource, /status === 403/)
  assert.match(viewSource, /status === 404/)
  assert.match(viewSource, /status === 409/)
  assert.match(viewSource, /page\.assemblyDetail\.loadFailed/)
  assert.match(viewSource, /@click="fetchDetail"/)
})

test('Related Files uses the server URL and retrieves every page in the Accession scope', () => {
  assert.match(viewSource, /detail\.value\?\.related_files_url/)
  assert.match(viewSource, /value\.startsWith\('\/gd\/api\/'\)/)
  assert.match(viewSource, /page_size:\s*100/)
  assert.match(viewSource, /while \(files\.length < total\)/)
  assert.match(viewSource, /drawerScope\.value = null/)
})

test('Annotation file actions filter the shared Accession file inventory by relation', () => {
  assert.match(viewSource, /@view-files="openAnnotationFiles"/)
  assert.match(viewSource, /type:\s*'annotation'/)
  assert.match(viewSource, /item\.relations\?\.some/)
  assert.match(viewSource, /relation\.related_type === drawerScope\.value\.type/)
})

test('Annotation names open the annotation page with a restorable Assembly source context', () => {
  assert.match(viewSource, /:enable-navigation="true"/)
  assert.match(viewSource, /@view-annotation="openAnnotation"/)
  assert.match(viewSource, /name:\s*'annotation'/)
  assert.match(viewSource, /annotation:\s*String\(annotation\.id\)/)
  assert.match(viewSource, /from:\s*'assembly'/)
  assert.match(viewSource, /return_to:\s*route\.fullPath/)
})

test('Related Files drawer provides file metadata, empty/error states and DataFile download action', () => {
  assert.match(drawerSource, /v-else-if="errorMessage"/)
  assert.match(drawerSource, /item\.file_name/)
  assert.match(drawerSource, /item\.file_role/)
  assert.match(drawerSource, /item\.size_display/)
  assert.match(drawerSource, /\$emit\('download', item\)/)
  assert.match(drawerSource, /emptyRelatedFiles/)
})

test('hidden Tools routes remain registered', () => {
  for (const path of ['/core-variable-blocks', '/codon-card', '/tools/codonw']) {
    assert.match(routerSource, new RegExp(`path:\\s*'${path}'`))
  }
})
