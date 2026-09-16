export const topNavItems = [
  {
    key: 'home',
    labelKey: 'nav.home',
    path: '/dashboard'
  },
  {
    key: 'accession',
    labelKey: 'nav.accession',
    path: '/accession-card'
  },
  {
    key: 'assembly',
    labelKey: 'nav.assembly',
    path: '/assembly'
  },
  {
    key: 'data',
    labelKey: 'nav.data',
    path: '/data-overview',
    children: [
      { labelKey: 'nav.dataOverview', path: '/data-overview' },
      { labelKey: 'nav.researchGroupRawData', path: '/raw-data' }
    ]
  },
  {
    key: 'more',
    labelKey: 'nav.more',
    children: [
      { labelKey: 'nav.annotation', path: '/annotation' },
      { labelKey: 'nav.transcriptomeOverview', path: '/transcriptome-overview' }
    ]
  }
]

const pathAliasMap = {
  '/': '/dashboard',
  '/annotation-card': '/annotation',
  '/core-variable-blocks-card': '/core-variable-blocks',
  '/accession-detail': '/accession-card'
}

const groupMatchers = {
  home: ['/dashboard'],
  accession: ['/accession-card', '/accession-detail', '/accession-map'],
  assembly: ['/assembly'],
  data: ['/data', '/data-chart', '/data-overview', '/raw-data'],
  more: ['/annotation', '/annotation-card', '/transcriptome', '/transcriptome-overview']
}

export const normalizeTopNavPath = (path = '') => pathAliasMap[path] || path

export const getTopNavActiveGroup = (path = '') => {
  const normalizedPath = normalizeTopNavPath(path)

  return (
    Object.entries(groupMatchers).find(([, paths]) =>
      paths.some((matcherPath) => normalizedPath === matcherPath || normalizedPath.startsWith(`${matcherPath}/`))
    )?.[0] || null
  )
}

export const isTopNavGroupActive = (groupKey, path = '') => getTopNavActiveGroup(path) === groupKey
