/**
 * Security search TypeScript type definitions matching backend API contracts.
 */

export interface SecuritySearchResultItem {
  ticker: string;
  name: string;
  exchange?: string | null;
  exchange_display?: string | null;
  asset_type: string;
  currency?: string | null;
  provider: string;
}

export interface SecuritySearchResponse {
  query: string;
  count: number;
  results: SecuritySearchResultItem[];
}
