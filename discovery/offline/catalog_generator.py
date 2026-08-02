"""
discovery.offline.catalog_generator — Real BigBasket Dataset Blinkit Catalog Generator.
Parses 27,555+ real product items from BigBasket Products.csv and maps them to Blinkit's 35-L1 taxonomy.
"""

import os
import csv
import json
import random
from typing import List, Dict, Any
from discovery.core.types import Candidate

DATASET_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "BigBasket Products.csv")
CATALOG_JSON_PATH = os.path.join(os.path.dirname(__file__), "catalog_1100.json")

# Emoji mapping per L1 ID
L1_EMOJI_MAP = {
  1: "🥦", 2: "🌾", 3: "🪔", 4: "🥛", 5: "🍪", 6: "🥜", 7: "🍗", 8: "🍳",
  9: "🥔", 10: "🍫", 11: "🧃", 12: "☕", 13: "🍜", 14: "🍯", 15: "🌿", 16: "🍦",
  17: "🧴", 18: "💇‍♀️", 19: "✨", 20: "💄", 21: "🌸", 22: "👶", 23: "💊", 24: "🧼",
  25: "🛋️", 26: "🧹", 27: "🔌", 28: "📚", 29: "🐶", 30: "🧳", 31: "⚽", 32: "🪔",
  33: "👕", 34: "💍", 35: "🌐"
}

def map_bigbasket_row(category: str, sub_category: str, product_name: str) -> tuple:
    c = (category or "").strip()
    s = (sub_category or "").strip()
    p = (product_name or "").lower()
    s_low = s.lower()
    c_low = c.lower()

    if 'pet' in s_low or 'dog' in p or 'cat' in p or 'pet food' in p:
        return 29, 'Pet Care', 'pets'
    if 'pooja' in s_low or 'lamp' in p or 'diya' in p or 'incense' in p:
        return 32, 'Spiritual & Puja', 'spiritual'
    if 'baby' in c_low or 'baby' in s_low or 'diaper' in p or 'wipes' in p:
        return 22, 'Baby Care', 'baby'
    if 'fruit' in s_low or 'vegetable' in s_low or c == 'Fruits & Vegetables':
        return 1, 'Vegetables & Fruits', 'produce'
    if 'atta' in s_low or 'flours' in s_low or 'rice' in s_low or 'dals' in s_low:
        return 2, 'Atta, Rice & Dal', 'staples'
    if 'oil' in s_low or 'ghee' in s_low or 'masala' in s_low or 'spices' in s_low:
        return 3, 'Oil, Ghee & Masala', 'staples'
    if 'dairy' in s_low or 'milk' in s_low or 'egg' in c_low or 'egg' in s_low or 'paneer' in p:
        return 4, 'Dairy, Bread & Eggs', 'dairy'
    if 'bakery' in s_low or 'cookie' in s_low or 'biscuit' in p or 'rusk' in s_low or 'bread' in p:
        return 5, 'Bakery & Biscuits', 'snacks'
    if 'dry fruit' in s_low or 'cereal' in s_low or 'oat' in p or 'almond' in p or 'cashew' in p:
        return 6, 'Dry Fruits & Cereals', 'staples'
    if 'meat' in c_low or 'fish' in c_low or 'chicken' in p or 'mutton' in s_low or 'seafood' in s_low:
        return 7, 'Chicken, Meat & Fish', 'instant'
    if 'utensil' in s_low or 'cookware' in s_low or 'crockery' in s_low or 'kitchen' in s_low:
        return 8, 'Kitchenware & Appliances', 'cleaning'
    if 'chip' in s_low or 'namkeen' in s_low or 'snack' in s_low or 'popcorn' in p:
        return 9, 'Chips & Namkeen', 'snacks'
    if 'chocolate' in s_low or 'sweet' in s_low or 'candy' in s_low or 'toffee' in p:
        return 10, 'Sweets & Chocolates', 'snacks'
    if 'tea' in s_low or 'coffee' in s_low:
        return 12, 'Tea, Coffee & Milk Drinks', 'drinks'
    if 'drink' in s_low or 'juice' in s_low or 'water' in s_low or c == 'Beverages' or 'soda' in p:
        return 11, 'Drinks & Juices', 'drinks'
    if 'noodle' in s_low or 'pasta' in s_low or 'ready to eat' in s_low or 'instant' in p or 'maggi' in p:
        return 13, 'Instant Food', 'instant'
    if 'pickle' in s_low or 'spread' in s_low or 'sauce' in s_low or 'ketchup' in p or 'jam' in p:
        return 14, 'Sauces & Spreads', 'staples'
    if 'ice cream' in s_low or 'dessert' in s_low or 'kulfi' in p:
        return 16, 'Ice Creams & More', 'snacks'
    if 'hair' in s_low or 'shampoo' in p or 'conditioner' in p or 'comb' in p:
        return 18, 'Hair', 'personal'
    if 'skin' in s_low or 'face' in s_low or 'lotion' in p or 'cream' in p:
        return 19, 'Skin & Face', 'personal'
    if 'makeup' in s_low or 'cosmetic' in s_low or 'nail' in p or 'lipstick' in p:
        return 20, 'Beauty & Cosmetics', 'personal'
    if 'sanitary' in s_low or 'pad' in p or 'tampon' in p or 'hygiene' in s_low:
        return 21, 'Feminine Hygiene', 'personal'
    if 'health' in s_low or 'pharma' in s_low or 'medicine' in p or 'sanitizer' in p:
        return 23, 'Health & Pharma', 'pharmacy'
    if 'clean' in s_low or 'detergent' in s_low or 'freshener' in s_low or 'mop' in s_low:
        return 26, 'Cleaners & Repellents', 'cleaning'
    if 'stationery' in s_low or 'game' in s_low or 'pen' in p or 'toy' in p:
        return 28, 'Stationery & Games', 'cleaning'
    if 'bag' in s_low or 'travel' in s_low or 'luggage' in p:
        return 30, 'Travel', 'cleaning'
    if 'sport' in s_low or 'fitness' in s_low or 'dumbell' in p:
        return 31, 'Sports & Fitness', 'cleaning'
    if c == 'Gourmet & World Food':
        return 35, 'Imported Store', 'imported'

    return 25, 'Home & Lifestyle', 'cleaning'

