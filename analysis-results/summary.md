# Benchmark Summary

| Category | Configuration | Node Count | Throughput (RPS) | Latency p50 (ms) | Latency p99 (ms) | Latency p99.9 (ms) | Efficiency (RPS/$)
|---|---|---|---|---|---|---|---|
| Budget Entry Level | Single | 1x 1cores | 46488 ± 1671 | 4.01 ± 0.27 | 15.51 ± 0.87 | 21.68 ± 2.04 | 1507.41 |
| Entry Level | Cluster | 3x 1cores | 105270 ± 7063 | 1.08 ± 0.04 | 10.46 ± 1.45 | 15.11 ± 1.22 | 1137.82 |
| Entry Level | Single | 1x 4cores | 114801 ± 4993 | 2.14 ± 0.11 | 3.86 ± 0.15 | 9.58 ± 0.48 | 930.63 |
| High Perf | Cluster (24x) | 24x 2cores | 200404 ± 22836 | 1.24 ± 0.10 | 2.54 ± 0.90 | 9.61 ± 9.64 | 135.38 |
| High Perf | Cluster (48x) | 48x 1cores | 177921 ± 4921 | 1.41 ± 0.04 | 2.41 ± 0.05 | 4.71 ± 0.04 | 120.19 |
| High Perf | Single | 1x 48cores | 192225 ± 21297 | 1.22 ± 0.11 | 3.76 ± 0.64 | 7.91 ± 0.85 | 129.86 |
| Mid Range | Cluster | 7x 2cores | 241606 ± 10513 | 1.04 ± 0.04 | 2.08 ± 0.18 | 14.66 ± 14.21 | 559.59 |
| Mid Range | Single | 1x 16cores | 202438 ± 13911 | 1.19 ± 0.07 | 2.43 ± 0.37 | 6.09 ± 0.34 | 410.26 |
