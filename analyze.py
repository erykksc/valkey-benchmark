import os
import glob
import re
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import sys
from collections import defaultdict

# Configuration
RESULTS_DIR = "results"
OUTPUT_DIR = "analysis-results"
PRICING_FILE = "pricing.yml"
TRIM_START = 120
TRIM_END_FROM_END = 30
RUN_DURATION = 1200  # Assumed total duration before trim
TRIM_END = RUN_DURATION - TRIM_END_FROM_END

# Visual Settings
sns.set_theme(style="whitegrid")
plt.rcParams["figure.figsize"] = [12, 6]

# Mapping
TYPE_MAP = {
    "1cores": "t2d-standard-1",
    "2cores": "t2d-standard-2",
    "4cores": "t2d-standard-4",
    "16cores": "t2d-standard-16",
    "48cores": "t2d-standard-48",
}


def load_pricing(pricing_file):
    print(f"Loading pricing from {pricing_file}...")
    prices = {}
    current_type = None
    in_us_central1 = False

    try:
        with open(pricing_file, "r") as f:
            for line in f:
                line_strip = line.strip()
                if line_strip.startswith("t2d-standard-"):
                    current_type = line_strip.rstrip(":")
                    in_us_central1 = False
                elif current_type and "us-central1:" in line_strip:
                    in_us_central1 = True
                elif current_type and in_us_central1 and "month:" in line_strip:
                    parts = line_strip.split(":")
                    if len(parts) == 2:
                        try:
                            price = float(parts[1].strip())
                            prices[current_type] = price
                        except ValueError:
                            pass
                    in_us_central1 = False
    except FileNotFoundError:
        print(f"Error: Pricing file {pricing_file} not found.")
        sys.exit(1)

    return prices


def parse_filename(filename):
    # Pattern example: 1xAMD-EPYC-7B13_4cores_15Gi_2026-02-02_17-24_threads-3.csv
    basename = os.path.basename(filename)

    # Extract Node Count and Cores
    match_config = re.search(r"(\d+)xAMD-EPYC-7B13_(\d+)cores", basename)
    node_count = int(match_config.group(1)) if match_config else None
    cores_str = f"{match_config.group(2)}cores" if match_config else None

    # Extract Thread Count
    match_threads = re.search(r"_threads-(\d+)", basename)
    threads = (
        int(match_threads.group(1)) if match_threads else 1
    )  # Default to 1 if not found

    return node_count, cores_str, threads


def get_config_group(node_count, cores_str):
    if node_count == 1 and cores_str == "1cores":
        return "Budget Entry Level", "Single"

    if node_count == 1 and cores_str == "4cores":
        return "Entry Level", "Single"
    if node_count == 3 and cores_str == "1cores":
        return "Entry Level", "Cluster"

    if node_count == 1 and cores_str == "16cores":
        return "Mid Range", "Single"
    if node_count == 7 and cores_str == "2cores":
        return "Mid Range", "Cluster"

    if node_count == 1 and cores_str == "48cores":
        return "High Perf", "Single"
    if node_count == 24 and cores_str == "2cores":
        return "High Perf", "Cluster (24x)"
    if node_count == 48 and cores_str == "1cores":
        return "High Perf", "Cluster (48x)"

    return None, None


def calculate_percentiles(histogram):
    """Calculates p50, p99, p99.9 from a histogram."""
    if not histogram:
        return {"p50": 0, "p99": 0, "p999": 0}

    sorted_lats = sorted(histogram.keys())
    total_count = sum(histogram.values())

    p50_target = total_count * 0.50
    p99_target = total_count * 0.99
    p999_target = total_count * 0.999

    current_count = 0
    results = {}

    for lat in sorted_lats:
        count = histogram[lat]
        prev_count = current_count
        current_count += count

        if "p50" not in results and current_count >= p50_target:
            results["p50"] = lat
        if "p99" not in results and current_count >= p99_target:
            results["p99"] = lat
        if "p999" not in results and current_count >= p999_target:
            results["p999"] = lat
            break  # We found the highest target

    return results


