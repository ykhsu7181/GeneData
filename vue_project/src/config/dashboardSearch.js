const MODULE_KEYWORDS = [
  { keywords: ['home', 'dashboard', '首页'], route: { path: '/dashboard' } },
  { keywords: ['accession', '品种', '材料'], route: { path: '/accession-card' } },
  { keywords: ['genome', '基因组'], route: { path: '/genome-card' } },
  { keywords: ['annotation', '注释'], route: { path: '/annotation' } },
  { keywords: ['transcriptome', '转录组'], route: { path: '/transcriptome-overview' } },
  { keywords: ['codon', '密码子'], route: { path: '/codon-card' } },
  { keywords: ['core', 'variable', '区块', '核心可变'], route: { path: '/core-variable-blocks' } },
  { keywords: ['map', 'geo', 'location', '地理', '地图'], route: { path: '/accession-map' } }
]

const DATASET_TYPE_ROUTES = {
  genome: { path: '/genome-card' },
  annotation: { path: '/annotation' },
  transcriptome: { path: '/transcriptome-overview' },
  population_genetics: { path: '/data-overview' },
  variant: { path: '/data-overview' },
  phenotype: { path: '/data-overview' }
}

const normalize = (value) => (value || '').trim().toLowerCase()

const matchesLabel = (query, candidate) => {
  const normalizedQuery = normalize(query)
  const normalizedCandidate = normalize(candidate)
  return normalizedCandidate && (
    normalizedCandidate === normalizedQuery ||
    normalizedCandidate.includes(normalizedQuery) ||
    normalizedQuery.includes(normalizedCandidate)
  )
}

export const resolveDashboardSearch = (query, dashboardData) => {
  const trimmedQuery = (query || '').trim()
  if (!trimmedQuery) {
    return null
  }

  const normalizedQuery = normalize(trimmedQuery)

  const moduleMatch = MODULE_KEYWORDS.find((item) =>
    item.keywords.some((keyword) => normalizedQuery.includes(normalize(keyword)))
  )
  if (moduleMatch) {
    return moduleMatch.route
  }

  const speciesMatch = (dashboardData.species_cards || []).find((card) =>
    matchesLabel(trimmedQuery, card.name_cn) ||
    matchesLabel(trimmedQuery, card.latin_name) ||
    matchesLabel(trimmedQuery, card.species_code)
  )
  if (speciesMatch) {
    return {
      path: '/data-overview',
      query: {
        search: speciesMatch.name_cn || speciesMatch.latin_name || speciesMatch.species_code
      }
    }
  }

  const subPopulationMatch = (dashboardData.sub_population_distribution || []).find((item) =>
    matchesLabel(trimmedQuery, item.name)
  )
  if (subPopulationMatch) {
    return {
      path: '/data-overview',
      query: {
        sub_population: subPopulationMatch.name
      }
    }
  }

  const datasetTypeMatch = (dashboardData.dataset_type_summary || []).find((item) =>
    matchesLabel(trimmedQuery, item.dataset_type)
  )
  if (datasetTypeMatch) {
    return DATASET_TYPE_ROUTES[datasetTypeMatch.dataset_type] || { path: '/data-overview' }
  }

  const geoMatch = (dashboardData.geo_distribution || []).find((item) =>
    matchesLabel(trimmedQuery, item.region)
  )
  if (geoMatch) {
    return {
      path: '/accession-map',
      query: {
        region: geoMatch.region
      }
    }
  }

  return {
    path: '/accession-card',
    query: {
      accession: trimmedQuery
    }
  }
}

export const keywordToRoute = (keyword, dashboardData) => {
  if (!keyword) {
    return null
  }

  if (keyword.type === 'module' && keyword.target) {
    return { path: keyword.target }
  }

  if (keyword.type === 'species' && keyword.target) {
    return {
      path: '/data-overview',
      query: {
        search: keyword.label
      }
    }
  }

  return resolveDashboardSearch(keyword.label, dashboardData)
}
