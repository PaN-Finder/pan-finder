import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.container import BarContainer


def plot_scores(
    scores_by_dataset: dict,
    runtimes_by_dataset: dict,
    avg_score: float,
    avg_runtime: float,
    output_path: Path,
):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10))

    # Plot scores
    for ds, scores in scores_by_dataset.items():
        ax1.plot(range(0, len(scores)), scores, marker="o", linestyle="-", label=ds)
    ax1.text(
        0.95,
        0.95,
        f"Average Score: {avg_score:.2f}",
        horizontalalignment="right",
        verticalalignment="top",
        transform=ax1.transAxes,
        bbox=dict(facecolor="white", alpha=0.5),
    )
    ax1.set_title("Query Scores by Dataset")
    ax1.set_xlabel("Query")
    ax1.set_ylabel("Score")
    ax1.legend()
    ax1.grid(True)

    # Plot query runtimes
    for ds, times in runtimes_by_dataset.items():
        ax2.plot(range(0, len(times)), times, marker="o", linestyle="-", label=ds)
    ax2.text(
        0.95,
        0.95,
        f"Average Query Time: {avg_runtime:.3f}s",
        horizontalalignment="right",
        verticalalignment="top",
        transform=ax2.transAxes,
        bbox=dict(facecolor="white", alpha=0.5),
    )
    ax2.set_title("Query Runtimes by Dataset")
    ax2.set_xlabel("Query")
    ax2.set_ylabel("Runtime (s)")
    ax2.legend()
    ax2.grid(True)

    max_queries = max(len(scores) for scores in scores_by_dataset.values())
    ax1.set_xticks(range(0, max_queries))
    ax2.set_xticks(range(0, max_queries))

    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def plot_query_score_breakdown(
    scores_by_dataset, breakdowns_by_dataset: dict, output_path: Path
):
    fig, axes = plt.subplots(2, 1, figsize=(10, 10), sharex=True)

    for ds, breakdowns in breakdowns_by_dataset.items():
        queries = range(0, len(breakdowns))
        score = scores_by_dataset[ds]
        overall = [b["overall"] for b in breakdowns]
        similarity = [b["similarity"] for b in breakdowns]
        chunk = [b["chunk_score"] for b in breakdowns]
        full_match_score = [b["full_match_score"] for b in breakdowns]
        partial_match_score = [b["partial_match_score"] for b in breakdowns]
        keyword = [b["keyword"] for b in breakdowns]

        # First subplot: Only the overall score
        axes[0].plot(queries, score, marker="o", linestyle="-", label=f"{ds} Score")

        # Second subplot: Breakdown components
        axes[1].plot(queries, overall, marker="*", linestyle=":", label=f"{ds} Overall")
        axes[1].plot(
            queries, similarity, marker="v", linestyle="--", label=f"{ds} Similarity"
        )
        axes[1].plot(queries, chunk, marker="^", linestyle="-", label=f"{ds} Chunk")
        axes[1].plot(
            queries,
            full_match_score,
            marker="s",
            linestyle="-.",
            label=f"{ds} full_match_score",
        )
        axes[1].plot(
            queries,
            partial_match_score,
            marker="D",
            linestyle="--",
            label=f"{ds} partial_match_score",
        )
        axes[1].plot(queries, keyword, marker="x", linestyle=":", label=f"{ds} Keyword")

    # Formatting first subplot
    axes[0].set_title("Calculated Scores by Dataset")
    axes[0].set_ylabel("Score")
    axes[0].legend()
    axes[0].grid(True)

    # Formatting second subplot
    axes[1].set_title(
        "Score Breakdown (Overall, Similarity, Chunk, Full Match, Partial Match, Keyword)"
    )
    axes[1].set_xlabel("Query Index")
    axes[1].set_ylabel("Score")
    axes[1].legend()
    axes[1].grid(True)

    # Ensure x-axis tick labels are whole numbers
    max_queries = max(len(breakdowns) for breakdowns in breakdowns_by_dataset.values())
    axes[1].set_xticks(range(0, max_queries))  # Ensure whole number ticks

    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def plot_stacked_bar_query_score_breakdown(
    scores_by_dataset, breakdowns_by_dataset: dict, output_path: Path
):
    # Create a figure with two subplots
    fig, axes = plt.subplots(2, 1, figsize=(10, 10), sharex=True)

    # First subplot: Overall scores as a line plot
    for ds, breakdowns in breakdowns_by_dataset.items():
        queries = range(0, len(breakdowns))
        score = scores_by_dataset[ds]
        axes[0].plot(queries, score, marker="o", linestyle="-", label=f"{ds} Score")

    axes[0].set_title("Calculated Scores by Dataset")
    axes[0].set_ylabel("Score")
    axes[0].legend()
    axes[0].grid(True)

    # Second subplot: Stacked bar chart for breakdown components (Similarity, Filter, Keyword)
    n_datasets = len(breakdowns_by_dataset)
    bar_width = 0.8 / n_datasets
    offsets = np.linspace(-0.4 + bar_width / 2, 0.4 - bar_width / 2, n_datasets)
    max_queries = max(len(breakdowns) for breakdowns in breakdowns_by_dataset.values())
    x = np.arange(max_queries)
    for i, (ds, breakdowns) in enumerate(breakdowns_by_dataset.items()):
        n_queries = len(breakdowns)
        similarity = np.array([float(b["similarity"]) for b in breakdowns], dtype=float)
        chunk = np.array([float(b["chunk_score"]) for b in breakdowns], dtype=float)
        full_match_score = np.array(
            [float(b["full_match_score"]) for b in breakdowns], dtype=float
        )
        partial_match_score = np.array(
            [float(b["partial_match_score"]) for b in breakdowns], dtype=float
        )
        keyword = np.array([float(b["keyword"]) for b in breakdowns], dtype=float)
        # Pad arrays if this dataset has fewer queries than max_queries
        if n_queries < max_queries:
            similarity = np.pad(similarity, (0, max_queries - n_queries), "constant")
            chunk = np.pad(chunk, (0, max_queries - n_queries), "constant")
            full_match_score = np.pad(
                full_match_score, (0, max_queries - n_queries), "constant"
            )
            partial_match_score = np.pad(
                partial_match_score, (0, max_queries - n_queries), "constant"
            )
            keyword = np.pad(keyword, (0, max_queries - n_queries), "constant")
        pos = x + offsets[i]
        axes[1].bar(pos, similarity, bar_width, label=f"{ds} Similarity")
        axes[1].bar(pos, chunk, bar_width, bottom=similarity, label=f"{ds} Chunk")
        axes[1].bar(
            pos,
            full_match_score,
            bar_width,
            bottom=similarity + chunk,
            label=f"{ds} Full Match",
        )
        axes[1].bar(
            pos,
            partial_match_score,
            bar_width,
            bottom=similarity + chunk + full_match_score,
            label=f"{ds} Partial Match",
        )
        axes[1].bar(
            pos,
            keyword,
            bar_width,
            bottom=similarity + chunk + full_match_score + partial_match_score,
            label=f"{ds} Keyword",
        )
    axes[1].set_title(
        "Score Breakdown (Stacked Bar: Similarity, Chunk, Full Match, Partial Match, Keyword)"
    )
    axes[1].set_xlabel("Query Index")
    axes[1].set_ylabel("Score")
    axes[1].legend()
    axes[1].grid(False)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([str(i) for i in x])

    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def plot_average_scores_per_dataset(
    results_df: pd.DataFrame, overall_test_metrics: dict, output_path: Path
):
    """
    Plots a summary of average scores per dataset across different tests,
    including the overall average score and runtime for each test in the legend.
    """
    # Pivot the table for easier plotting
    pivot_df = results_df.pivot(
        index="dataset_name", columns="test_name", values="avg_score_percent"
    )

    n_datasets = max(1, len(pivot_df.index))
    n_configs = max(1, len(pivot_df.columns))
    fig_width = max(12, min(18, 1.2 * n_datasets + 1.1 * n_configs))
    fig, ax = plt.subplots(figsize=(fig_width, 8))

    # Plotting
    pivot_df.plot(kind="bar", width=0.8, ax=ax)

    ax.set_title("Average Score (%) per Dataset Across Test Configurations", pad=12)
    ax.set_ylabel("Average Score (%)")
    ax.set_xlabel("Dataset Name")
    ax.tick_params(axis="x", rotation=35)
    for label in ax.get_xticklabels():
        label.set_ha("right")
    ax.grid(axis="y", linestyle="--", alpha=0.7)
    ax.set_ylim(0, 105)

    # Add individual bar labels
    for container in ax.containers:
        if isinstance(container, BarContainer):
            ax.bar_label(
                container, fmt="%.1f", label_type="edge", padding=2, fontsize=8
            )

    handles, labels = ax.get_legend_handles_labels()

    if handles:
        ax.legend(
            handles,
            labels,
            title="Test Configuration",
            loc="upper left",
            bbox_to_anchor=(1.01, 1.0),
            ncols=1,
            frameon=False,
        )

    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)


