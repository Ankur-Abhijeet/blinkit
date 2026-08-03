"""
discovery.api.app — FastAPI Gateway & Web Simulation Interface.
§5 architecture.md: Cache read path (`GET /v1/discovery/slot`) + web UI simulator (`/`).
"""

import os
import re
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from discovery.worker.nearline_worker import NearlineWorkerEngine
from discovery.core.types import CartContext, CartItem, Candidate
from discovery.config.flags import FeatureFlags
from discovery.api import accounts


class CartItemPayload(BaseModel):
    sku_id: int
    l1_id: int
    l2_id: int
    name: str
    price_paise: int


class SimulateCartPayload(BaseModel):
    user_id: int
    cart_id: str
    cart_subtotal_paise: int
    cart_items: List[CartItemPayload]
    store_id: int = 1
    time_of_day: str = "Evening (7:55 PM)"
    weather: str = "Monsoon Rain, 26°C"


class SlotResponsePayload(BaseModel):
    decision_id: str
    sku_id: int
    l1_id: int
    product_name: str
    pack: str
    price_paise: int
    mrp_paise: int
    reason_code: str
    reason_line: str
    copy_source: str


# ---------------------------------------------------------------------------
# Joke copy: the punchline shown against each recommended product.
# House style — 1 to 3 lines, 3 to 20 words, about THAT product.
# ---------------------------------------------------------------------------

JOKE_MIN_WORDS = 3
JOKE_MAX_WORDS = 20
JOKE_MAX_LINES = 3
# Accepted range is 3-20, but anything this terse is almost always a label
# ("Tulsi tea for rainstorm calm") rather than a joke — worth one retry.
JOKE_RETRY_BELOW_WORDS = 7

# Trailing size/qty noise on BigBasket titles, e.g. "... - Vegetarian Capsule 500 mg"
_PACK_TAIL_RE = re.compile(
    r"[\s,\-–—]*\b\d+(\.\d+)?\s*(mg|g|gm|gms|kg|ml|l|ltr|litre|liter|pc|pcs|pieces?|wipes?|capsules?|tablets?|sachets?|packs?|units?|n)\b\.?$",
    re.IGNORECASE,
)


def short_product_label(name: str, max_chars: int = 32) -> str:
    """A compact, human product label for jokes and single-line card titles."""
    label = (name or "").strip()
    if not label:
        return "this"

    # BigBasket titles put the variant after a dash ("Sponge Pad- Two In One");
    # the head is the real product. Hyphenated words ("Two-In-One") are untouched.
    head = re.split(r"\s*[-–—]\s+", label)[0].strip() or label
    head = _PACK_TAIL_RE.sub("", head).strip(" ,-–—")

    if len(head) <= max_chars:
        return head or label[:max_chars]

    # Trim on a word boundary rather than mid-word.
    clipped = head[:max_chars].rsplit(" ", 1)[0].strip(" ,-–—")
    return (clipped or head[:max_chars]).strip()


def clean_joke(text: Optional[str]) -> Optional[str]:
    """Enforces the house style. Returns None when the line is unusable."""
    if not text:
        return None

    lines = [ln.strip() for ln in str(text).strip().splitlines() if ln.strip()]
    if not lines:
        return None

    joke = "\n".join(lines[:JOKE_MAX_LINES])
    words = joke.split()

    if len(words) < JOKE_MIN_WORDS:
        return None

    if len(words) > JOKE_MAX_WORDS:
        joke = " ".join(words[:JOKE_MAX_WORDS]).rstrip(" ,;:—-")
        if not joke.endswith((".", "!", "?", "…")):
            joke += "."

    return joke


# Product-aware backups, used only when Groq cannot deliver a usable joke.
_JOKE_TEMPLATES = [
    "{item}? Bold. Your cart just developed a personality. 😏",
    "Nobody plans for {item}. Everybody ends up with {item}. 🛒",
    "{item} at {when}. We won't tell anyone. 🤫",
    "{weather} outside, {item} inside. Balance restored. ⚖️",
    "Your cart called. It demanded {item}. Loudly. 📣",
    "{item}: the plot twist this basket deserved. 🎬",
]


def punchy_joke_count(items: List[Dict[str, Any]]) -> int:
    """How many of the first 3 headlines clear the 'actual joke' bar."""
    count = 0
    for r in (items or [])[:3]:
        joke = clean_joke(r.get("headline"))
        if joke and len(joke.split()) >= JOKE_RETRY_BELOW_WORDS:
            count += 1
    return count


