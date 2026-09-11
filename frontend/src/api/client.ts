/**
 * HTTP Client utility for communicating with AURELIUS backend.
 */

import type { ApiErrorResponse } from '../types/market';

export class ApiError extends Error {
  status: number;
  data: ApiErrorResponse;

  constructor(status: number, data: ApiErrorResponse) {
    super(data.message || `API error (${status})`);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

export async function apiClient<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;

  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    let errorData: ApiErrorResponse;
    try {
      errorData = await response.json();
    } catch {
      errorData = {
        error: 'HTTP_ERROR',
        message: `Request failed with status ${response.status}`,
      };
    }
    throw new ApiError(response.status, errorData);
  }

  return response.json();
}
