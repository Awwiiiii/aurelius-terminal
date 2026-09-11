export type QuantitativeMetricType = 'VOLATILITY' | 'CORRELATION' | 'MEAN';
export type ReturnCalculationType = 'SIMPLE' | 'LOG';

export interface DescriptiveStatisticsResponse {
  sample_size: number;
  mean: string;
  median: string;
  sample_variance: string | null;
  population_variance: string | null;
  sample_std_dev: string | null;
  population_std_dev: string | null;
  min_value: string;
  max_value: string;
  range_value: string;
  mad: string;
  iqr: string;
  skewness: string | null;
  excess_kurtosis: string | null;
}

export interface QuantileDistributionResponse {
  p1: string;
  p5: string;
  p10: string;
  p25: string;
  p50: string;
  p75: string;
  p90: string;
  p95: string;
  p99: string;
}

export interface HistogramBinResponse {
  bin_start: string;
  bin_end: string;
  bin_mid: string;
  count: number;
  frequency: string;
}

export interface ReturnDistributionSummaryResponse {
  ticker: string;
  horizon: string;
  return_type: 'SIMPLE' | 'LOG';
  sample_size: number;
  positive_count: number;
  positive_pct: string;
  negative_count: number;
  negative_pct: string;
  zero_count: number;
  zero_pct: string;
  statistics: DescriptiveStatisticsResponse;
  quantiles: QuantileDistributionResponse;
  histogram: HistogramBinResponse[];
}

export interface MultiAssetCorrelationMatrixResponse {
  tickers: string[];
  horizon: string;
  common_dates_count: number;
  start_date: string;
  end_date: string;
  correlation_matrix: (string | null)[][];
  covariance_matrix: (string | null)[][];
}

export interface RollingStatisticPointResponse {
  date: string;
  value: string | null;
}

export interface RollingQuantitativeSeriesResponse {
  ticker_a: string;
  ticker_b: string | null;
  metric_name: string;
  window: number;
  series: RollingStatisticPointResponse[];
}
