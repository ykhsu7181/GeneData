import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const source = path => readFileSync(resolve('src', path), 'utf8')
const view = source('views/PublicFileCatalogView.vue')
const service = source('services/publicFileCatalog.js')
const router = source('router/index.js')
const nav = source('config/topNavConfig.mjs')

assert.match(service, /\/v1\/files\//, 'catalog uses the production external API')
assert.match(service, /files\/manifest\.tsv/, 'catalog exposes a complete TSV manifest')
assert.match(view, /name_contains/)
assert.match(view, /accession/)
assert.match(view, /assembly/)
assert.match(view, /role/)
assert.match(view, /format/)
assert.match(view, /dataset/)
assert.match(view, /file_code/)
assert.match(view, /sha256/)
assert.match(view, /GENEDATA_TOKEN/, 'download command documents token use without storing a token')
assert.match(view, /type="selection"/, 'catalog supports selecting multiple files')
assert.match(view, /buildPublicFileCacheScript/, 'catalog generates an inspectable cache script')
assert.match(view, /buildPublicFileBatchScript/, 'catalog generates an immutable batch API workflow')
assert.match(view, /buildPublicFileArchiveScript/, 'catalog generates an explicit server archive workflow')
assert.match(view, /includeCompanions/, 'catalog can include authorized companion indexes')
assert.match(view, /filteredManifestUrl/, 'manifest export follows the active catalog filters')
assert.doesNotMatch(view, /localStorage.*TOKEN|file_path/, 'the public page exposes neither tokens nor storage paths')
assert.match(router, /path: '\/public-files'/)
assert.match(nav, /nav\.publicFileCatalog/)

console.log('public file catalog source checks passed')