def process_file(filepath, start_timestamp):
    chunk_size = 100000

    # Aggregators
    rps_per_sec = defaultdict(int)
    latencies_per_sec = defaultdict(list)
    latency_histogram = defaultdict(int)  # Global histogram for the run

    try:
        # First pass: Read in chunks
        for chunk in pd.read_csv(
            filepath,
            comment="#",
            chunksize=chunk_size,
            usecols=["FinishedAt", "Latency(us)"],
        ):
            # Calculate Relative Time
            chunk["RelativeTime"] = (chunk["FinishedAt"] - start_timestamp).astype(int)

            # Filter Time Window
            mask = (chunk["RelativeTime"] >= TRIM_START) & (
                chunk["RelativeTime"] < TRIM_END
            )
            valid_data = chunk[mask]

            if valid_data.empty:
                continue

            # Aggregation for Time Series (Plots 1 & 3)
            counts = valid_data.groupby("RelativeTime").size()
            for t, count in counts.items():
                rps_per_sec[t] += count

            grouped = valid_data.groupby("RelativeTime")["Latency(us)"]
            for t, group in grouped:
                # Store P99 for this second in this file
                p99 = group.quantile(0.99)
                latencies_per_sec[t].append(p99)

            # Aggregation for CDF (Plot 2)
            lat_counts = valid_data["Latency(us)"].value_counts()
            for lat, count in lat_counts.items():
                latency_histogram[lat] += count

    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return None, None, None

    return rps_per_sec, latencies_per_sec, latency_histogram


def process_data(results_dir=RESULTS_DIR):
    """
    Reads all files and processes data. Returns a dictionary of results.
    Useful for running in IPython: `results = process_data()`
    """
    if not os.path.exists(results_dir):
        print(f"Results directory '{results_dir}' not found.")
        return {}

    # Discover and Group Files
    files = glob.glob(os.path.join(results_dir, "*.csv"))
    groups = defaultdict(list)

    print(f"Found {len(files)} files.")

    for f in files:
        node_count, cores_str, threads = parse_filename(f)
        if not node_count:
            continue

        category, sub_label = get_config_group(node_count, cores_str)
        if category:
            groups[(category, sub_label)].append((f, node_count, cores_str, threads))

    # Process Groups
    results = {}

    for (category, sub_label), file_info_list in groups.items():
        file_list = [x[0] for x in file_info_list]

        if len(file_list) < 3:
            print(
                f"Warning: Group {category} - {sub_label} has {len(file_list)} runs (expected 3)."
            )

        print(f"Processing {category} - {sub_label} ({len(file_list)} runs)...")

        group_rps_per_sec = defaultdict(list)
        group_p99_per_sec = defaultdict(list)
        group_latency_hist = defaultdict(int)

        # Metadata
        _, node_count, cores_str, threads = file_info_list[0]

        # Run Summaries for Table
        run_stats = []

        for filepath in file_list:
            try:
                # Get Start Time
                df_head = pd.read_csv(
                    filepath, comment="#", nrows=1, usecols=["FinishedAt"]
                )
                if df_head.empty:
                    print(f"Skipping empty file: {filepath}")
                    continue
                start_time = df_head["FinishedAt"].iloc[0]
            except Exception as e:
                print(f"Error reading header of {filepath}: {e}")
                continue

            # Process File
            rps, lats, hist = process_file(filepath, start_time)

            if rps is not None and lats is not None and hist is not None:
                # Store aggregates for plots
                for t, count in rps.items():
                    group_rps_per_sec[t].append(count)
                for t, p99_list in lats.items():
                    group_p99_per_sec[t].extend(p99_list)
                for lat, count in hist.items():
                    group_latency_hist[lat] += count

                # Calculate Run Stats
                total_ops = sum(rps.values())
                duration = len(rps)
                avg_rps = total_ops / duration if duration > 0 else 0

                percentiles = calculate_percentiles(hist)

                run_stats.append(
                    {
                        "avg_rps": avg_rps,
                        "p50": percentiles.get("p50", 0),
                        "p99": percentiles.get("p99", 0),
                        "p999": percentiles.get("p999", 0),
                    }
                )

        # Calculate Mean +/- Std for Table
        if run_stats:
            stats_summary = {
                "rps_mean": np.mean([r["avg_rps"] for r in run_stats]),
                "rps_std": np.std([r["avg_rps"] for r in run_stats]),
                "p50_mean": np.mean([r["p50"] for r in run_stats]),
                "p50_std": np.std([r["p50"] for r in run_stats]),
                "p99_mean": np.mean([r["p99"] for r in run_stats]),
                "p99_std": np.std([r["p99"] for r in run_stats]),
                "p999_mean": np.mean([r["p999"] for r in run_stats]),
                "p999_std": np.std([r["p999"] for r in run_stats]),
            }
        else:
            stats_summary = {}

        results[(category, sub_label)] = {
            "rps": group_rps_per_sec,
            "p99": group_p99_per_sec,
            "hist": group_latency_hist,
            "node_count": node_count,
            "cores_str": cores_str,
            "threads": threads,
            "stats": stats_summary,
        }

    return results


