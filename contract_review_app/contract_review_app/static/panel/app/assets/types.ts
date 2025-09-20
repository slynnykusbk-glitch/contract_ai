export interface PartyRegistry {
  name: string
  number_or_duns?: string
  status?: string
  address?: string
  incorp_date?: string
  sic_codes?: string[]
}

export interface CompaniesMetaItem {
  verdict: 'match' | 'mismatch' | 'ambiguous' | 'not_found' | 'ok'
  from_document: {
    name?: string
    number?: string
  }
  matched?: {
    company_name?: string
    company_number?: string
    company_status?: string
    address_snippet?: string
    sic_codes?: string[]
    links?: {
      self?: string
      officers?: string
      filing_history?: string
    }
  }
}
