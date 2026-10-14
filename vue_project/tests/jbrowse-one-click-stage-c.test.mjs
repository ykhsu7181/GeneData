import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'

const read = path => readFileSync(join(process.cwd(), path), 'utf8')
const annotationView = read('src/views/AnnotationView.vue')
const browserView = read('src/views/GenomeBrowserView.vue')
const accessionDetailView = read('src/views/AccessionDetailTableView.vue')
const assemblyDetailView = read('src/views/AssemblyView.vue')
const internalNavigationSource = read('src/utils/internalNavigation.js')
const jbrowseNavigationSource = read('src/utils/jbrowseNavigation.js')
const localeZh = read('src/i18n/locales/zh-CN.js')
const localeEn = read('src/i18n/locales/en-US.js')
const responsiveLayoutPlugin = read('../jbrowse_plugins/genedata-responsive-layout.js')
const jbrowseBuildScript = read('../scripts/build_jbrowse2_web.sh')

const importSource = source => import(`data:text/javascript;charset=utf-8,${encodeURIComponent(source)}`)

test('annotation table uses a readiness-gated feature action and trusted location API', () => {
  assert.match(annotationView, /fixed="right"/)
  assert.match(annotationView, /width="96"/)
  assert.match(annotationView, /<Aim\s*\/>/)
  assert.match(annotationView, /type="primary"[\s\S]*?link[\s\S]*?page\.annotation\.locateFeature/)
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

test('browser page keeps its surrounding chrome compact and names navigation actions', () => {
  assert.match(browserView, /<ArrowLeft\s*\/>/)
  assert.match(browserView, /<Refresh\s*\/>/)
  assert.match(browserView, /<TopRight\s*\/>/)
  assert.match(browserView, /page\.genomeBrowser\.backToAnnotation/)
  assert.match(browserView, /page\.genomeBrowser\.backToAssembly/)
  assert.doesNotMatch(browserView, /page\.genomeBrowser\.description/)
  assert.match(browserView, /\.browser-shell \{ position:relative; height:calc\(100vh - 282px\); height:calc\(100dvh - 282px\); min-height:480px; \}/)
  assert.doesNotMatch(browserView, /min-height:680px/)
  assert.doesNotMatch(browserView, /class="primary-link"/)
})

test('browser detail heading matches accession and assembly detail heading sizes', () => {
  assert.match(browserView, /\.browser-header h1 \{[^}]*font-size:30px;[^}]*line-height:1\.2;/)
  assert.match(accessionDetailView, /\.page-heading h1 \{[^}]*font-size:30px;[^}]*line-height:1\.2;/)
  assert.match(assemblyDetailView, /\.detail-header h1 \{[^}]*font-size:30px;[^}]*line-height:1\.2;/)
  assert.match(browserView, /\.browser-header h1 \{ font-size:25px; \}/)
  assert.match(accessionDetailView, /\.page-heading h1 \{ width:100%; font-size:25px; \}/)
  assert.match(assemblyDetailView, /\.detail-header h1 \{ font-size:25px; \}/)
})

test('JBrowse responsive plugin fills the remaining iframe height without reloading the session', () => {
  assert.match(responsiveLayoutPlugin, /GeneDataResponsiveLayout/)
  assert.match(responsiveLayoutPlugin, /new window\.ResizeObserver\(schedule\)/)
  assert.match(responsiveLayoutPlugin, /display\.setHeight\(nextHeight\)/)
  assert.match(responsiveLayoutPlugin, /window\.innerHeight - APP_CHROME_HEIGHT - view\.height - BOTTOM_GAP/)
  assert.doesNotMatch(responsiveLayoutPlugin, /location\.reload|window\.location/)
  assert.match(jbrowseBuildScript, /plugins\/genedata-responsive-layout\.js/)
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
    'locateFeature',
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
