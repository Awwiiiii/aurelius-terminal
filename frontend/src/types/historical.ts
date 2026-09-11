export type HistoricalTimeHorizon =
  | '1M'
  | '3M'
  | '6M'
  | 'YTD'
  | '1Y'
  | '3Y'
  | '5Y'
  | 'MAX'
  | 'CUSTOM';

export interface ReturnMetricsResponse {
  adjusted_price_return: string;
  cagr: string | null;
  mean_daily_return: string;
  positive_days: number;
  negative_days: number;
  zero_days: number;
  win_rate: string | null;
}

export interface VolatilityMetricsResponse {
  daily_volatility: string;
  annualized_volatility: string;
  trading_days_assumed: number;
}

export interface DrawdownMetricsResponse {
  max_drawdown: string;
  max_drawdown_peak_date: string;
  max_drawdown_trough_date: string;
  recovery_date: string | null;
  is_recovered: boolean;
  current_drawdown: string;
}

export interface HistoricalExtremesResponse {
  period_high: string;
  period_high_date: string;
  period_low: string;
  period_low_date: string;
  distance_from_high: string;
  distance_from_low: string;
}

export interface BenchmarkComparisonResponse {
  benchmark_id: string;
  benchmark_name: string;
  common_base_date: string;
  security_return: string;
  benchmark_return: string;
  excess_return: string;
  correlation: string;
}

export interface HistoricalBarPointResponse {
  date: string;
  open: string;
  high: string;
  low: string;
  close: string;
  adj_close: string;
  volume: number;
  daily_return: string | null;
  cumulative_return: string;
  drawdown: string;
  sma_20: string | null;
  sma_50: string | null;
  sma_200: string | null;
  ema_20: string | null;
  rolling_vol_20: string | null;
  benchmark_cumulative_return: string | null;
}

export interface HistoricalAnalysisResponse {
  ticker: string;
  horizon: string;
  start_date: string;
  end_date: string;
  calendar_days: number;
  trading_days: number;
  returns: ReturnMetricsResponse;
  volatility: VolatilityMetricsResponse;
  drawdowns: DrawdownMetricsResponse;
  extremes: HistoricalExtremesResponse;
  benchmark_comparison: BenchmarkComparisonResponse | null;
  series: HistoricalBarPointResponse[];
  provider: string;
  fetched_at: string;
}
