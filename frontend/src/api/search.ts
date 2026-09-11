/**
 * Security search API service.
 */

import { apiClient } from './client';
import type { SecuritySearchResponse } from '../types/search';

export async function searchSecurities(
  query: string,
  limit: number = 10
): Promise<SecuritySearchResponse> {
  const params = new URLSearchParams({
    q: query,
    limit: limit.toString(),
  });
  return apiClient<SecuritySearchResponse>(`/api/v1/market/search?${params.toString()}`);
}
