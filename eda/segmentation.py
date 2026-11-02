import os
import sys

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from portfolio import HIGH_RATING, HIGH_TRAFFIC_VIEWS

csv_path = os.path.join(
    os.path.dirname(__file__),
    "..",
    "data",
    "expanded",
    "product_segmentation_recommendations.csv",
)

df = pd.read_csv(csv_path)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
IMAGE_DIR = os.path.join(PROJECT_ROOT, "reports", "visualisations", "expanded")
os.makedirs(IMAGE_DIR, exist_ok=True)

plt.figure(figsize=(11, 7))

# Color mapping for the segments present in your dataset
palette = {
    "Stars (High Traffic, High Rating)": "#2ca02c",  # Green
    "Hidden Gems (Low Traffic, High Rating)": "#1f77b4",  # Blue
    "At Risk (High Traffic, Low Rating)": "#ff7f0e",  # Orange
    "Dead Weight (Low Traffic, Low Rating)": "#d62728",  # Red
}

for segment, color in palette.items():
    subset = df[df["segment"] == segment]
    if not subset.empty:
        plt.scatter(
            subset["average_rating"],
            subset["total_views"],
            c=color,
            label=f"{segment} ({len(subset)})",
            alpha=0.8,
            edgecolors="k",
            linewidths=0.5,
            s=70,
        )

# Exact business logic gates used in your segmentation script
RATING_GATE = HIGH_RATING
TRAFFIC_GATE = HIGH_TRAFFIC_VIEWS

plt.axvline(
    x=RATING_GATE,
    color="gray",
    linestyle="--",
    linewidth=1.2,
    label=f"Rating Threshold ({RATING_GATE})",
)
plt.axhline(
    y=TRAFFIC_GATE,
    color="gray",
    linestyle="--",
    linewidth=1.2,
    label=f"Traffic Threshold ({TRAFFIC_GATE})",
)

plt.title(
    f"Aislewise Expanded Product Portfolio ({len(df):,} products)",
    fontsize=14,
    fontweight="bold",
    pad=15,
)
plt.xlabel("Average Rating (Stars)", fontsize=11, fontweight="bold")
plt.ylabel("Recorded view events (symlog scale)", fontsize=11, fontweight="bold")
plt.yscale("symlog", linthresh=1)
plt.legend(loc="upper left", bbox_to_anchor=(1, 1), frameon=True)
plt.grid(True, linestyle=":", alpha=0.5)
plt.tight_layout()

output_path = os.path.join(IMAGE_DIR, "SEGMENTATION.png")
plt.savefig(output_path, dpi=160, bbox_inches="tight")
plt.close()
print(f"Visualization saved to: {output_path}")