#!/usr/bin/env python3

import argparse

import pandas as pd
import matplotlib.pyplot as plt


def main():
    # get args
    parser = argparse.ArgumentParser(
        description="Analyze Valkey benchmark results from one or more CSV files and generate comparative plots.",
    )
    _ = parser.add_argument(
        "files",
        nargs="+",
        help="One or more path(s) to the benchmark result CSV files.",
    )
    args = parser.parse_args()

    # load data
    input_file = args.files[0]
    print(f"Analyzing: {input_file}\n")
    df = pd.read_csv(input_file, comment="#")

    # pre-process data
    df["FinishedAt"] = pd.to_datetime(df["FinishedAt"], unit="s")
    run_start_time = df["FinishedAt"].min()
    df["Elapsed"] = df["FinishedAt"] - run_start_time
    df.set_index("Elapsed", inplace=True)

    # calculate P50, P90, P95, P99, P99.99 and success-rate
    benchmark_summary = df["Latency(us)"].describe(
        percentiles=[0.5, 0.9, 0.95, 0.99, 0.999]
    )
    benchmark_summary.loc["set-success_rate"] = df[df["OperationType"] == "SET"][
        "Success"
    ].mean()
    benchmark_summary.loc["get-success_rate"] = df[df["OperationType"] == "GET"][
        "Success"
    ].mean()
    print(benchmark_summary)

    # Bar chart of percentiles, success rate, goodput per second
    # g = sns.barplot(data=benchmark_summary)
    # g.figure.show()

    # Success Rate Over Time for SET Operation
    df_filtered = df[df["OperationType"] == "SET"]
    success_rate_over_time = df_filtered["Success"].resample("1s").mean().ffill()
    fig, ax = plt.subplots(figsize=(30, 14))
    success_rate_over_time.plot(ax=ax, label=input_file)
    ax.set_title("Success Rate Over Time SET Operations", fontsize=16)
    ax.set_xlabel("Time", fontsize=12)
    ax.set_ylabel("Success Rate (per second)", fontsize=12)
    ax.legend()
    fig.show()

    # Success Rate Over Time for GET Operation
    df_filtered = df[df["OperationType"] == "GET"]
    success_rate_over_time = df_filtered["Success"].resample("1s").mean().ffill()
    fig, ax = plt.subplots(figsize=(30, 14))
    success_rate_over_time.plot(ax=ax, label=input_file)
    ax.set_title("Success Rate Over Time GET Operations", fontsize=16)
    ax.set_xlabel("Time", fontsize=12)
    ax.set_ylabel("Success Rate (per second)", fontsize=12)
    ax.legend()
    fig.show()

    # Latency P50 over time

    # Latency P99 over time

    # Throughput over time
    # throughput_over_time = df.resample("1s").sum().ffill()
    # fig, ax = plt.subplots(figsize=(30, 14))
    # goodput_over_time.plot(ax=ax, label=input_file)
    # ax.set_title("Throughput over time", fontsize=16)
    # ax.set_xlabel("Time", fontsize=12)
    # ax.set_ylabel("Throughput (per second)", fontsize=12)
    # ax.legend()
    # fig.show()


if __name__ == "__main__":
    main()
    input()