def fallback_joke(product_name: str, time_of_day: str, weather: str, idx: int) -> str:
    """Never ships a bland product description — always lands a punchline."""
    when = (time_of_day or "this hour").split(" (")[0].strip().lower()
    weather_word = (weather or "Weather").split(",")[0].strip()
    joke = _JOKE_TEMPLATES[idx % len(_JOKE_TEMPLATES)].format(
        item=short_product_label(product_name, max_chars=26),
        when=when,
        weather=weather_word,
    )
    return clean_joke(joke) or joke


JOKE_SYSTEM_PROMPT = (
    "You are Blinkit's Contextual AI Discovery Engine — a stand-up comedian who moonlights as a grocery recommender. "
    "Analyse the SPECIFIC SYNERGY of this exact cart combination, the Time of Day and the Weather. "
    "Pick 3 complementary products from the UNDISCOVERED candidates given to you. "
    "For EACH product, write ONE joke that obeys ALL of these rules:\n"
    "1. LENGTH: between 3 and 20 words — hard limits. Aim for 8 to 16: that is enough room "
    "for a setup AND a punchline.\n"
    "2. SHAPE: 1 to 3 short lines, and a COMPLETE THOUGHT with a turn in it — not a label.\n"
    "3. RELEVANT: obviously about THAT specific product and how it collides with their cart, "
    "the weather, or the hour. A joke that would fit any other product is a failed joke.\n"
    "4. FUNNY, MEMORABLE, EYE-CATCHING: sharp and a little judgy. Tease their life choices "
    "affectionately. Land the punchline on the last word.\n"
    "5. At most one emoji, at the end.\n"
    "GOOD — copy this energy:\n"
    "- 'Chips at midnight. Your resolutions died bravely. 🥔'\n"
    "- 'Rain outside, ice cream inside. Main character energy. 🍦'\n"
    "- 'Coffee, because pretending to function is a full-time job. ☕'\n"
    "- 'Face wash, for the garlic you just committed to. ✨'\n"
    "BAD — never produce these, they are labels pretending to be jokes:\n"
    "- 'Ham for midnight cravings strong'\n"
    "- 'Tulsi tea for rainstorm calm'\n"
    "- 'Hazelnut wafers for Coke pairing'\n"
    "The bad ones only name the product and a reason. A real joke needs a victim, a turn, "
    "or a confession. If a line does not make you smirk, rewrite it.\n"
    "Respond ONLY in valid JSON: "
    "{\"reason_title\": \"witty banner title, max 8 words\", "
    "\"items\": [{\"sku_id\": int, \"headline\": \"the joke, 3-20 words\"}]}"
)


