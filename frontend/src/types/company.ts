/**
 * Company profile and security identity TypeScript type definitions.
 */

export interface CompanyProfileResponse {
  lookup_ticker: string;
  company_name: string;
  legal_name?: string | null;
  description?: string | null;
  sector?: string | null; // Provider-supplied, not authoritative GICS
  industry?: string | null; // Provider-supplied, not authoritative GICS
  country?: string | null;
  state?: string | null;
  city?: string | null;
  address?: string | null;
  website?: string | null;
  employees?: number | null;
  provider: string;
  fetched_at: string;
}

export interface SecurityInfoResponse {
  ticker: string;
  name: string;
  asset_type: string;
  currency: string;
  exchange?: string | null;
  exchange_display?: string | null;
  timezone?: string | null;
  country?: string | null;
  sector?: string | null;
  industry?: string | null;
  provider: string;
  fetched_at: string;
}

export interface SecurityDetailResponse {
  security: SecurityInfoResponse;
  company_profile?: CompanyProfileResponse | null;
  is_operating_company: boolean;
}

export interface CompanyProfileEndpointResponse {
  company_profile?: CompanyProfileResponse | null;
  is_operating_company: boolean;
  message?: string | null;
}