def extract_pack_size(title: str, type_str: str) -> str:
    words = title.split()
    for i, w in enumerate(words):
        if any(c.isdigit() for c in w) and any(unit in w.lower() for unit in ['g', 'kg', 'ml', 'l', 'pc', 'pack', 'mg', 's']):
            return w
        if w.isdigit() and i + 1 < len(words) and words[i+1].lower() in ['g', 'kg', 'ml', 'l', 'pcs', 'pack', 'mg']:
            return f"{w} {words[i+1]}"
    return type_str or "1 unit"

def generate_catalog_from_bigbasket(max_items: int = 3000) -> List[Candidate]:
    random.seed(42)
    candidates = []
    
    if not os.path.exists(DATASET_CSV_PATH):
        raise FileNotFoundError(f"Dataset CSV not found at {DATASET_CSV_PATH}")

    sku_id = 1001
    with open(DATASET_CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
        # Sample evenly across rows
        sampled_rows = rows[:max_items] if len(rows) > max_items else rows

        for row in sampled_rows:
            product_name = (row.get("product") or "").strip()
            category = (row.get("category") or "").strip()
            sub_cat = (row.get("sub_category") or "").strip()
            brand = (row.get("brand") or "").strip()
            type_str = (row.get("type") or "").strip()
            
            try:
                sale_price = float(row.get("sale_price", 50))
                market_price = float(row.get("market_price", sale_price))
            except ValueError:
                sale_price = 50.0
                market_price = 50.0

            if sale_price <= 0:
                sale_price = 40.0
            if market_price < sale_price:
                market_price = sale_price

            l1_id, l1_name, cat_key = map_bigbasket_row(category, sub_cat, product_name)
            pack = extract_pack_size(product_name, type_str)
            emoji = L1_EMOJI_MAP.get(l1_id, "🛍️")

            price_paise = int(round(sale_price * 100))
            mrp_paise = int(round(market_price * 100))
            full_name = f"{brand} {product_name}".strip() if brand and not product_name.startswith(brand) else product_name

            c = Candidate(
                sku_id=sku_id,
                l1_id=l1_id,
                l2_id=l1_id * 10 + 1,
                name=full_name,
                pack=pack,
                price_paise=price_paise,
                mrp_paise=mrp_paise,
                margin_pct=round(random.uniform(0.12, 0.35), 4),
                velocity_30d=random.randint(50, 1200),
                complaint_rate=round(random.uniform(0.001, 0.015), 4),
                available_qty=random.randint(10, 500),
                volume_ml=0,
                weight_g=0,
                is_excluded_l1=l1_id in [15, 23, 24],
                generation_source="CG1",
            )
            
            # Attach web metadata dynamically
            object.__setattr__(c, "_web_meta", {
                "sku_id": sku_id,
                "name": full_name,
                "pack": pack,
                "price": int(sale_price),
                "mrp": int(market_price),
                "cat": cat_key,
                "emoji": emoji,
                "l1_id": l1_id,
                "l2_id": c.l2_id,
                "brand": brand,
            })

            candidates.append(c)
            sku_id += 1

    return candidates

def get_catalog_with_metadata() -> List[Dict[str, Any]]:
    candidates = generate_catalog_from_bigbasket(max_items=3000)
    web_catalog = []
    for c in candidates:
        meta = getattr(c, "_web_meta", {
            "sku_id": c.sku_id,
            "name": c.name,
            "pack": c.pack,
            "price": int(c.price_paise / 100),
            "mrp": int(c.mrp_paise / 100),
            "cat": "produce",
            "emoji": "🛍️",
            "l1_id": c.l1_id,
            "l2_id": c.l2_id,
            "brand": "",
        })
        web_catalog.append(meta)
    return web_catalog

def generate_and_save_catalog():
    items = get_catalog_with_metadata()
    with open(CATALOG_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump({"total": len(items), "items": items}, f, indent=2)
    print(f"Generated and saved {len(items)} real BigBasket products to {CATALOG_JSON_PATH}")

generate_1000_catalog = generate_catalog_from_bigbasket

if __name__ == "__main__":
    generate_and_save_catalog()
