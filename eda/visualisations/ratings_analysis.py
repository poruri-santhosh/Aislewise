import os
import sys
import os

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from data_loader import load_data

df = load_data()

columns = ["standard_price", "total_views", "average_rating"]
correlation = df[columns].corr()
print("--- Correlation Matrix ---")
print(correlation)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
IMAGE_DIR = os.path.join(PROJECT_ROOT, "reports", "visualisations", "expanded")
os.makedirs(IMAGE_DIR, exist_ok=True)

fig, ax = plt.subplots(figsize=(8, 6))
image = ax.imshow(correlation, cmap="coolwarm", vmin=-1, vmax=1)
ax.set_xticks(np.arange(len(columns)), labels=columns, rotation=25, ha="right")
ax.set_yticks(np.arange(len(columns)), labels=columns)
for row in range(len(columns)):
    for column in range(len(columns)):
        ax.text(
            column,
            row,
            f"{correlation.iloc[row, column]:.2f}",
            ha="center",
            va="center",
            color="black",
        )
ax.set_title(f"Expanded product metric correlations ({len(df):,} products)")
fig.colorbar(image, ax=ax, label="Pearson correlation")
fig.tight_layout()

output_path = os.path.join(IMAGE_DIR, "product_metrics_correlation.png")
fig.savefig(output_path, dpi=160, bbox_inches="tight")
plt.close(fig)
print(f"Visualization saved to: {output_path}")