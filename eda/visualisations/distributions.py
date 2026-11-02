import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from data_loader import load_data


df = load_data()
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
IMAGE_DIR = os.path.join(PROJECT_ROOT, "reports", "visualisations", "expanded")
os.makedirs(IMAGE_DIR, exist_ok=True)

fig, ax = plt.subplots(figsize=(10, 5))
ax.hist(np.log1p(df["total_views"]), bins=40, edgecolor="white", color="#4278c5")
ax.set_title(f"Recorded view-event distribution ({len(df):,} products)")
ax.set_xlabel("log(1 + recorded view events per product)")
ax.set_ylabel("Products")
ax.grid(axis="y", alpha=0.2)
fig.tight_layout()
output_path = os.path.join(IMAGE_DIR, "product_views_distribution.png")
fig.savefig(output_path, dpi=160, bbox_inches="tight")
plt.close(fig)
print(f"Visualization saved to: {output_path}")