def plot_score_distribution_boxplot(
    raw_scores_by_test_config_path: Path, output_path: Path
):
    """
    Plots a box plot of the score distribution for multiple tests.
    """
    try:
        with open(raw_scores_by_test_config_path) as f:
            all_scores_by_test = json.load(f)
    except FileNotFoundError:
        print(f"Error: The file {raw_scores_by_test_config_path} was not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {raw_scores_by_test_config_path}.")
        return

    if not all_scores_by_test or not isinstance(all_scores_by_test, dict):
        print("No valid scores data available in the JSON file to generate box plot.")
        return

    test_names = list(all_scores_by_test.keys())
    score_data = []
    valid_test_names = []

    for name in test_names:
        scores = all_scores_by_test[name]
        if (
            scores
            and isinstance(scores, list)
            and all(isinstance(s, (int, float)) for s in scores)
        ):  # Ensure data is not empty and is a list of numbers
            score_data.append(scores)
            valid_test_names.append(name)

    if not score_data:
        print("All score lists are empty or invalid. Cannot generate box plot.")
        return

    fig, ax = plt.subplots(
        figsize=(max(10, 1.5 * len(valid_test_names)), 7)
    )  # Adjust width based on number of tests

    boxplot_parts = ax.boxplot(
        score_data, patch_artist=True, medianprops=dict(color="red", linewidth=1.5)
    )

    # Customizing colors for better distinction
    colors = plt.cm.get_cmap("viridis", len(valid_test_names))
    for i, patch in enumerate(boxplot_parts["boxes"]):
        # Directly use the colormap with the discrete index
        patch.set_facecolor(colors(i))
        patch.set_alpha(0.7)

    ax.set_title("Score Distribution by Test Configuration (Box Plot)")
    ax.set_ylabel("Score")
    ax.set_xlabel("Test Configuration")
    ax.set_xticks(np.arange(1, len(valid_test_names) + 1))
    ax.set_xticklabels(valid_test_names, rotation=45, ha="right")
    ax.grid(True, linestyle="--", alpha=0.7, axis="y")
    ax.set_ylim(-0.05, 1.05)  # Scores are typically between 0 and 1

    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    print(f"Box plot saved to {output_path}")


