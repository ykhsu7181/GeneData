import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'

const read = path => readFileSync(join(process.cwd(), path), 'utf8')
const annotationView = read('src/views/AnnotationView.vue')
const browserView = read('src/views/GenomeBrowserView.vue')
const internalNavigationSource = read('src/utils/internalNavigation.js')
const jbrowseNavigationSource = read('src/utils/jbrowseNavigation.js')
const localeZh = read('src/i18n/locales/zh-CN.js')
const localeEn = read('src/i18n/locales/en-US.js')

const importSource = source => import(`data:text/javascript;charset=utf-8,${encodeURIComponent(source)}`)

test('annotation table uses a readiness-gated feature action and trusted location API', () => {
  assert.match(annotationView, /fixed="right"/)
  assert.match(annotationView, /openFeatureInBrowser\(scope\.row\)/)
  assert.match(annotationView, /normalizePositiveId\(row\?\.feature_id\)/)
  assert.match(annotationView, /browserStatusPayload\.value\?\.status === 'ready'/)
  assert.match(annotationView, /browserStatusPayload\.value\?\.location_ready === true/)
  assert.match(annotationView, /annotations\/\$\{encodeURIComponent\(annotationId\)\}[\s\S]*?features\/\$\{encodeURIComponent\(featureId\)\}\/jbrowse-location\//)
  assert.match(annotationView, /name: 'assembly-browser'/)
  assert.match(annotationView, /annotation_id: annotationId/)
  assert.match(annotationView, /loc,/)
  assert.match(annotationView, /return_to: returnTo/)
})

test('readiness is cached per Assembly and Annotation and stale requests are ignored', () => {
  assert.match(annotationView, /`\$\{contextAssemblyId\.value\}:\$\{contextAnnotationId\.value\}`/)
  assert.match(annotationView, /const browserStatusCache = new Map\(\)/)
  assert.match(annotationView, /browserStatusCache\.has\(key\)/)
  assert.match(annotationView, /fetchBrowserStatus\(\{ force: forceBrowserStatus \}\)/)
  assert.match(annotationView, /fetchFiles\(\{ forceBrowserStatus: true \}\)/)
  assert.match(annotationView, /browserStatusController\?\.abort\(\)/)
  assert.match(annotationView, /requestToken !== browserStatusRequestToken/)
  assert.match(annotationView, /browserContextKey\.value !== key/)
})

test('browser page uses the same selected-mode URL for iframe and new window', () => {
  assert.match(browserView, /:src="iframeUrl"/)
  assert.match(browserView, /:href="iframeUrl"/)
  assert.match(browserView, /rel="noopener noreferrer"/)
  assert.match(browserView, /assemblyName: payload\.assembly_name/)
  assert.match(browserView, /trackIds: Array\.isArray\(payload\.track_ids\)/)
  assert.match(browserView, /if \(!requestedLocation\.value\)/)
  assert.match(browserView, /buildJBrowseUrl\(\{ configUrl: configUrl\.toString\(\) \}\)/)
})

test('shared internal return-path validator allows only application-owned destinations', async () => {
  assert.match(annotationView, /normalizeInternalAppPath\(route\.fullPath\)/)
  assert.match(browserView, /normalizeInternalAppPath\(route\.query\.return_to\)/)

  const { normalizeInternalAppPath, normalizeAssemblyReturnPath } = await importSource(internalNavigationSource)
  assert.equal(normalizeInternalAppPath('/annotation?assembly_id=93'), '/annotation?assembly_id=93')
  assert.equal(normalizeInternalAppPath('/annotation-card?annotation_id=7'), '/annotation-card?annotation_id=7')
  assert.equal(normalizeAssemblyReturnPath('/assembly/93?tab=files'), '/assembly/93?tab=files')
  for (const unsafe of [
    'https://example.com/annotation',
    '//example.com/annotation',
    '/\\example.com/annotation',
    '/%2Fexample.com/annotation',
    '/%252Fexample.com/annotation',
    '/admin',
    '/annotation#fragment'
  ]) {
    assert.equal(normalizeInternalAppPath(unsafe), '')
  }
})

test('JBrowse URL builder validates coordinates and emits fixed selected-mode parameters', async () => {
  const { buildJBrowseUrl, normalizeJBrowseLocation, normalizePositiveId } = await importSource(jbrowseNavigationSource)
  assert.equal(normalizePositiveId('93'), '93')
  assert.equal(normalizePositiveId('0'), '')
  assert.equal(normalizeJBrowseLocation('Chr1:10-20'), 'Chr1:10-20')
  assert.equal(normalizeJBrowseLocation('Chr1:20-10'), '')
  assert.equal(normalizeJBrowseLocation('Chr 1:10-20'), '')

  const selectedUrl = buildJBrowseUrl({
    configUrl: 'https://genedata.test/gd/api/files/assemblies/93/jbrowse-config/?annotation_id=7',
    assemblyName: 'assembly_93',
    loc: 'Chr1:10-20',
    trackIds: ['assembly_93-reference', 'annotation_7']
  })
  const selectedParams = new URL(selectedUrl, 'https://genedata.test').searchParams
  assert.equal(selectedParams.get('assembly'), 'assembly_93')
  assert.equal(selectedParams.get('loc'), 'Chr1:10-20')
  assert.equal(selectedParams.get('tracks'), 'assembly_93-reference,annotation_7')

  const defaultUrl = buildJBrowseUrl({ configUrl: 'https://genedata.test/config' })
  const defaultParams = new URL(defaultUrl, 'https://genedata.test').searchParams
  assert.equal(defaultParams.get('config'), 'https://genedata.test/config')
  assert.equal(defaultParams.has('loc'), false)
  assert.equal(defaultParams.has('tracks'), false)
})

test('Stage C messages exist in both locales', () => {
  for (const key of [
    'viewInGenomeBrowser',
    'browserStatusLoading',
    'browserUnavailable',
    'browserFeatureUnavailable',
    'browserLocationNotFound',
    'browserLocationConflict',
    'browserLocationInvalid',
    'browserMappingUnavailable',
    'browserLocationFailed',
    'invalidAnnotation',
    'invalidLocation',
    'locationUnavailable'
  ]) {
    assert.match(localeZh, new RegExp(`${key}:`))
    assert.match(localeEn, new RegExp(`${key}:`))
  }
})
