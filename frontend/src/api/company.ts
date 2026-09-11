/**
 * Company profile and security metadata API service.
 */

import { apiClient } from './client';
import type {
  CompanyProfileEndpointResponse,
  SecurityDetailResponse,
} from '../types/company';

export async function getSecurityDetail(
  ticker: string
): Promise<SecurityDetailResponse> {
  return apiClient<SecurityDetailResponse>(
    `/api/v1/market/security/${encodeURIComponent(ticker)}`
  );
}

export async function getCompanyProfile(
  ticker: string
): Promise<CompanyProfileEndpointResponse> {
  return apiClient<CompanyProfileEndpointResponse>(
    `/api/v1/market/company/${encodeURIComponent(ticker)}`
  );
}
