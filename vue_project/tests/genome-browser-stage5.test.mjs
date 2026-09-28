import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'

const read = (path) => readFileSync(join(process.cwd(), path), 'utf8')
const router = read('src/router/index.js')
const assemblyView = read('src/views/AssemblyView.vue')
const browserView = read('src/views/GenomeBrowserView.vue')

test('router exposes the assembly genome browser page', () => {
  assert.match(router, /path:\s*'\/assembly\/:assemblyId\/browser'/)
  assert.match(router, /name:\s*'assembly-browser'/)
  assert.match(router, /GenomeBrowserView\.vue/)
})

test('assembly detail gates its browser entry on readiness', () => {
  assert.match(assemblyView, /jbrowse-status\//)
  assert.match(assemblyView, /\['ready', 'reference_only'\]/)
  assert.match(assemblyView, /name:\s*'assembly-browser'/)
  assert.match(assemblyView, /:disabled="!browserReady \|\| browserStatusLoading"/)
})

test('browser page launches same-origin JBrowse with dynamic config', () => {
  assert.match(browserView, /\/jbrowse2\/\?\$\{params\.toString\(\)\}/)
  assert.match(browserView, /jbrowse-config\//)
  assert.match(browserView, /params\.set\('tracks'/)
  assert.match(browserView, /<iframe/)
  assert.doesNotMatch(browserView, /file_path|manual_files|derived_data/)
})
