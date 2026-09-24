export const GEOGRAPHIC_GRID_SIZE = 2;
export const UNKNOWN_SUB_POPULATION = 'Unknown';
export const GEOGRAPHIC_CLUSTER_COLORS = Object.freeze({
  single: '#1677e8',
  small: '#16a34a',
  medium: '#7c3aed',
  large: '#f07818',
  extraLarge: '#eab308',
  veryLarge: '#ef4444',
  extreme: '#ec4899'
});

const normalizeText = (value) => (
  value === null || value === undefined ? '' : String(value).trim()
);

const normalizeCoordinate = (value) => {
  if (value === null || value === undefined || normalizeText(value) === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};

export const normalizeSubPopulation = (value) => {
  const normalized = normalizeText(value);
  if (!normalized || normalized === '-' || normalized === '未知亚群') {
    return UNKNOWN_SUB_POPULATION;
  }
  return normalized;
};

export const isValidCoordinate = (longitude, latitude) => {
  const normalizedLongitude = normalizeCoordinate(longitude);
  const normalizedLatitude = normalizeCoordinate(latitude);
  return (
    normalizedLongitude !== null
    && normalizedLatitude !== null
    && normalizedLongitude >= -180
    && normalizedLongitude <= 180
    && normalizedLatitude >= -90
    && normalizedLatitude <= 90
  );
};

export const normalizeGeographicItems = (items = []) => {
  const records = Array.isArray(items)
    ? items
    : Object.entries(items || {}).map(([accession, info]) => ({ accession, ...(info || {}) }));
  const uniqueRecords = new Map();

  records.forEach((item) => {
    const accession = normalizeText(item?.accession);
    if (!accession) return;
    uniqueRecords.set(accession, {
      ...item,
      accession,
      longitude: normalizeCoordinate(item.longitude),
      latitude: normalizeCoordinate(item.latitude),
      sub_population: normalizeSubPopulation(item.sub_population),
      country: normalizeText(item.country) || null,
      region: normalizeText(item.region) || null
    });
  });

  return Array.from(uniqueRecords.values());
};

export const getValidGeographicItems = (items = []) => (
  normalizeGeographicItems(items).filter((item) => (
    isValidCoordinate(item.longitude, item.latitude)
  ))
);

export const aggregateGeographicItems = (items = [], gridSize = GEOGRAPHIC_GRID_SIZE) => {
  const normalizedGridSize = Number(gridSize);
  if (!Number.isFinite(normalizedGridSize) || normalizedGridSize <= 0) return [];

  const maxGridX = Math.ceil(360 / normalizedGridSize) - 1;
  const maxGridY = Math.ceil(180 / normalizedGridSize) - 1;
  const grouped = new Map();

  getValidGeographicItems(items).forEach((item) => {
    const gridX = Math.min(maxGridX, Math.floor((item.longitude + 180) / normalizedGridSize));
    const gridY = Math.min(maxGridY, Math.floor((item.latitude + 90) / normalizedGridSize));
    const key = `${gridX}:${gridY}`;
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(item);
  });

  return Array.from(grouped.entries()).map(([key, accessions]) => ({
    key,
    accessions,
    count: accessions.length,
    longitude: accessions.reduce((sum, item) => sum + item.longitude, 0) / accessions.length,
    latitude: accessions.reduce((sum, item) => sum + item.latitude, 0) / accessions.length
  }));
};

export const buildGeographicMetrics = (items = [], gridSize = GEOGRAPHIC_GRID_SIZE) => {
  const records = normalizeGeographicItems(items);
  const validItems = getValidGeographicItems(records);
  return {
    totalAccessions: records.length,
    mappedAccessions: validItems.length,
    unmappedAccessions: records.length - validItems.length,
    geographicRegions: aggregateGeographicItems(validItems, gridSize).length,
    subPopulationCount: new Set(validItems.map((item) => item.sub_population)).size
  };
};

export const getGeographicViewport = (items = []) => {
  const validItems = getValidGeographicItems(items);
  if (!validItems.length) return { center: [0, 15], zoom: 1.05 };

  const longitudes = validItems.map((item) => item.longitude);
  const latitudes = validItems.map((item) => item.latitude);
  const minLongitude = Math.min(...longitudes);
  const maxLongitude = Math.max(...longitudes);
  const minLatitude = Math.min(...latitudes);
  const maxLatitude = Math.max(...latitudes);
  const longitudeSpan = maxLongitude - minLongitude;
  const latitudeSpan = maxLatitude - minLatitude;
  const visualSpan = Math.max(longitudeSpan, latitudeSpan * 1.8);
  const zoom = Math.min(5, Math.max(1.05, 250 / (visualSpan + 35)));

  return {
    center: [
      (minLongitude + maxLongitude) / 2,
      (minLatitude + maxLatitude) / 2
    ],
    zoom
  };
};

export const getTopGeographicRegions = (items = [], limit = 3) => {
  const counts = new Map();
  getValidGeographicItems(items).forEach((item) => {
    const name = normalizeText(item.country) || normalizeText(item.region);
    if (!name) return;
    counts.set(name, (counts.get(name) || 0) + 1);
  });
  return Array.from(counts.entries())
    .map(([name, count]) => ({ name, count }))
    .sort((left, right) => right.count - left.count || left.name.localeCompare(right.name))
    .slice(0, Math.max(0, Number(limit) || 0));
};

export const filterGeographicItems = (items = [], filters = {}) => {
  const accessions = normalizeText(filters.accession).toLowerCase();
  const region = normalizeText(filters.region).toLowerCase();
  const selectedSubPopulations = Array.isArray(filters.subPopulations)
    ? new Set(filters.subPopulations.map(normalizeSubPopulation))
    : null;

  return getValidGeographicItems(items).filter((item) => {
    if (accessions && item.accession.toLowerCase() !== accessions) return false;
    if (!accessions && selectedSubPopulations && !selectedSubPopulations.size) return false;
    if (!accessions && selectedSubPopulations && !selectedSubPopulations.has(item.sub_population)) return false;
    if (region) {
      const country = normalizeText(item.country).toLowerCase();
      const itemRegion = normalizeText(item.region).toLowerCase();
      if (!country.includes(region) && !itemRegion.includes(region)) return false;
    }
    return true;
  });
};

export const getSubPopulationColor = (subPopulation) => ({
  cA: '#2563eb',
  cB: '#dc2626',
  GJ: '#16a34a',
  XI: '#9333ea',
  WILD: '#ea580c',
  'O.glaberrima': '#db2777',
  Unknown: '#64748b'
}[normalizeSubPopulation(subPopulation)] || '#64748b');

export const getGeographicClusterColor = (count) => {
  const normalizedCount = Math.max(0, Number(count) || 0);
  if (normalizedCount <= 1) return GEOGRAPHIC_CLUSTER_COLORS.single;
  if (normalizedCount <= 5) return GEOGRAPHIC_CLUSTER_COLORS.small;
  if (normalizedCount <= 10) return GEOGRAPHIC_CLUSTER_COLORS.medium;
  if (normalizedCount < 20) return GEOGRAPHIC_CLUSTER_COLORS.large;
  if (normalizedCount <= 50) return GEOGRAPHIC_CLUSTER_COLORS.extraLarge;
  if (normalizedCount <= 100) return GEOGRAPHIC_CLUSTER_COLORS.veryLarge;
  return GEOGRAPHIC_CLUSTER_COLORS.extreme;
};
