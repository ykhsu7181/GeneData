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

test('Assembly list exposes a persistent user-selectable column picker', () => {
  assert.match(portalSource, /COLUMN_STORAGE_KEY = 'genedata_assembly_list_columns_v1'/)
  assert.match(portalSource, /DEFAULT_COLUMN_KEYS = \['accession', 'assembly', 'assembly_accession', 'assembly_level', 'species'\]/)
  assert.match(portalSource, /class="column-picker"/)
  assert.match(portalSource, /visibleColumns\.length === 1 && isColumnVisible\(column\.key\)/)
  assert.match(portalSource, /@change="toggleColumn\(column\.key, \$event\.target\.checked\)"/)
  assert.match(portalSource, /writeColumnPreference\(normalized\)/)
  for (const key of ['accession', 'assembly', 'assembly_accession', 'assembly_level', 'species']) {
    assert.match(portalSource, new RegExp(`v-if="isColumnVisible\\('${key}'\\)"`))
  }
})

test('Assembly portal canonicalizes query state and preserves it when opening detail', () => {
  assert.match(portalSource, /const buildPortalQuery = \(search, page = 1\)/)
  assert.match(portalSource, /router\.replace\(\{ name: 'assembly', query \}\)/)
  assert.match(portalSource, /delete query\.q|route\.query\.q/)
  assert.match(portalSource, /query:\s*\{\s*from:\s*'assembly',\s*\.\.\.buildPortalQuery\(routeSearch\.value, currentPage\.value\)\s*\}/)
})

test('Assembly detail preserves portal return context across breadcrumbs and related assembly switches', () => {
  assert.match(viewSource, /hasAssemblyPortalContext/)
  assert.match(viewSource, /name:\s*'assembly',\s*query:\s*assemblyPortalQuery/)
  assert.match(viewSource, /const assemblyPortalQuery = computed/)
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