def create_app(worker_engine: Optional[NearlineWorkerEngine] = None) -> FastAPI:
    app = FastAPI(title="Blinkit Cart Interrupt MVP", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if worker_engine is None:
        flags = FeatureFlags({
            "discovery.enabled": True,
            "discovery.slot_a.enabled": True,
            "discovery.slot_b.enabled": True,
            "discovery.a3.enabled": True,
            "discovery.a4.enabled": True,
            "discovery.arm_split": {"A": 0, "B": 100, "C": 0},
        })
        worker_engine = NearlineWorkerEngine(flags=flags)

    # Account store: signup/login verification, order history, location history
    accounts.init_db()
    app.include_router(accounts.router)

    @app.get("/healthz")
    def health_check():
        return {"status": "ok", "service": "discovery-api"}

    @app.get("/v1/catalog")
    def get_full_catalog():
        """Returns full real BigBasket dataset catalog for storefront browsing and search."""
        from discovery.offline.catalog_generator import get_catalog_with_metadata
        items = get_catalog_with_metadata()
        return {"total_count": len(items), "items": items}

    @app.get("/v1/discovery/slot", status_code=status.HTTP_200_OK)
    def get_slot(
        user_id: int = Query(..., description="User ID"),
        cart_id: str = Query(..., description="Cart ID"),
        cart_hash: str = Query(..., description="Cart Signature Hash"),
        slot: str = Query("A", description="Slot ID (A or B)"),
    ):
        """FastAPI prefetch endpoint (Cache read only, p99 <= 5ms, 204 fallback)."""
        if not worker_engine.flags.is_enabled("discovery.enabled"):
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        if slot == "A" and not worker_engine.flags.is_enabled("discovery.slot_a.enabled"):
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        if slot == "B" and not worker_engine.flags.is_enabled("discovery.slot_b.enabled"):
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        slot_suffix = ":slot_b" if slot == "B" else ""
        decision = worker_engine.get_cached_decision(user_id=user_id, cart_hash=f"{cart_hash}{slot_suffix}")

        if not decision or not decision.served_candidate:
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        cand = decision.served_candidate
        payload = SlotResponsePayload(
            decision_id=decision.decision_id,
            sku_id=cand.sku_id,
            l1_id=cand.l1_id,
            product_name=cand.name,
            pack=cand.pack,
            price_paise=cand.price_paise,
            mrp_paise=cand.mrp_paise,
            reason_code=decision.reason_code,
            reason_line=decision.reason_line,
            copy_source=decision.copy_source,
        )
        return payload

    @app.post("/v1/discovery/simulate")
    def simulate_cart(payload: SimulateCartPayload):
        """Simulation endpoint: runs AI discovery taking Time of Day, Weather, Basket & Undiscovered Categories."""
        cart_items = [
            CartItem(
                sku_id=item.sku_id,
                l1_id=item.l1_id,
                l2_id=item.l2_id,
                name=item.name,
                price_paise=item.price_paise,
            )
            for item in payload.cart_items
        ]

        ctx = CartContext(
            user_id=payload.user_id,
            session_id=f"sess_{payload.user_id}",
            cart_id=payload.cart_id,
            store_id=payload.store_id,
            cart_subtotal_paise=payload.cart_subtotal_paise,
            cart_items=cart_items,
            tenure_days=30,
            completed_orders=5,
        )

        from discovery.offline.catalog_generator import generate_catalog_from_bigbasket
        store_pool = generate_catalog_from_bigbasket()

        user_purchased = {10} if payload.user_id != 999 else set()
        decision = worker_engine.process_cart_event(ctx, store_pool, user_purchased_l1_ids=user_purchased)

        # Multi-Item AI Recommendation Layer via Groq API (llama-3.3-70b-versatile)
        # 5 Context Factors: (1) Available Catalog, (2) Cart Items, (3) Undiscovered Categories, (4) Time of Day, (5) Real-time Weather
        multi_recommendations = []
        try:
            from discovery.gateway.llm_gateway import LLMGatewayClient
            client = LLMGatewayClient()
            if client.groq_api_key and cart_items:
                cart_l1s = set(i.l1_id for i in cart_items)
                undiscovered_cands = [c for c in store_pool if c.l1_id not in user_purchased and c.l1_id not in cart_l1s]

                if undiscovered_cands:
                    cart_names = ", ".join(i.name for i in cart_items)
                    import random
                    # Cart Combination Signature Seeding (Cart Hash)
                    # Different cart combinations generate distinctly tailored candidate pools
                    cart_sig_hash = abs(hash(tuple(sorted(i.sku_id for i in cart_items))))
                    cart_random = random.Random(cart_sig_hash)

                    # Dynamic pool sampling seeded by cart combination
                    sample_size = min(15, len(undiscovered_cands))
                    sample_cands = cart_random.sample(undiscovered_cands, k=sample_size)
                    available_desc = "; ".join(f"SKU {c.sku_id}: {c.name} (Cat {c.l1_id}, Rs {c.price_paise//100})" for c in sample_cands)

                    user_prompt = (
                        f"Exact Cart Combination: [{cart_names}]\n"
                        f"Cart SKU Signature ID: {cart_sig_hash}\n"
                        f"Time of Day: {payload.time_of_day}\n"
                        f"Real-Time Weather: {payload.weather}\n"
                        f"Discovered Past Categories: {list(user_purchased)}\n"
                        f"Available Undiscovered Candidates: [{available_desc}]\n"
                    )

                    import json

                    # Writing the joke is a required step, not a nicety: if the first
                    # pass comes back short, bland or over-long, push Groq once more
                    # before falling back to canned copy.
                    parsed = {}
                    for attempt in range(2):
                        nudge = "" if attempt == 0 else (
                            "\nYour previous attempt produced labels, not jokes. Every headline MUST be "
                            "8-16 words, a complete thought with a punchline on the last word, clearly "
                            "about that specific product, and actually funny."
                        )
                        ok, ai_res = client.generate_completion(
                            prompt=user_prompt + nudge,
                            system_prompt=JOKE_SYSTEM_PROMPT,
                            use_groq=True,
                            temperature=0.9 if attempt == 0 else 1.0,
                            max_tokens=600,
                        )
                        if not ok:
                            print(f"[JOKE ENGINE] Groq call failed (attempt {attempt + 1}): {ai_res}")
                            continue

                        raw = ai_res.strip()
                        if raw.startswith("```"):
                            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

                        try:
                            candidate_parsed = json.loads(raw)
                        except json.JSONDecodeError as e:
                            print(f"[JOKE ENGINE] Unparseable Groq JSON (attempt {attempt + 1}): {e}")
                            continue

                        items = candidate_parsed.get("items", [])
                        usable = sum(1 for r in items[:3] if clean_joke(r.get("headline")))
                        punchy = punchy_joke_count(items)

                        # Keep the better of the two attempts, not simply the later one.
                        if not parsed or punchy >= punchy_joke_count(parsed.get("items", [])):
                            parsed = candidate_parsed

                        if usable >= 3 and punchy >= 3:
                            break
                        tail = "retrying" if attempt == 0 else "keeping best attempt"
                        print(f"[JOKE ENGINE] {usable}/3 usable, {punchy}/3 punchy (attempt {attempt + 1}); {tail}.")

                    recs = parsed.get("items", [])
                    for idx, r in enumerate(recs[:3]):
                        sku = r.get("sku_id")
                        m_cand = next((c for c in store_pool if c.sku_id == sku), sample_cands[idx % len(sample_cands)])
                        joke = clean_joke(r.get("headline")) or fallback_joke(
                            m_cand.name, payload.time_of_day, payload.weather, idx
                        )
                        multi_recommendations.append({
                            "candidate": m_cand.model_dump(),
                            "short_name": short_product_label(m_cand.name),
                            "headline": joke,
                        })

                    if multi_recommendations:
                        top_cand_dict = multi_recommendations[0]["candidate"]
                        top_cand = Candidate(**top_cand_dict)
                        banner_title = parsed.get("reason_title") or "Witty AI Recommendations for your Order"
                        decision = decision.model_copy(update={
                            "served_candidate": top_cand,
                            "reason_line": banner_title,
                            "copy_source": "groq_llama_3.3_70b_live",
                            "reason_code": "AI_CONTEXTUAL_MULTI_CATEGORY_MATCH"
                        })
        except Exception as e:
            print(f"[AI ENGINE EXCEPTION] {e}")

        # Always guarantee multi-candidate fallback if AI didn't populate 3 items
        if len(multi_recommendations) < 3:
            cart_l1s = set(i.l1_id for i in cart_items)
            fallback_cands = [c for c in store_pool if c.l1_id not in user_purchased and c.l1_id not in cart_l1s]
            seen_skus = set(r["candidate"]["sku_id"] for r in multi_recommendations)
            for c in fallback_cands:
                if c.sku_id not in seen_skus:
                    multi_recommendations.append({
                        "candidate": c.model_dump(),
                        "short_name": short_product_label(c.name),
                        "headline": fallback_joke(
                            c.name, payload.time_of_day, payload.weather, len(multi_recommendations)
                        ),
                    })
                    seen_skus.add(c.sku_id)
                    if len(multi_recommendations) >= 3:
                        break

        res_dict = decision.model_dump()
        res_dict["multi_recommendations"] = multi_recommendations
        res_dict["context"] = {
            "time_of_day": payload.time_of_day,
            "weather": payload.weather
        }
        return res_dict

    # Serve static web frontend
    web_dir = os.path.join(os.path.dirname(__file__), "..", "web")
    if os.path.exists(web_dir):
        app.mount("/static", StaticFiles(directory=web_dir), name="static")

        @app.get("/")
        def serve_index():
            return FileResponse(os.path.join(web_dir, "index.html"))

        @app.get("/styles.css")
        def serve_styles():
            return FileResponse(os.path.join(web_dir, "styles.css"))

        @app.get("/app.js")
        def serve_js():
            return FileResponse(os.path.join(web_dir, "app.js"))

    return app


# Default app instance
app = create_app()
