import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'
import assert from 'node:assert/strict'

const routerSource = readFileSync(join(process.cwd(), 'src', 'router', 'index.js'), 'utf8')
const viewSource = readFileSync(join(process.cwd(), 'src', 'views', 'AssemblyView.vue'), 'utf8')
const drawerSource = readFileSync(join(process.cwd(), 'src', 'components', 'assembly', 'RelatedFilesDrawer.vue'), 'utf8')

test('Assembly detail has an authenticated standalone route and bare Assembly redirects explicitly', () => {
  assert.match(
    routerSource,
    /path:\s*'\/assembly'[\s\S]*?redirect:\s*\{\s*name:\s*'accession-card'\s*\}[\s\S]*?requiresAuth:\s*true/
  )
  assert.match(
    routerSource,
    /path:\s*'\/assembly\/:assemblyId'[\s\S]*?name:\s*'assembly-detail'[\s\S]*?requiresAuth:\s*true/
  )
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
