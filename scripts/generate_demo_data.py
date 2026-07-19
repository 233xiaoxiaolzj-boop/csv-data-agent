"""Generate a deterministic, richer e-commerce CSV for local demos."""

from __future__ import annotations

import csv
import random
from datetime import date
from pathlib import Path

SEED = 20260719
REGIONS = ("South", "East", "North", "West")
CHANNELS = ("Marketplace", "Direct", "Social")
PRODUCTS = {
    "Electronics": (("Earbuds", 199), ("Smart Watch", 399)),
    "Home": (("Desk Lamp", 89), ("Storage Box", 49)),
    "Beauty": (("Skin Care Set", 159), ("Hair Dryer", 229)),
    "Sports": (("Yoga Mat", 99), ("Fitness Band", 79)),
}


def generate_rows(seed: int = SEED):
    random_generator = random.Random(seed)
    order_number = 1
    for year in (2024, 2025):
        for month in range(1, 13):
            for region in REGIONS:
                for channel in CHANNELS:
                    for category, products in PRODUCTS.items():
                        for _ in range(random_generator.randint(3, 6)):
                            product, base_price = random_generator.choice(products)
                            units = random_generator.randint(1, 12)
                            discount_rate = random_generator.choice((0, 0, 0.05, 0.1, 0.15))
                            unit_price = round(base_price * random_generator.uniform(0.95, 1.05), 2)
                            shipping_days = max(1, int(random_generator.gauss(3.8, 1.4)))
                            returned = int(
                                random_generator.random()
                                < 0.035 + (0.025 if shipping_days >= 6 else 0)
                            )
                            yield {
                                "order_date": date(
                                    year,
                                    month,
                                    random_generator.randint(1, 28),
                                ).isoformat(),
                                "order_id": f"ORD-{order_number:06d}",
                                "region": region,
                                "channel": channel,
                                "category": category,
                                "product": product,
                                "units": units,
                                "unit_price": unit_price,
                                "discount_rate": discount_rate,
                                "returned": returned,
                                "shipping_days": shipping_days,
                            }
                            order_number += 1


def main() -> None:
    output_path = Path(__file__).resolve().parents[1] / "sample_data" / "ecommerce_sales.csv"
    rows = list(generate_rows())
    with output_path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {len(rows):,} rows at {output_path}")


if __name__ == "__main__":
    main()
