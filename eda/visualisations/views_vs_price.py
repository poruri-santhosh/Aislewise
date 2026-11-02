
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
from data_loader import load_data

df = load_data()
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
IMAGE_DIR = os.path.join(PROJECT_ROOT, "reports", "visualisations", "analytics")
os.makedirs(IMAGE_DIR, exist_ok=True)

fig, ax = plt.subplots(figsize=(10, 5))
image = ax.scatter(
    df["standard_price"],
    df["total_views"],
    c=df["average_rating"],
    cmap="viridis",
    alpha=0.55,
    s=18,
)
ax.set_yscale("symlog", linthresh=1)
ax.set_title(f"Listed price vs. recorded view events ({len(df):,} products)")
ax.set_xlabel("Listed product price (source units)")
ax.set_ylabel("Recorded view events (symlog scale)")
fig.colorbar(image, ax=ax, label="Product rating")

fig.tight_layout()
output_path = os.path.join(IMAGE_DIR, "product_price_vs_views.png")
fig.savefig(output_path, dpi=160, bbox_inches="tight")
plt.close(fig)
print(f"Visualization saved to: {output_path}")
import sys
import os

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

from data_loader import load_data

df = load_data()

# Calculate Pearson Correlation
correlation = df["standard_price"].corr(df["total_views"])
print(f"Correlation between Price and Views: {correlation:.4f}")