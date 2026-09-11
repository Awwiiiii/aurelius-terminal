import React from 'react';
import { ApiError } from '../../api/client';

interface ErrorMessageProps {
  error: Error | ApiError | string | null;
  onRetry?: () => void;
}

export const ErrorMessage: React.FC<ErrorMessageProps> = ({ error, onRetry }) => {
  if (!error) return null;

  let errorCode = 'ERROR';
  let message = '';
  let hint = '';

  if (typeof error === 'string') {
    message = error;
  } else if (error instanceof ApiError) {
    errorCode = error.data.error || `HTTP ${error.status}`;
    message = error.data.message || error.message;

    if (errorCode === 'INVALID_TICKER') {
      hint = 'Please enter a valid stock ticker symbol (1-12 alphanumeric characters, e.g. AAPL, BRK.B).';
    } else if (errorCode === 'DATA_NOT_FOUND') {
      hint = 'The security could not be found or has no trading data for the requested dates.';
    } else if (errorCode === 'PROVIDER_RATE_LIMIT') {
      hint = 'The data provider rate limit has been exceeded. Please wait a minute before trying again.';
    } else if (errorCode === 'PROVIDER_UNAVAILABLE') {
      hint = 'The upstream provider is currently unreachable or encountering service degradation.';
    } else if (errorCode === 'DATA_QUALITY_FAILURE') {
      hint = 'Data returned by provider failed integrity checks (e.g. invalid prices or inverted high/low).';
    }
  } else {
    message = error.message;
  }

  return (
    <div className="error-banner">
      <div className="error-header">
        <span className="error-badge">{errorCode}</span>
        <span className="error-title">{message}</span>
      </div>
      {hint && <div className="error-hint">{hint}</div>}
      {onRetry && (
        <button onClick={onRetry} className="retry-btn">
          RETRY
        </button>
      )}
    </div>
  );
};
