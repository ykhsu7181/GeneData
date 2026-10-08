import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

const view = readFileSync(resolve(process.cwd(), 'src/views/AnnotationView.vue'), 'utf8')
const accessionHeader = readFileSync(
  resolve(process.cwd(), 'src/components/accession/AccessionPortalHeader.vue'),
  'utf8'
)
const zh = readFileSync(resolve(process.cwd(), 'src/i18n/locales/zh-CN.js'), 'utf8')
const en = readFileSync(resolve(process.cwd(), 'src/i18n/locales/en-US.js'), 'utf8')

test('Annotation Phase 9 opens chart mode with visible feature tracks by default', () => {
  const defaultSelection = view.match(/const displayFeatures = ref\(\[([\s\S]*?)\]\)/)?.[1] || ''
  for (const feature of ['gene', 'mRNA', 'CDS', 'exon', 'five_prime_UTR', 'three_prime_UTR']) {
    assert.match(defaultSelection, new RegExp(`['"]${feature}['"]`))
  }
})

test('Annotation Phase 9 gives table and chart modes accurate localized titles', () => {
  assert.match(view, /viewMode === 'chart' \? 'page\.annotation\.chartTitle' : 'page\.annotation\.tableTitle'/)
  assert.match(zh, /chartTitle: '注释图形'/)
  assert.match(en, /chartTitle: 'Annotation Visualization'/)
})

test('Annotation Phase 9 aligns its page heading with the Accession portal heading', () => {
  for (const declaration of [
    'margin-bottom:12px',
    'padding-top:4px',
    'color:#7183a0',
    'font-size:13px',
    'color:#2b6fc7',
    'color:#102f61',
    'font-size:30px',
    'line-height:1.12',
    'letter-spacing:-.03em'
  ]) {
    assert.match(accessionHeader.replaceAll(' ', ''), new RegExp(declaration.replaceAll('.', '\\.')))
  }
  assert.match(view, /\.annotation-hero\s*\{[\s\S]*margin-bottom:\s*12px;[\s\S]*padding-top:\s*4px;/)
  assert.match(view, /\.breadcrumb\s*\{[\s\S]*color:\s*#7183a0;[\s\S]*font-size:\s*13px;/)
  assert.match(view, /\.breadcrumb a,[\s\S]*color:\s*#2b6fc7;/)
  assert.match(view, /\.annotation-hero h1\s*\{[\s\S]*color:\s*#102f61;[\s\S]*font-size:\s*30px;[\s\S]*line-height:\s*1\.12;[\s\S]*letter-spacing:\s*-0\.03em;/)
})

test('Annotation Phase 9 renders short chromosomes as readable horizontal tracks', () => {
  assert.match(view, /Math\.max\(720, annotationContainer\.value\.clientWidth\)/)
  assert.match(view, /const actualSegmentWidth = numSegments === 1[\s\S]*\? segmentWidth/)
  assert.match(view, /formatGenomicPosition\(segmentStart\)/)
  assert.match(view, /formatGenomicPosition\(segmentEnd\)/)
  assert.match(view, /return `\$\{Math\.round\(value\)\} bp`/)
  assert.match(view, /trackHeight = 10/)
  assert.match(view, /\.annotation-container\s*\{[\s\S]*min-height:\s*220px/)
})

test('Annotation Phase 9 makes row length controls effective for bp and kb chromosomes', () => {
  assert.match(view, /const getSegmentLengthStepBp = \(chromosomeLength\)/)
  assert.match(view, /const getDefaultSegmentLengthBp = \(chromosomeLength\)/)
  assert.match(view, /const segmentLengthUnit = computed/)
  assert.match(view, /segmentLengthUnit\.value === 'bp'/)
  assert.match(view, /segmentLengthUnit\.value === 'kb'/)
  assert.match(view, /v-model\.number="segmentLengthDisplay"/)
  assert.match(view, /:step="segmentLengthStep"/)
  assert.match(view, /initializeSegmentLength\(chromosomeLength\.value\)/)
  assert.match(zh, /rowLength: '每行长度 \(\{unit\}\)：'/)
  assert.match(en, /rowLength: 'Length per row \(\{unit\}\):'/)
})

test('Annotation Phase 9 draws automatically after the loading container mounts', () => {
  assert.match(view, /let visualizationReady = false/)
  assert.match(view, /visualizationReady = true/)
  assert.match(
    view,
    /finally\s*\{[\s\S]*loadingVisualization\.value = false;[\s\S]*await nextTick\(\);[\s\S]*drawAnnotationVisualization\(\)/
  )
  assert.match(view, /const displayedResultCount = computed/)
  assert.match(view, /viewMode\.value === 'chart' \? visualizationData\.value\.length : totalCount\.value/)
  assert.match(view, /count: displayedResultCount/)
})