def generate_markdown_table(results, output_dir=OUTPUT_DIR):
    """Generates a Markdown table with aggregated stats."""
    prices = load_pricing(PRICING_FILE)

    filepath = os.path.join(output_dir, "summary.md")
    print(f"Generating summary table to {filepath}...")

    with open(filepath, "w") as f:
        f.write("# Benchmark Summary\n\n")
        f.write(
            "| Category | Configuration | Node Count | Throughput (RPS) | Latency p50 (ms) | Latency p99 (ms) | Latency p99.9 (ms) | Efficiency (RPS/$)\n"
        )
        f.write("|---|---|---|---|---|---|---|---|\n")

        # Sort by Category then Sub-label
        sorted_keys = sorted(results.keys(), key=lambda x: (x[0], x[1]))

        for category, sub_label in sorted_keys:
            data = results[(category, sub_label)]

            # Helper to format
            def fmt(val, std=None):
                if std is not None:
                    return f"{val:.2f} ± {std:.2f}"
                return f"{val:.2f}"

            avg_rps = 0

            # Check if we have per-run stats (Mean +/- Std)
            if "stats" in data and data["stats"]:
                s = data["stats"]
                rps_val = f"{s['rps_mean']:.0f} ± {s['rps_std']:.0f}"
                p50_val = fmt(s["p50_mean"] / 1000, s["p50_std"] / 1000)
                p99_val = fmt(s["p99_mean"] / 1000, s["p99_std"] / 1000)
                p999_val = fmt(s["p999_mean"] / 1000, s["p999_std"] / 1000)
                avg_rps = s["rps_mean"]
            else:
                # Fallback: Calculate Global stats from aggregated data
                # RPS
                total_ops = sum(sum(counts) for counts in data["rps"].values())
                num_seconds = len(data["rps"])
                # Guess num_runs from first second's data length
                num_runs = 3
                if num_seconds > 0:
                    first_sec_data = next(iter(data["rps"].values()))
                    num_runs = len(first_sec_data)

                avg_rps = total_ops / (num_seconds * num_runs) if num_seconds > 0 else 0
                rps_val = f"{avg_rps:.0f} (Global)"

                # Latency Percentiles (Global from aggregated histogram)
                percentiles = calculate_percentiles(data["hist"])
                p50_val = f"{percentiles.get('p50', 0) / 1000:.2f} (Global)"
                p99_val = f"{percentiles.get('p99', 0) / 1000:.2f} (Global)"
                p999_val = f"{percentiles.get('p999', 0) / 1000:.2f} (Global)"

            # Pricing
            machine_type = TYPE_MAP.get(data["cores_str"])
            monthly_cost = 0
            efficiency = 0
            if machine_type and machine_type in prices:
                monthly_cost = prices[machine_type] * data["node_count"]
                if monthly_cost > 0:
                    efficiency = avg_rps / monthly_cost

            eff_str = f"{efficiency:.2f}"

            f.write(
                f"| {category} | {sub_label} | {data['node_count']}x {data['cores_str']} | {rps_val} | {p50_val} | {p99_val} | {p999_val} | {eff_str} |\n"
            )

    print("Summary table generated.")


