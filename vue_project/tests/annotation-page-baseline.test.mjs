import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

const source = readFileSync(resolve(process.cwd(), 'src/views/AnnotationView.vue'), 'utf8')
const searchPanelSource = readFileSync(
  resolve(process.cwd(), 'src/components/annotation/AnnotationSearchPanel.vue'),
  'utf8'
)
const summaryBarSource = readFileSync(
  resolve(process.cwd(), 'src/components/annotation/AnnotationSummaryBar.vue'),
  'utf8'
)

test('Annotation keeps its current hierarchy and data endpoints', () => {
  assert.match(source, /axios\.get\('\/files\/query\/annotation-organisms\/'/)
  assert.match(source, /axios\.get\(`\/files\/accessions\/\$\{accession\}\/`,\s*\{/)
  assert.match(source, /axios\.get\('\/files\/query\/annotation-data\/'/)
  assert.match(source, /annotation_id/)
  assert.match(source, /assembly_id/)
})

test('Annotation keeps the existing list columns and pagination', () => {
  for (const property of ['seqid', 'feature', 'start', 'end', 'length', 'strand', 'source', 'score']) {
    assert.match(source, new RegExp(`el-table-column prop="${property}"`))
  }
  assert.match(source, /page\.annotation\.attributes/)
  assert.match(source, /<el-pagination/)
  assert.match(source, /:page-sizes="\[20, 50, 100, 200\]"/)
})

test('Annotation retains both table and chart modes', () => {
  assert.match(source, /viewMode === 'table'/)
  assert.match(source, /viewMode === 'chart'/)
  assert.match(source, /drawAnnotationVisualization/)
  assert.match(source, /fetchVisualizationData/)
})

test('Annotation exposes draft and applied query compatibility state', () => {
  assert.match(source, /const draftQuery = reactive\(\{/)
  assert.match(source, /const appliedQuery = reactive\(\{/)
  for (const key of ['accession', 'assemblyId', 'annotationId', 'chromosome', 'featureType']) {
    assert.match(source, new RegExp(`${key}:`))
  }
  assert.match(source, /const selectedOrganism = computed\(\{/)
  assert.match(source, /const contextAnnotationId = computed\(\{/)
})

test('Annotation provides an Accession to Assembly to Annotation cascade', () => {
  assert.match(source, /:assembly-id="selectedAssemblyId"/)
  assert.match(source, /:annotation-id="selectedAnnotationId"/)
  assert.match(searchPanelSource, /v-for="item in assemblyOptions"/)
  assert.match(searchPanelSource, /v-for="item in annotationOptions"/)
  assert.match(searchPanelSource, /:label="\$t\('page\.annotation\.allChromosomes'\)" value=""/)
  assert.match(source, /const handleAssemblyChange = async/)
  assert.match(source, /const handleAnnotationChange = async/)
  assert.match(source, /assemblyOptions\.value\.find/)
  assert.match(source, /const annotation = pickAnnotation\(assembly, ''\)/)
  assert.match(source, /selectedChromosome\.value = ''/)
  assert.match(source, /selectedFeatureType\.value = 'all'/)
})

test('Annotation loads full filter metadata separately from filtered rows', () => {
  assert.match(source, /axios\.get\('\/files\/query\/annotation-options\/'/)
  assert.match(source, /annotationStatistics\.value = data\.summary \|\| null/)
  assert.match(source, /chromosomeOptions\.value = Array\.isArray\(data\.chromosomes\)/)
  assert.match(source, /feature_types/)
  const optionsIndex = source.indexOf('await fetchAnnotationOptions();')
  const reconcileIndex = source.indexOf('await reconcileRouteFilters();', optionsIndex)
  const filesIndex = source.indexOf('await fetchFiles();', reconcileIndex)
  assert.ok(optionsIndex >= 0 && optionsIndex < reconcileIndex && reconcileIndex < filesIndex)
  assert.doesNotMatch(source, /annotationStatistics\.value = data\.statistics/)
  assert.doesNotMatch(source, /chromosomeOptions\.value = data\.statistics\.chromosomes/)
  assert.match(summaryBarSource, /summary\?\.chromosome_count/)
  assert.match(summaryBarSource, /summary\?\.feature_type_count/)
})

test('Annotation chromosome All option omits the chromosome request filter', () => {
  assert.match(source, /if \(chromosome\) \{\s*params\.chromosome = chromosome;/)
})
