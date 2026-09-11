import React from 'react';
import type { BenchmarkSnapshot } from '../../types/overview';
import { BenchmarkCard } from './BenchmarkCard';

interface BenchmarkRibbonProps {
  benchmarks: BenchmarkSnapshot[];
  onSelectBenchmark?: (benchmarkId: string) => void;
}

export const BenchmarkRibbon: React.FC<BenchmarkRibbonProps> = ({
  benchmarks,
  onSelectBenchmark,
}) => {
  // Sort or maintain canonical order: SP500, DOW, NASDAQ, RUSSELL2000, VIX
  const canonicalOrder = ['SP500', 'DOW', 'NASDAQ', 'RUSSELL2000', 'VIX'];
  const sortedBenchmarks = [...benchmarks].sort((a, b) => {
    const idxA = canonicalOrder.indexOf(a.benchmark_id);
    const idxB = canonicalOrder.indexOf(b.benchmark_id);
    return (idxA >= 0 ? idxA : 99) - (idxB >= 0 ? idxB : 99);
  });

  return (
    <section className="benchmark-ribbon-section">
      <div className="section-header">
        <div className="section-title-group">
          <span className="section-bullet">◈</span>
          <h2 className="section-heading">CANONICAL MARKET BENCHMARKS</h2>
        </div>
        <span className="section-annotation">
          EQUITY INDICES (USD) &amp; IMPLIED VOLATILITY (VIX PTS)
        </span>
      </div>

      <div className="benchmark-cards-grid">
        {sortedBenchmarks.map((b) => (
          <BenchmarkCard
            key={b.benchmark_id}
            benchmark={b}
            onSelect={onSelectBenchmark}
          />
        ))}
      </div>
    </section>
  );
};