def generate_plots(results, output_dir=OUTPUT_DIR):
    """
    Generates plots from processed results.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print("Generating plots...")

    categories = sorted(list(set(k[0] for k in results.keys())))

    for cat in categories:
        cat_data = {k: v for k, v in results.items() if k[0] == cat}

        # Construct Descriptive Title
        descriptions = []
        for (c, label), data in cat_data.items():
            desc = f"{label}: {data['node_count']}x{data['cores_str']}"
            descriptions.append(desc)
        title_suffix = f"\n({', '.join(descriptions)})"

        # Plot 1: Workload Transition
        fig, ax1 = plt.subplots()
        ax2 = ax1.twinx()

        colors = ["blue", "orange", "green"]

        for idx, ((_, label), data) in enumerate(cat_data.items()):
            color = colors[idx % len(colors)]

            seconds = sorted(data["rps"].keys())
            if not seconds:
                continue

            mean_rps = [np.mean(data["rps"][s]) for s in seconds]
            std_rps = [np.std(data["rps"][s]) for s in seconds]
            mean_p99 = [np.mean(data["p99"][s]) / 1000.0 for s in seconds]  # us to ms

            ax1.plot(
                seconds, mean_rps, label=f"{label} RPS", color=color, linestyle="-"
            )
            ax1.fill_between(
                seconds,
                np.array(mean_rps) - np.array(std_rps),
                np.array(mean_rps) + np.array(std_rps),
                color=color,
                alpha=0.1,
            )

            ax2.plot(
                seconds,
                mean_p99,
                label=f"{label} P99 Latency",
                color=color,
                linestyle="--",
            )

        ax1.set_xlabel("Time (s)")
        ax1.set_ylabel("Throughput (RPS)")
        ax2.set_ylabel("P99 Latency (ms)")
        ax1.set_title(f"Workload Transition: {cat}{title_suffix}")

        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

        plt.savefig(
            os.path.join(output_dir, f"workload_transition_{cat.replace(' ', '_')}.png")
        )
        plt.close()

        # Plot 2: Latency CDF
        plt.figure()
        ax = plt.gca()
        for idx, ((_, label), data) in enumerate(cat_data.items()):
            hist = data["hist"]
            if not hist:
                continue

            sorted_lats = sorted(hist.keys())
            total_reqs = sum(hist.values())

            x = []
            y = []
            running_sum = 0

            for lat in sorted_lats:
                count = hist[lat]
                running_sum += count
                percentile = running_sum / total_reqs

                if percentile >= 0.90:
                    x.append(lat / 1000.0)  # us to ms
                    y.append(percentile)

            plt.plot(x, y, label=label)

        for percentile, label in ((0.99, "p99"), (0.999, "p99.9")):
            ax.axhline(percentile, color="gray", linestyle="--", linewidth=1, alpha=0.8)
            ax.text(
                0.99,
                percentile,
                label,
                transform=ax.get_yaxis_transform(),
                ha="right",
                va="bottom",
                color="gray",
            )

        plt.xscale("log")
        plt.xlabel("Latency (ms) [Log Scale]")
        plt.ylabel("Percentile (CDF)")
        plt.title(f"Tail Latency CDF (P90-P99.9): {cat}{title_suffix}")
        plt.legend()
        plt.grid(True, which="both", ls="-")
        plt.savefig(
            os.path.join(output_dir, f"latency_cdf_{cat.replace(' ', '_')}.png")
        )
        plt.close()

    # Plot 4: Cost-Efficiency Index
    generate_cost_plot(results, output_dir)


def generate_cost_plot(results, output_dir):
    prices = load_pricing(PRICING_FILE)

    plt.figure()
    labels = []
    efficiencies = []
    colors = []
    sort_keys = []

    category_order = {
        "Budget Entry Level": 0,
        "Entry Level": 1,
        "Mid Range": 2,
        "High Perf": 3,
    }

    sub_label_order = {
        "Single": 0,
        "Cluster": 1,
        "Cluster (24x)": 2,
        "Cluster (48x)": 3,
    }

    for (category, sub_label), data in results.items():
        node_count = data["node_count"]
        cores_str = data["cores_str"]
        machine_type = TYPE_MAP.get(cores_str)

        if not machine_type or machine_type not in prices:
            print(f"Error: No pricing found for {machine_type} ({cores_str})")
            continue

        monthly_cost_per_node = prices[machine_type]
        total_monthly_cost = monthly_cost_per_node * node_count

        # Avg RPS from stats if available, else calc
        if "stats" in data and data["stats"]:
            avg_rps = data["stats"]["rps_mean"]
        else:
            total_ops = sum(sum(counts) for counts in data["rps"].values())
            num_seconds = len(data["rps"])
            num_runs = len(list(data["rps"].values())[0]) if num_seconds > 0 else 3
            avg_rps = total_ops / (num_seconds * num_runs) if num_seconds > 0 else 0

        efficiency = avg_rps / total_monthly_cost

        config_desc = f"{data['node_count']}x {data['cores_str']}"
        full_label = f"{category}\n({config_desc})"
        labels.append(full_label)
        efficiencies.append(efficiency)
        sort_keys.append(
            (
                category_order.get(category, 999),
                sub_label_order.get(sub_label, 999),
                full_label,
            )
        )

        if "Single" in sub_label:
            colors.append("blue")
        elif "Cluster" in sub_label:
            colors.append("orange")
        else:
            colors.append("gray")

    sorted_indices = sorted(range(len(labels)), key=lambda i: sort_keys[i])
    labels = [labels[i] for i in sorted_indices]
    efficiencies = [efficiencies[i] for i in sorted_indices]
    colors = [colors[i] for i in sorted_indices]

    bars = plt.bar(labels, efficiencies, color=colors)
    for bar, efficiency in zip(bars, efficiencies):
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{efficiency:.2f}",
            ha="center",
            va="bottom",
        )
    plt.ylabel("Efficiency Index (Avg RPS / $ Monthly)")
    plt.title("Cost-Efficiency Comparison")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "cost_efficiency.png"))
    plt.close()


def main():
    results = process_data()
    generate_markdown_table(results)
    generate_plots(results)
    print(f"Analysis complete. Results saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