def plot_score_distribution_stripplot(
    raw_scores_by_test_config_path: Path, output_path: Path
):
    """
    Plots a strip plot of the score distribution for multiple tests.
    """
    try:
        with open(raw_scores_by_test_config_path) as f:
            all_scores_by_test = json.load(f)
    except FileNotFoundError:
        print(f"Error: The file {raw_scores_by_test_config_path} was not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {raw_scores_by_test_config_path}.")
        return

    if not all_scores_by_test or not isinstance(all_scores_by_test, dict):
        print("No valid scores data available in the JSON file to generate strip plot.")
        return

    plot_data = []
    for test_name, scores in all_scores_by_test.items():
        if (
            scores
            and isinstance(scores, list)
            and all(isinstance(s, (int, float)) for s in scores)
        ):
            for score in scores:
                plot_data.append({"test_name": test_name, "score": score})
        else:
            print(
                f"Warning: Invalid or empty score list for test '{test_name}'. Skipping."
            )

    if not plot_data:
        print("No valid scores to plot after processing. Cannot generate strip plot.")
        return

    df = pd.DataFrame(plot_data)

    # Determine unique test names for ordering and coloring
    unique_test_names = df["test_name"].unique()

    fig, ax = plt.subplots(
        figsize=(max(10, 1.5 * len(unique_test_names)), 7)
    )  # Adjust width

    # Create the strip plot
    sns.stripplot(
        x="test_name",
        y="score",
        hue="test_name",
        data=df,
        ax=ax,
        jitter=True,
        alpha=0.7,
        palette="viridis",  # Use a palette for distinct colors per category
        order=unique_test_names,  # Ensure consistent order
        legend=False,  # Disable legend as hue is used for coloring x categories
    )

    ax.set_title("Score Distribution by Test Configuration (Strip Plot)")
    ax.set_ylabel("Score")
    ax.set_xlabel("Test Configuration")
    ax.set_xticks(np.arange(len(unique_test_names)))
    ax.set_xticklabels(unique_test_names, rotation=45, ha="right")
    ax.grid(True, linestyle="--", alpha=0.7, axis="y")
    ax.set_ylim(-0.05, 1.05)  # Scores are typically between 0 and 1

    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    print(f"Strip plot saved to {output_path}")


