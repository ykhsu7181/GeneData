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
assert.doesNotMatch(view, /localStorage.*TOKEN|file_path/, 'the public page exposes neither tokens nor storage paths')
assert.match(router, /path: '\/public-files'/)
assert.match(nav, /nav\.publicFileCatalog/)

console.log('public file catalog source checks passed')
