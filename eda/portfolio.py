"""Reusable product portfolio segmentation rules."""

HIGH_TRAFFIC_VIEWS = 20
HIGH_RATING = 4.2


def classify_product(total_views: float, average_rating: float) -> str:
    """Classify a product using the portfolio's inclusive traffic and rating gates."""
    high_traffic = total_views >= HIGH_TRAFFIC_VIEWS
    high_rating = average_rating >= HIGH_RATING

    if high_traffic and high_rating:
        return "Stars (High Traffic, High Rating)"
    if high_rating:
        return "Hidden Gems (Low Traffic, High Rating)"
    if high_traffic:
        return "At Risk (High Traffic, Low Rating)"
    return "Dead Weight (Low Traffic, Low Rating)"