def plot_knee_point_distribution(knee_data_path: Path, output_path: Path):
    """
    Plots distribution of knee point statistics.

    Args:
        knee_data_path: Path to JSON file containing knee point data
        output_path: Path to save the generated plot
    """
    try:
        with open(knee_data_path) as f:
            knee_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: The file {knee_data_path} was not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {knee_data_path}.")
        return

    if not knee_data or not isinstance(knee_data, dict):
        print("No valid knee point data available in the JSON file.")
        return

    # Extract data for plotting
    all_stats = []
    for test_name, test_data in knee_data.items():
        for query_stats in test_data:
            query_stats["test_name"] = test_name
            all_stats.append(query_stats)

    if not all_stats:
        print("No knee point statistics found to plot.")
        return

    df = pd.DataFrame(all_stats)

    # Create subplots - 2x4 grid for 8 plots
    fig, axes = plt.subplots(2, 4, figsize=(24, 12))
    fig.suptitle("Knee Point Filtering Statistics Distribution", fontsize=16)

    # Plot 1: Original vs Filtered count
    axes[0, 0].scatter(df["original_count"], df["filtered_count"], alpha=0.6)
    axes[0, 0].plot(
        [0, df["original_count"].max()],
        [0, df["original_count"].max()],
        "r--",
        alpha=0.8,
    )
    axes[0, 0].set_xlabel("Original Result Count")
    axes[0, 0].set_ylabel("Filtered Result Count")
    axes[0, 0].set_title("Original vs Filtered Results")
    axes[0, 0].grid(True, alpha=0.3)

    # Plot 2: Filtering effectiveness (percentage kept)
    df["percentage_kept"] = (df["filtered_count"] / df["original_count"] * 100).fillna(
        100
    )
    sns.histplot(data=df, x="percentage_kept", bins=20, ax=axes[0, 1])
    axes[0, 1].set_xlabel("Percentage of Results Kept (%)")
    axes[0, 1].set_ylabel("Frequency")
    axes[0, 1].set_title("Distribution of Filtering Effectiveness")
    axes[0, 1].grid(True, alpha=0.3)

    # Plot 3: Knee index distribution
    valid_knee_df = df[df["knee_index"] >= 0]
    if not valid_knee_df.empty:
        sns.histplot(data=valid_knee_df, x="knee_index", bins=20, ax=axes[0, 2])
        axes[0, 2].set_xlabel("Knee Point Index")
        axes[0, 2].set_ylabel("Frequency")
        axes[0, 2].set_title("Distribution of Knee Point Positions")
        axes[0, 2].grid(True, alpha=0.3)
    else:
        axes[0, 2].text(
            0.5,
            0.5,
            "No valid knee indices found",
            transform=axes[0, 2].transAxes,
            ha="center",
            va="center",
        )
        axes[0, 2].set_title("Distribution of Knee Point Positions")

    # Plot 4: Knee point value distribution
    valid_knee_value_df = df[df["knee_point_value"] >= 0]  # Include 0 values
    if not valid_knee_value_df.empty:
        sns.histplot(
            data=valid_knee_value_df, x="knee_point_value", bins=20, ax=axes[0, 3]
        )
        axes[0, 3].set_xlabel("Knee Point Value (Score)")
        axes[0, 3].set_ylabel("Frequency")
        axes[0, 3].set_title("Distribution of Knee Point Values")
        axes[0, 3].grid(True, alpha=0.3)

        # Add statistical info
        mean_val = valid_knee_value_df["knee_point_value"].mean()
        median_val = valid_knee_value_df["knee_point_value"].median()
        axes[0, 3].axvline(
            mean_val,
            color="red",
            linestyle="--",
            alpha=0.7,
            label=f"Mean: {mean_val:.3f}",
        )
        axes[0, 3].axvline(
            median_val,
            color="orange",
            linestyle="--",
            alpha=0.7,
            label=f"Median: {median_val:.3f}",
        )
        axes[0, 3].legend(fontsize=8)
    else:
        axes[0, 3].text(
            0.5,
            0.5,
            "No valid knee point values found",
            transform=axes[0, 3].transAxes,
            ha="center",
            va="center",
        )
        axes[0, 3].set_title("Distribution of Knee Point Values")

    # Plot 5: Max distance from line
    valid_distance_df = df[df["max_distance"] >= 0]
    if not valid_distance_df.empty:
        sns.histplot(data=valid_distance_df, x="max_distance", bins=20, ax=axes[1, 0])
        axes[1, 0].set_xlabel("Max Distance from Line")
        axes[1, 0].set_ylabel("Frequency")
        axes[1, 0].set_title("Distribution of Knee Point Distances")
        axes[1, 0].grid(True, alpha=0.3)
    else:
        axes[1, 0].text(
            0.5,
            0.5,
            "No valid distances found",
            transform=axes[1, 0].transAxes,
            ha="center",
            va="center",
        )
        axes[1, 0].set_title("Distribution of Knee Point Distances")

    # Plot 6: Top score distribution
    sns.histplot(data=df, x="top_score", bins=20, ax=axes[1, 1])
    axes[1, 1].set_xlabel("Top Score")
    axes[1, 1].set_ylabel("Frequency")
    axes[1, 1].set_title("Distribution of Top Scores")
    axes[1, 1].grid(True, alpha=0.3)

    # Plot 7: Threshold flags summary
    threshold_data = []
    for _, row in df.iterrows():
        threshold_data.append(
            {
                "linearity_met": row["linearity_threshold_met"],
                "min_results_met": row["min_results_threshold_met"],
                "min_top_score_met": row["min_top_score_threshold_met"],
            }
        )

    threshold_df = pd.DataFrame(threshold_data)
    threshold_counts = {
        "Linearity": threshold_df["linearity_met"].sum(),
        "Min Results": threshold_df["min_results_met"].sum(),
        "Min Top Score": threshold_df["min_top_score_met"].sum(),
    }

    bars = axes[1, 2].bar(threshold_counts.keys(), threshold_counts.values())
    axes[1, 2].set_ylabel("Count")
    axes[1, 2].set_title("Threshold Conditions Met")
    axes[1, 2].grid(True, alpha=0.3)

    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        axes[1, 2].text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{int(height)}",
            ha="center",
            va="bottom",
        )

    # Plot 8: Knee point value vs filtering effectiveness
    if "knee_point_value" in df.columns:
        # Only plot points where knee point filtering actually occurred
        filtered_df = df[(df["knee_point_value"] > 0) & (df["percentage_kept"] < 100)]
        if not filtered_df.empty:
            axes[1, 3].scatter(
                filtered_df["knee_point_value"],
                filtered_df["percentage_kept"],
                alpha=0.6,
            )
            axes[1, 3].set_xlabel("Knee Point Value (Score)")
            axes[1, 3].set_ylabel("Percentage Kept (%)")
            axes[1, 3].set_title("Knee Point Value vs Filtering Effectiveness")
            axes[1, 3].grid(True, alpha=0.3)
        else:
            axes[1, 3].text(
                0.5,
                0.5,
                "No filtering events found",
                transform=axes[1, 3].transAxes,
                ha="center",
                va="center",
            )
            axes[1, 3].set_title("Knee Point Value vs Filtering Effectiveness")
    else:
        axes[1, 3].text(
            0.5,
            0.5,
            "Knee point value data not available",
            transform=axes[1, 3].transAxes,
            ha="center",
            va="center",
        )
        axes[1, 3].set_title("Knee Point Value vs Filtering Effectiveness")

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Knee point distribution plot saved to {output_path}")


