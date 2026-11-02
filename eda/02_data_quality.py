
from data_loader import load_data

df = load_data()

print("\n--- 1. MISSING VALUES ---")
print(df.isnull().sum())

print("\n--- 2. DUPLICATE ROWS ---")
print(df.duplicated().sum())

print("\n--- 3. DUPLICATE PRODUCT IDs ---")
print(df["asin"].duplicated().sum())

print("\n--- 4. INVALID VALUES ---")
print("Negative views:", (df["total_views"] < 0).sum())
print("Invalid prices:", (df["standard_price"] <= 0).sum())
print(
    "Invalid ratings:",
    (~df["average_rating"].between(0, 5)).sum()
)

print("\n--- 5. ZERO-VIEW PRODUCTS ---")
zero_views = df[df["total_views"] == 0]
print("Count:", len(zero_views))
if not zero_views.empty:
    print(zero_views[["asin", "product_title", "total_views"]].head(10).to_string(index=False))

print("\n--- 6. QUALITY CHECK COMPLETE ---")
