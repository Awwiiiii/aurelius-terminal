import React from 'react';
import type { MetricStatus } from '../../types/fundamental';

interface Props {
  status: MetricStatus;
  diagnosticCount?: number;
}

export const MetricStatusBadge: React.FC<Props> = ({ status, diagnosticCount = 0 }) => {
  switch (status) {
    case 'VALID':
      return <span className="status-badge status-valid">VALID</span>;
    case 'DISTORTED':
      return (
        <span className="status-badge status-distorted" title="Mathematically or economically distorted">
          ⚠ DISTORTED{diagnosticCount > 0 ? ` (${diagnosticCount})` : ''}
        </span>
      );
    case 'UNAVAILABLE':
      return <span className="status-badge status-unavailable">UNAVAILABLE</span>;
    case 'NOT_APPLICABLE':
      return <span className="status-badge status-na">NOT APPLICABLE</span>;
    default:
      return <span className="status-badge">{status}</span>;
  }
};