def plot_overall_changes(results_dir: Path, output_path: Path):
    """
    Reads all 'results_*.csv' files from the specified directory,
    calculates the average 'avg_score_percent' for each 'test_name' per file,
    and plots these averages over time (represented by file timestamps).

    Args:
        results_dir (Path): Directory containing the 'results_*.csv' files.
        output_path (Path): Path to save the generated plot.
    """
    all_file_data = []

    # Find and sort CSV files by name (assuming filename contains sortable timestamp, e.g., YYYYMMDD_HHMMSS)
    csv_files = sorted(list(results_dir.glob("results_*.csv")))

    if not csv_files:
        print(f"No 'results_*.csv' files found in {results_dir}.")
        return

    for file_path in csv_files:
        try:
            # Extract timestamp string from filename, e.g., "results_20230101_120000.csv" -> "20230101_120000"
            timestamp_str = file_path.stem.replace("results_", "")
            df = pd.read_csv(file_path)

            if df.empty:
                # Optionally, print a warning: print(f"Warning: {file_path.name} is empty. Skipping.")
                continue

            required_columns = {"test_name", "avg_score_percent"}
            if not required_columns.issubset(df.columns):
                missing_cols = required_columns - set(df.columns)
                print(
                    f"Warning: {file_path.name} is missing required columns: {missing_cols}. Skipping."
                )
                continue

            # Calculate average score per test_name for the current file
            avg_scores_for_file = (
                df.groupby("test_name")["avg_score_percent"].mean().reset_index()
            )
            avg_scores_for_file["timestamp"] = timestamp_str
            all_file_data.append(avg_scores_for_file)
        except pd.errors.EmptyDataError:
            # Optionally, print a warning for empty/malformed CSVs
            # print(f"Warning: {file_path.name} is empty or malformed (pandas EmptyDataError). Skipping.")
            continue
        except Exception as e:
            print(f"Error processing file {file_path.name}: {e}. Skipping.")
            continue

    if not all_file_data:
        print("No data collected from CSV files. Cannot generate plot.")
        return

    overall_df = pd.concat(all_file_data, ignore_index=True)

    if overall_df.empty:
        print("Collected data is empty after concatenation. Cannot generate plot.")
        return

    # Pivot table: timestamps as index, test_names as columns, avg_score_percent as values
    try:
        pivot_df = overall_df.pivot(
            index="timestamp", columns="test_name", values="avg_score_percent"
        )
    except Exception as e:
        # This error might occur if (timestamp, test_name) pairs are not unique after aggregation,
        # though the current logic should prevent this.
        print(f"Error pivoting data: {e}. Please check data integrity.")
        return

    if pivot_df.empty:
        print("Pivoted data is empty. Cannot generate plot.")
        return

    n_timestamps = max(1, len(pivot_df.index))
    n_configs = max(1, len(pivot_df.columns))
    fig_width = max(11, min(18, 7 + 0.35 * n_timestamps + 0.6 * n_configs))
    fig, (ax1, ax2) = plt.subplots(
        2,
        1,
        figsize=(fig_width, 10),
        sharex=True,
        gridspec_kw={"height_ratios": [1.05, 0.95]},
    )

    # Plot individual test configurations on the first subplot (ax1)
    numeric_cols_to_plot = pivot_df.select_dtypes(include=np.number).columns
    if not pivot_df[numeric_cols_to_plot].empty:
        pivot_df[numeric_cols_to_plot].plot(kind="line", marker="o", ax=ax1)
    else:
        # Handle case where there are no numeric columns to plot from pivot_df
        pass

    ax1.set_title("Average Score (%) Over Time by Test Configuration")
    ax1.set_ylabel("Average Score (%)")
    ax1.grid(True, linestyle="--", alpha=0.7)
    ax1.set_ylim(70, 90)

    handles, labels = ax1.get_legend_handles_labels()
    if handles:
        ax1.legend(
            handles,
            labels,
            title="Test Configuration",
            loc="upper left",
            bbox_to_anchor=(1.01, 1.0),
            ncols=1,
            frameon=False,
        )

    # Annotate individual test lines on ax1
    for test_name in pivot_df.columns:
        if pd.api.types.is_numeric_dtype(
            pivot_df[test_name]
        ):  # Annotate only numeric series
            for timestamp_idx, score in enumerate(pivot_df[test_name]):
                if pd.notna(score):
                    ax1.text(
                        timestamp_idx,
                        score,
                        f"{score:.1f}",
                        fontsize=9,
                        ha="left",
                        va="bottom",
                        color="black",
                        alpha=0.7,
                    )

    # Calculate and plot overall average line on the second subplot (ax2)
    overall_avg_scores = pd.Series(dtype=float)  # Initialize as empty
    if not pivot_df.empty:
        numeric_pivot_df = pivot_df.select_dtypes(include=np.number)
        if not numeric_pivot_df.empty and numeric_pivot_df.shape[1] > 0:
            overall_avg_scores = numeric_pivot_df.mean(axis=1)
            overall_avg_scores.plot(
                ax=ax2,
                label="Overall Average",  # This label is for the line itself, not a legend title
                color="black",
                linewidth=2.5,
                marker="D",
                linestyle="--",
                markersize=7,
            )

    ax2.set_title("Overall Average Score (%) Across All Configurations")
    ax2.set_xlabel("Result File Timestamp")
    ax2.set_ylabel("Average Score (%)")
    ax2.grid(True, linestyle="--", alpha=0.7)
    ax2.set_ylim(70, 90)  # Consistent Y-axis with ax1

    # Annotate overall average line on ax2
    if not overall_avg_scores.empty:
        for timestamp_idx, score in enumerate(overall_avg_scores):
            if pd.notna(score):
                x_text = timestamp_idx  # Offset for x-coordinate
                y_text = score - 0.4  # Offset for y-coordinate
                ax2.text(
                    x_text,
                    y_text,
                    f"{score:.1f}",
                    fontsize=9,
                    ha="right",
                    va="top",
                    color="black",
                    fontweight="bold",
                    alpha=0.9,
                )

    # Manage X-axis ticks and labels for the shared x-axis (applies to ax2, which is bottom)
    if n_timestamps > 0:
        if n_timestamps > 15:
            step = max(1, n_timestamps // 15)
            # Set ticks for ax2, ax1 will share them
            ax2.set_xticks(np.arange(0, n_timestamps, step))
            ax2.set_xticklabels(pivot_df.index[::step], rotation=45, ha="right")
        else:
            ax2.set_xticks(np.arange(0, n_timestamps))
            ax2.set_xticklabels(pivot_df.index, rotation=45, ha="right")

    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)
    print(f"Overall changes plot saved to {output_path}")
