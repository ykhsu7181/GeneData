import axios from 'axios'

export const emptyDashboardPayload = () => ({
  summary: {
    assembly_count: null,
    species_count: null,
    annotation_count: null,
    accession_count: null
  },
  featured_accessions: []
})

export const fetchDashboardData = async () => {
  const response = await axios.get('/warehouse/dashboard/')
  return {
    ...emptyDashboardPayload(),
    ...(response.data || {})
  }
}
