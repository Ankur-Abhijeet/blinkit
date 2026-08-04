// Authentic Blinkit Quick Commerce Client Script — Multi-Page & Multi-Section Routing

let ALL_PRODUCTS = [];
let state = {
  userId: 101,
  cartMap: {}, // sku_id -> { product, qty }
  currentView: "home", // "home" | "category" | "search" | "productDetail" | "auth" | "account"
  activeCategory: "all",
  activeCategoryTitle: "All Items",
  searchQuery: "",
  sortBy: "popular",
  lastDecision: null,

  // Live order tracking (active for 10 minutes after checkout)
  activeOrder: null,      // { order_id, placed_at_ms, total_paise, location, items }
  trackingTimer: null,

  // Account & session
  auth: null,             // { token, user: { id, username, created_at } }
  authMode: "login",      // "login" | "signup" — two distinct actions
  pendingCheckout: false, // true when auth was triggered by a checkout
  returnView: "home",     // where to go back to after the auth page
  locationHistory: [],    // guest-session locations, carried into a new account on signup
  accountData: null,      // last /v1/account payload
};

const AUTH_STORAGE_KEY = "blinkit_auth";
const TRACKING_STORAGE_KEY = "blinkit_active_order";

// A placed order stays trackable for 10 minutes.
const TRACKING_WINDOW_MS = 10 * 60 * 1000;

// Delivery stages, keyed by seconds elapsed since the order was placed.
const TRACKING_STAGES = [
  { at: 0,   icon: "🧾", label: "Order confirmed",         sub: "Payment received, sending to the store" },
  { at: 90,  icon: "📦", label: "Packed at the dark store", sub: "Your items are being bagged" },
  { at: 240, icon: "🛵", label: "Picked up by your rider",  sub: "On the way to you now" },
  { at: 450, icon: "📍", label: "Arriving at your door",    sub: "Keep your phone close" },
];

const CATEGORY_NAMES = {
  produce: "Vegetables & Fruits",
  staples: "Atta, Rice, Oil & Dal",
  dairy: "Dairy, Bread & Eggs",
  snacks: "Chips, Biscuits & Sweets",
  drinks: "Drinks, Juices & Tea",
  instant: "Instant Food & Sauces",
  personal: "Beauty & Personal Care",
  cleaning: "House Cleaning & Decor",
  baby: "Baby Care",
  electronics: "Electronics & Appliances",
  imported: "Imported Store",
  pharmacy: "Health & Pharma",
  pets: "Pet Store",
};

// Self-Collected Time & Weather Context
try {
  // Wipe legacy address strings cached in browser storage, but keep the signed-in
  // session so a page reload does not silently log the user out.
  const preservedAuth = localStorage.getItem(AUTH_STORAGE_KEY);
  const preservedOrder = localStorage.getItem(TRACKING_STORAGE_KEY);
  localStorage.clear();
  sessionStorage.clear();
  if (preservedAuth) localStorage.setItem(AUTH_STORAGE_KEY, preservedAuth);
  if (preservedOrder) localStorage.setItem(TRACKING_STORAGE_KEY, preservedOrder);
} catch (e) {}

let liveUserLocation = "NextLeap Office, Koramangala, Bangalore";
let liveWeatherCondition = "Pleasant & Breezy, 24°C";

function updateHeaderAddressDisplay(locText, source = "session") {
  liveUserLocation = locText;
  const addressText = document.getElementById("headerAddressText");
  if (addressText) addressText.textContent = locText;
  recordLocationVisit(locText, source);
}

// Location history: kept locally while browsing as a guest (handed to the backend
// on signup) and pushed straight to the account once signed in.
function recordLocationVisit(locText, source = "session") {
  const location = (locText || "").trim();
  if (!location) return;

  const last = state.locationHistory[state.locationHistory.length - 1];
  if (!last || last.location !== location) {
    state.locationHistory.push({ location, source, recorded_at: new Date().toISOString() });
  }

  if (state.auth) {
    fetch(`${API_BASE_URL}/v1/account/location`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ location, source }),
    }).catch(err => console.warn("Location history sync failed:", err));
  }
}

async function detectUserLocationAndWeather() {
  const addressText = document.getElementById("headerAddressText");

  if (!("geolocation" in navigator)) {
    updateHeaderAddressDisplay(liveUserLocation);
    return;
  }

  if (addressText) addressText.textContent = "📍 Requesting GPS Location...";

  navigator.geolocation.getCurrentPosition(
    async (position) => {
      const lat = position.coords.latitude;
      const lon = position.coords.longitude;

      try {
        // Reverse Geocoding to get City & Locality
        const geoRes = await fetch(`https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${lat}&longitude=${lon}&localityLanguage=en`);
        if (geoRes.ok) {
          const geoData = await geoRes.json();
          const locality = geoData.locality || geoData.city || "Current Location";
          const city = geoData.principalSubdivision || geoData.countryName || "";
          updateHeaderAddressDisplay(`${locality}${city ? ", " + city : ""}`, "gps");
        }

        // Fetch Current Weather via Open-Meteo API
        const weatherRes = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current_weather=true`);
        if (weatherRes.ok) {
          const weatherData = await weatherRes.json();
          const cw = weatherData.current_weather;
          if (cw) {
            const temp = Math.round(cw.temperature);
            const code = cw.weathercode;
            let condition = "Sunny";
            if (code >= 1 && code <= 3) condition = "Partly Cloudy";
            else if (code >= 45 && code <= 48) condition = "Foggy";
            else if (code >= 51 && code <= 67) condition = "Rainy";
            else if (code >= 71) condition = "Cold";
            
            liveWeatherCondition = `${condition}, ${temp}°C`;
          }
        }
      } catch (err) {
        console.warn("GPS/Weather API Error:", err);
        updateHeaderAddressDisplay(liveUserLocation);
      }
    },
    (err) => {
      console.warn("Geolocation permission denied/unavailable:", err);
      updateHeaderAddressDisplay(liveUserLocation);
    },
    { timeout: 10000, enableHighAccuracy: true }
  );
}

function getSystemTimeOfDay() {
  const d = new Date();
  const hour = d.getHours();
  const timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  if (hour >= 5 && hour < 12) return `Morning (${timeStr})`;
  if (hour >= 12 && hour < 17) return `Afternoon (${timeStr})`;
  if (hour >= 17 && hour < 21) return `Evening (${timeStr})`;
  return `Late Night (${timeStr})`;
}

function getSystemWeather() {
  if (liveWeatherCondition) return liveWeatherCondition;
  const month = new Date().getMonth();
  if (month >= 5 && month <= 8) return "Monsoon Rain & Humid, 27°C";
  if (month >= 9 || month <= 1) return "Cold Winter & Fog, 14°C";
  return "Hot Summer & Sunny, 34°C";
}

// DOM Handles
const homeView = document.getElementById("homeView");
const categoryView = document.getElementById("categoryView");
const searchView = document.getElementById("searchView");
const topNavPills = document.getElementById("topNavPills");

const homeBestsellersGrid = document.getElementById("homeBestsellersGrid");
const categoryProductsGrid = document.getElementById("categoryProductsGrid");
const searchProductsGrid = document.getElementById("searchProductsGrid");

const categoryPageTitle = document.getElementById("categoryPageTitle");
const categoryPageCountBadge = document.getElementById("categoryPageCountBadge");
const sortSelect = document.getElementById("sortSelect");

const cartItemsWrapper = document.getElementById("cartItemsWrapper");
const drawerItemBadge = document.getElementById("drawerItemBadge");
const deliveryProgressText = document.getElementById("deliveryProgressText");
const progressBarFill = document.getElementById("progressBarFill");
const billItemTotal = document.getElementById("billItemTotal");
const billGrandTotal = document.getElementById("billGrandTotal");
const btnPayAmount = document.getElementById("btnPayAmount");
const proceedCheckoutBtn = document.getElementById("proceedCheckoutBtn");

const searchInput = document.getElementById("searchInput");
const clearSearchBtn = document.getElementById("clearSearchBtn");
const searchBackBtn = document.getElementById("searchBackBtn");
const backToHomeBtn = document.getElementById("backToHomeBtn");

// Mobile & Navigation Handles
const mobileFloatingCartBar = document.getElementById("mobileFloatingCartBar");
const floatThumbPreviews = document.getElementById("floatThumbPreviews");
const mobileFloatCount = document.getElementById("mobileFloatCount");
const mobileFloatTotal = document.getElementById("mobileFloatTotal");
const mobileViewCartBtn = document.getElementById("mobileViewCartBtn");
const cartSidebar = document.getElementById("cartSidebar");
const closeDrawerBtn = document.getElementById("closeDrawerBtn");
const headerCartBtn = document.getElementById("headerCartBtn");

// Modal Sheet Handles
const slotAModalOverlay = document.getElementById("slotAModalOverlay");
const dialogCloseBtn = document.getElementById("dialogCloseBtn");
const slotABannerTitle = document.getElementById("slotABannerTitle");
const contextPillTag = document.getElementById("contextPillTag");
const multiRecsGrid = document.getElementById("multiRecsGrid");
const modalSkipBtn = document.getElementById("modalSkipBtn");

// Dynamic Backend API Base URL (Render Backend <-> Vercel Frontend Integration)
const API_BASE_URL = (function() {
  if (window.BLINKIT_BACKEND_URL) return window.BLINKIT_BACKEND_URL;
  if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
    return ""; // Relative URL for unified local dev server
  }
  return localStorage.getItem("BLINKIT_BACKEND_URL") || "https://blinkit-mvp-backend.onrender.com";
})();

// 1. Load 3,000+ Item Catalog
async function loadFullCatalog() {
  try {
    const res = await fetch(`${API_BASE_URL}/v1/catalog`);
    if (res.ok) {
      const data = await res.json();
      ALL_PRODUCTS = data.items || [];
      renderCurrentView();
    }
  } catch (err) {
    console.error("Failed to load catalog:", err);
  }
}

// 2. View Switcher Routing Logic
function showView(viewName, catSlug = null) {
  state.currentView = viewName;

  const homeView = document.getElementById("homeView");
  const categoryView = document.getElementById("categoryView");
  const searchView = document.getElementById("searchView");
  const productDetailView = document.getElementById("productDetailView");
  const pdpStickyBottomBar = document.getElementById("pdpStickyBottomBar");
  const authView = document.getElementById("authView");
  const accountView = document.getElementById("accountView");
  const trackingView = document.getElementById("trackingView");
  const pillStrip = document.getElementById("topNavPills");

  if (homeView) homeView.classList.add("hidden");
  if (categoryView) categoryView.classList.add("hidden");
  if (searchView) searchView.classList.add("hidden");
  if (productDetailView) productDetailView.classList.add("hidden");
  if (pdpStickyBottomBar) pdpStickyBottomBar.classList.add("hidden");
  if (authView) authView.classList.add("hidden");
  if (accountView) accountView.classList.add("hidden");
  if (trackingView) trackingView.classList.add("hidden");

  // Category pills are storefront navigation — hide them on account screens
  if (pillStrip) {
    const chromeless = viewName === "auth" || viewName === "account" || viewName === "tracking";
    pillStrip.style.display = chromeless ? "none" : "";
  }

  // Highlight pill buttons
  document.querySelectorAll(".pill-item").forEach(p => p.classList.remove("active"));

  if (viewName === "home") {
    if (homeView) homeView.classList.remove("hidden");
    const homePill = document.querySelector(`.pill-item[data-nav="home"]`);
    if (homePill) homePill.classList.add("active");
  } else if (viewName === "category") {
    if (categoryView) categoryView.classList.remove("hidden");
    state.activeCategory = catSlug || "produce";
    state.activeCategoryTitle = CATEGORY_NAMES[state.activeCategory] || "Category Items";

    if (categoryPageTitle) categoryPageTitle.textContent = state.activeCategoryTitle;

    const activePill = document.querySelector(`.pill-item[data-cat="${state.activeCategory}"]`);
    if (activePill) activePill.classList.add("active");
  } else if (viewName === "search") {
    if (searchView) searchView.classList.remove("hidden");
  } else if (viewName === "productDetail") {
    if (productDetailView) productDetailView.classList.remove("hidden");
    // The PDP add control lives in the floating cart bar instead, so this
    // bar stays hidden — the floating bar sits on top of it either way.
  } else if (viewName === "auth") {
    if (authView) authView.classList.remove("hidden");
  } else if (viewName === "account") {
    if (accountView) accountView.classList.remove("hidden");
  } else if (viewName === "tracking") {
    if (trackingView) trackingView.classList.remove("hidden");
  }

  renderCurrentView();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// 3. Render Current Active View Content
function renderCurrentView() {
  if (state.currentView === "home") {
    renderHomeView();
  } else if (state.currentView === "category") {
    renderCategoryView();
  } else if (state.currentView === "search") {
    renderSearchView();
  } else if (state.currentView === "productDetail") {
    renderProductDetailView();
  } else if (state.currentView === "auth") {
    renderAuthView();
  } else if (state.currentView === "account") {
    renderAccountView();
  } else if (state.currentView === "tracking") {
    renderTrackingView();
  }

  renderFloatingPdpAddSlot();
}

function renderHomeView() {
  // Render Top 16 Bestsellers on Home Page
  const bestsellers = ALL_PRODUCTS.slice(0, 16);
  homeBestsellersGrid.innerHTML = renderProductCardsHTML(bestsellers);
}

function renderCategoryView() {
  let items = ALL_PRODUCTS.filter(p => p.cat === state.activeCategory);

  // Apply Sorting
  if (state.sortBy === "price_low") {
    items = items.slice().sort((a, b) => a.price - b.price);
  } else if (state.sortBy === "price_high") {
    items = items.slice().sort((a, b) => b.price - a.price);
  } else if (state.sortBy === "discount") {
    items = items.slice().sort((a, b) => (b.mrp - b.price) - (a.mrp - a.price));
  }

  if (categoryPageCountBadge) categoryPageCountBadge.textContent = `${items.length} items available`;
  categoryProductsGrid.innerHTML = renderProductCardsHTML(items);
}

function renderSearchView() {
  const q = state.searchQuery.toLowerCase().trim();
  const searchQueryTitle = document.getElementById("searchQueryTitle");
  if (searchQueryTitle) searchQueryTitle.textContent = q ? `Search results for "${q}"` : "Search Results";

  if (!q) {
    searchProductsGrid.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: #64748b;">
        <div style="font-size: 36px; margin-bottom: 6px;">🔍</div>
        <h3>Search for fresh produce, milk, snacks, drinks & more</h3>
      </div>
    `;
    return;
  }

  const matches = ALL_PRODUCTS.filter(p => p.name.toLowerCase().includes(q) || p.pack.toLowerCase().includes(q));

  if (matches.length === 0) {
    searchProductsGrid.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: #64748b;">
        <div style="font-size: 36px; margin-bottom: 6px;">🧺</div>
        <h3>No items found matching "${q}"</h3>
        <p>Try searching for 'atta', 'butter', 'cola', 'soap', or 'biscuit'.</p>
      </div>
    `;

    return;
  }

  searchProductsGrid.innerHTML = renderProductCardsHTML(matches);
}

// ---- Pricing ------------------------------------------------------------
// 43% of the catalogue carries mrp == price. Those are not discounts, so we
// show a single price with no struck-through duplicate and no badge.

function discountPercent(price, mrp) {
  if (!mrp || mrp <= price) return 0;
  return Math.round(((mrp - price) / mrp) * 100);
}

// Price block: "₹149 ₹176 15% OFF" when discounted, plain "₹220" when not.
function priceBlockHTML(price, mrp, opts = {}) {
  const pct = discountPercent(price, mrp);
  const cls = opts.compact ? "price-box compact" : "price-box";
  if (pct === 0) {
    return `<div class="${cls}"><span class="price-main">₹${price}</span></div>`;
  }
  // Two tight lines keep the block narrow so the ADD button stays beside it
  // and every card in the grid ends up the same height.
  return `
    <div class="${cls}">
      <span class="price-main">₹${price}</span>
      <span class="price-sub-row">
        <span class="price-mrp">₹${mrp}</span>
        <span class="price-off">${pct}% OFF</span>
      </span>
    </div>
  `;
}

// Corner ribbon for grid cards; empty string when there is nothing to shout about.
function discountBadgeHTML(price, mrp) {
  const pct = discountPercent(price, mrp);
  return pct > 0 ? `<span class="discount-badge">${pct}% OFF</span>` : "";
}

// One recommendation card, shared by the checkout sheet and the tracking page.
function recCardHTML(r) {
  const c = r.candidate;
  const price = Math.round(c.price_paise / 100);
  const mrp = Math.round(c.mrp_paise / 100);

  let emoji = c.emoji || "🛍️";
  if (!c.emoji) {
    if (c.l1_id === 20) emoji = "👶";
    else if (c.l1_id === 25) emoji = "🐶";
    else if (c.l1_id === 18) emoji = "🍫";
    else if (c.l1_id === 88) emoji = "💊";
    else if (c.l1_id === 35) emoji = "🧴";
    else if (c.l1_id === 42) emoji = "🥤";
  }

  return `
    <div class="rec-card-item">
      <div class="rec-img-box">${emoji}</div>
      <div class="rec-body">
        <div class="rec-title" title="${c.name}">${r.short_name || c.name}</div>
        <div class="rec-reason">😏 ${r.headline || "Your cart called. It demanded this. Loudly. 📣"}</div>
      </div>
      <div class="rec-price-row">
        ${priceBlockHTML(price, mrp, { compact: true })}
        <button class="rec-btn-add" onclick="addRecommendedSku(${c.sku_id})">+ ADD</button>
      </div>
    </div>
  `;
}

// The Groq round-trip takes a few seconds, so the wait gets skeleton cards,
// a scanning bar and a rotating status line rather than a frozen panel.
const REC_LOADING_STEPS = [
  "Reading your basket…",
  "Checking the time and the weather…",
  "Hunting through 3,000 products…",
  "Writing something rude about your cart…",
  "Almost there…",
];

let recLoadingTimer = null;

function showRecLoadingState(grid) {
  if (!grid) return;
  stopRecLoadingState();

  grid.innerHTML = `
    <div class="rec-loading-head">
      <div class="rec-scanner"><span></span></div>
      <p class="rec-loading-step" id="recLoadingStep">${REC_LOADING_STEPS[0]}</p>
    </div>
    ${recSkeletonHTML(3)}
  `;

  let i = 0;
  recLoadingTimer = setInterval(() => {
    i = (i + 1) % REC_LOADING_STEPS.length;
    const el = document.getElementById("recLoadingStep");
    if (!el) return stopRecLoadingState();

    // Plain text swap. The motion in this panel comes from the scanner bar and
    // the shimmering skeletons; animating the label too left it caught at a
    // low-opacity keyframe for much of every rotation.
    el.textContent = REC_LOADING_STEPS[i];
  }, 1600);
}

function stopRecLoadingState() {
  if (recLoadingTimer) {
    clearInterval(recLoadingTimer);
    recLoadingTimer = null;
  }
}

// Shimmering placeholders shown while the Groq call is in flight.
function recSkeletonHTML(count = 3) {
  return Array.from({ length: count }).map(() => `
    <div class="rec-card-item rec-skeleton" aria-hidden="true">
      <div class="rec-img-box skel skel-box"></div>
      <div class="rec-body">
        <div class="skel skel-line skel-title"></div>
        <div class="skel skel-line skel-joke"></div>
        <div class="skel skel-line skel-joke short"></div>
      </div>
      <div class="rec-price-row">
        <div class="skel skel-line skel-price"></div>
        <div class="skel skel-pill"></div>
      </div>
    </div>
  `).join("");
}

// Product Cards Generator
function renderProductCardsHTML(productsList) {
  return productsList.map(p => {
    const inCart = state.cartMap[p.sku_id];
    const qty = inCart ? inCart.qty : 0;

    return `
      <div class="blinkit-card" onclick="openProductDetail(${p.sku_id}, event)">
        <div class="card-top">
          <span class="time-badge">8 MINS</span>
          ${discountBadgeHTML(p.price, p.mrp)}
        </div>
        <div class="card-img">${p.emoji || "🛍️"}</div>
        <div class="card-title">${p.name}</div>
        <div class="card-pack">${p.pack}</div>
        <div class="card-bottom" onclick="event.stopPropagation()">
          ${priceBlockHTML(p.price, p.mrp)}
          ${qty === 0 ? `
            <button class="add-btn-blinkit" onclick="updateQty(${p.sku_id}, 1)">ADD</button>
          ` : `
            <div class="stepper">
              <button onclick="updateQty(${p.sku_id}, ${qty - 1})">-</button>
              <span>${qty}</span>
              <button onclick="updateQty(${p.sku_id}, ${qty + 1})">+</button>
            </div>
          `}
        </div>
      </div>
    `;
  }).join("");
}

// Product Detail Page (PDP) Handlers
function openProductDetail(skuId, evt) {
  if (evt) evt.stopPropagation();
  const product = ALL_PRODUCTS.find(p => p.sku_id === skuId);
  if (!product) return;

  if (state.currentView !== "productDetail") {
    state.previousView = state.currentView;
  }
  state.activeProductSku = skuId;
  showView("productDetail");
}

function renderProductDetailView() {
  const p = ALL_PRODUCTS.find(item => item.sku_id === state.activeProductSku);
  if (!p) return;

  const pdpHeaderBrand = document.getElementById("pdpHeaderBrand");
  const pdpHeaderTitle = document.getElementById("pdpHeaderTitle");
  if (pdpHeaderBrand) pdpHeaderBrand.textContent = p.brand || "BLINKIT FRESH";
  if (pdpHeaderTitle) pdpHeaderTitle.textContent = p.name;

  const inCart = state.cartMap[p.sku_id];
  const qty = inCart ? inCart.qty : 0;
  const savings = Math.max(0, p.mrp - p.price);
  const discountPct = discountPercent(p.price, p.mrp);

  // Synthetic multi-packs: only claim a saving when there actually is one.
  const pack2Price = Math.round(p.price * 1.9);
  const pack4Price = Math.round(p.price * 3.6);
  const pack2Save = Math.max(0, Math.round(p.mrp * 2 - pack2Price));
  const pack4Save = Math.max(0, Math.round(p.mrp * 4 - pack4Price));

  const similarProducts = ALL_PRODUCTS.filter(item => item.cat === p.cat && item.sku_id !== p.sku_id).slice(0, 10);
  const topCategoryProducts = ALL_PRODUCTS.filter(item => item.l1_id === p.l1_id && item.sku_id !== p.sku_id).slice(0, 10);
  const peopleAlsoBought = ALL_PRODUCTS.filter(item => item.cat !== p.cat).slice(0, 10);
  const categoryBrands = Array.from(new Set(ALL_PRODUCTS.filter(item => item.cat === p.cat && item.brand).map(item => item.brand))).slice(0, 8);

  const container = document.getElementById("pdpContainer");
  if (!container) return;

  container.innerHTML = `
    <!-- 1. Hero Product Card -->
    <div class="pdp-hero-card">
      <div class="pdp-hero-img-box">
        <span class="pdp-time-tag">⚡ 10 MINS</span>
        ${discountPct > 0 ? `<span class="pdp-discount-tag">${discountPct}% OFF</span>` : ''}
        ${p.emoji || "🛍️"}
      </div>

      <div class="pdp-brand-name">${p.brand || "BLINKIT ASSURED"}</div>
      <h2 class="pdp-product-title">${p.name}</h2>

      <div class="pdp-pack-selector-title">Select Unit / Pack Size</div>
      <div class="pdp-pack-options-grid">
        <div class="pdp-pack-option-btn active">
          <span class="pdp-pack-weight">${p.pack}</span>
          <span class="pdp-pack-price">₹${p.price}</span>
          ${savings > 0 ? `<span class="pdp-pack-save">SAVE ₹${savings}</span>` : ''}
        </div>
        <div class="pdp-pack-option-btn">
          <span class="pdp-pack-weight">2x Pack</span>
          <span class="pdp-pack-price">₹${pack2Price}</span>
          ${pack2Save > 0 ? `<span class="pdp-pack-save">SAVE ₹${pack2Save}</span>` : ''}
        </div>
        <div class="pdp-pack-option-btn">
          <span class="pdp-pack-weight">4x Family</span>
          <span class="pdp-pack-price">₹${pack4Price}</span>
          ${pack4Save > 0 ? `<span class="pdp-pack-save">SAVE ₹${pack4Save}</span>` : ''}
        </div>
      </div>

      <div class="pdp-trust-banner">
        <div class="pdp-trust-item">
          <span>⚡</span>
          <span>Delivered in 10 minutes from nearest dark store</span>
        </div>
        <div class="pdp-trust-item">
          <span>🏷️</span>
          <span>Get 10% off with ICICI / HDFC Bank Cards</span>
        </div>
        <div class="pdp-trust-item">
          <span>🛡️</span>
          <span>100% Freshness Guarantee & Instant Refund</span>
        </div>
      </div>
    </div>

    <!-- 2. Product Details Accordion -->
    <div class="pdp-section-box">
      <h3 class="pdp-section-title">Product Details</h3>
      <p style="font-size:12px; color:#475569; line-height:1.5;">
        Freshly sourced premium quality <strong>${p.name}</strong> from verified local suppliers. 
        Hygienically packed for immediate 10-minute delivery.
      </p>
      <div style="margin-top:10px; font-size:11px; color:#64748b;">
        <div>• <strong>Brand:</strong> ${p.brand || "Blinkit Essentials"}</div>
        <div>• <strong>Unit Pack:</strong> ${p.pack}</div>
        <div>• <strong>Category:</strong> ${CATEGORY_NAMES[p.cat] || p.cat} (L1 ${p.l1_id})</div>
      </div>
    </div>

    <!-- 3. Similar Products Carousel -->
    ${similarProducts.length > 0 ? `
      <div class="pdp-section-box">
        <h3 class="pdp-section-title">Similar products</h3>
        <div class="pdp-horizontal-scroll">
          ${similarProducts.map(sp => renderPDPMiniCard(sp)).join('')}
        </div>
      </div>
    ` : ''}

    <!-- 4. Top Products in Category Carousel -->
    ${topCategoryProducts.length > 0 ? `
      <div class="pdp-section-box">
        <h3 class="pdp-section-title">Top products in this category</h3>
        <div class="pdp-horizontal-scroll">
          ${topCategoryProducts.map(tp => renderPDPMiniCard(tp)).join('')}
        </div>
      </div>
    ` : ''}

    <!-- 5. Brands in this Category -->
    ${categoryBrands.length > 0 ? `
      <div class="pdp-section-box">
        <h3 class="pdp-section-title">Brands in this category</h3>
        <div class="pdp-brand-pills-row">
          ${categoryBrands.map(b => `<div class="pdp-brand-pill">${b}</div>`).join('')}
        </div>
      </div>
    ` : ''}

    <!-- 6. People Also Bought Carousel -->
    ${peopleAlsoBought.length > 0 ? `
      <div class="pdp-section-box">
        <h3 class="pdp-section-title">People Also Bought</h3>
        <div class="pdp-horizontal-scroll">
          ${peopleAlsoBought.map(pb => renderPDPMiniCard(pb)).join('')}
        </div>
      </div>
    ` : ''}
  `;

  // Update PDP Sticky Bottom Bar
  const pdpBottomPack = document.getElementById("pdpBottomPack");
  const pdpBottomPrice = document.getElementById("pdpBottomPrice");
  const pdpBottomMrp = document.getElementById("pdpBottomMrp");
  const pdpBottomActionCol = document.getElementById("pdpBottomActionCol");

  if (pdpBottomPack) pdpBottomPack.textContent = p.pack;
  if (pdpBottomPrice) pdpBottomPrice.textContent = `₹${p.price}`;
  if (pdpBottomMrp) {
    pdpBottomMrp.textContent = discountPct > 0 ? `₹${p.mrp}` : "";
    pdpBottomMrp.style.display = discountPct > 0 ? "" : "none";
  }

  if (pdpBottomActionCol) {
    if (qty === 0) {
      pdpBottomActionCol.innerHTML = `
        <button class="pdp-add-btn" onclick="updateQty(${p.sku_id}, 1)">ADD TO CART</button>
      `;
    } else {
      pdpBottomActionCol.innerHTML = `
        <div class="stepper" style="height:42px; font-size:14px; background:#f0fdf4; border-color:#16a34a;">
          <button onclick="updateQty(${p.sku_id}, ${qty - 1})">-</button>
          <span style="font-weight:900; font-size:15px; padding: 0 12px; color:#15803d;">${qty} in cart</span>
          <button onclick="updateQty(${p.sku_id}, ${qty + 1})">+</button>
        </div>
      `;
    }
  }
}

function renderPDPMiniCard(p) {
  const inCart = state.cartMap[p.sku_id];
  const qty = inCart ? inCart.qty : 0;
  return `
    <div class="pdp-mini-card" onclick="openProductDetail(${p.sku_id}, event)">
      <div class="pdp-mini-img">${p.emoji || "🛍️"}${discountBadgeHTML(p.price, p.mrp)}</div>
      <div class="pdp-mini-title">${p.name}</div>
      <div class="pdp-mini-pack">${p.pack}</div>
      <div class="pdp-mini-bottom" onclick="event.stopPropagation()">
        <span class="pdp-mini-price">₹${p.price}</span>
        ${qty === 0 ? `
          <button class="add-btn-blinkit" style="padding:4px 8px; font-size:9px;" onclick="updateQty(${p.sku_id}, 1)">ADD</button>
        ` : `
          <span style="font-size:10px; font-weight:800; color:#16a34a;">${qty} in cart</span>
        `}
      </div>
    </div>
  `;
}

// 4. Update Quantity & Cart State
function updateQty(skuId, newQty) {
  const product = ALL_PRODUCTS.find(p => p.sku_id === skuId);
  if (!product) return;

  if (newQty <= 0) {
    delete state.cartMap[skuId];
  } else {
    state.cartMap[skuId] = { product, qty: newQty };
  }

  renderCurrentView();
  renderCartSidebar();
  triggerNearlineSimulation();
}

// 5. Render Cart Sidebar Drawer
function renderCartSidebar() {
  const items = Object.values(state.cartMap);
  const totalCount = items.reduce((sum, i) => sum + i.qty, 0);
  const itemTotalRupees = items.reduce((sum, i) => sum + (i.product.price * i.qty), 0);
  const grandTotal = itemTotalRupees > 0 ? itemTotalRupees + 4 : 0;

  drawerItemBadge.textContent = `${totalCount} Item${totalCount === 1 ? '' : 's'}`;
  const headerCartCount = document.getElementById("headerCartCount");
  if (headerCartCount) headerCartCount.textContent = totalCount;

  if (mobileFloatCount) mobileFloatCount.textContent = `${totalCount} item${totalCount === 1 ? '' : 's'}`;
  if (mobileFloatTotal) mobileFloatTotal.textContent = `₹${grandTotal}`;

  if (floatThumbPreviews) {
    floatThumbPreviews.textContent = items.length > 0
      ? items.slice(0, 3).map(i => i.product.emoji || "🛍️").join("")
      : "🛒";
  }

  // The bar is always available. With an empty cart it drops the ₹0 / 0 items
  // readout and offers just "View cart", which opens the empty basket drawer.
  if (mobileFloatingCartBar) {
    mobileFloatingCartBar.classList.remove("hidden");
    mobileFloatingCartBar.classList.toggle("cart-empty-mode", totalCount === 0);
  }

  renderFloatingPdpAddSlot();

  // Delivery Progress (₹199 Threshold)
  const freeThreshold = 199;
  if (itemTotalRupees >= freeThreshold || itemTotalRupees === 0) {
    deliveryProgressText.textContent = "Awesome! You saved ₹25 on Delivery Charge";
    progressBarFill.style.width = "100%";
  } else {
    const diff = freeThreshold - itemTotalRupees;
    deliveryProgressText.textContent = `Add items worth ₹${diff} more for FREE Delivery`;
    progressBarFill.style.width = `${(itemTotalRupees / freeThreshold) * 100}%`;
  }

  billItemTotal.textContent = `₹${itemTotalRupees}`;
  billGrandTotal.textContent = `₹${grandTotal}`;
  btnPayAmount.textContent = `₹${grandTotal}`;

  if (items.length === 0) {
    cartItemsWrapper.innerHTML = `
      <div class="empty-cart-state">
        <div class="empty-icon">🧺</div>
        <h4>Your basket is empty</h4>
        <p>Add items to your basket to test AI discovery recommendations on checkout!</p>
      </div>
    `;
    proceedCheckoutBtn.disabled = true;
  } else {
    cartItemsWrapper.innerHTML = items.map(i => {
      const p = i.product;
      const pct = discountPercent(p.price, p.mrp);
      const priceLine = pct > 0
        ? `<span class="cart-price-now">₹${p.price}</span>
           <span class="cart-price-mrp">₹${p.mrp}</span>
           <span class="price-off">${pct}% OFF</span>`
        : `<span class="cart-price-now">₹${p.price}</span>`;

      return `
        <div class="cart-item-row">
          <div class="item-info">
            <span class="title">${p.name}</span>
            <span class="price">${priceLine}<span class="cart-qty-x">× ${i.qty}</span></span>
          </div>
          <div class="stepper">
            <button onclick="updateQty(${p.sku_id}, ${i.qty - 1})">-</button>
            <span>${i.qty}</span>
            <button onclick="updateQty(${p.sku_id}, ${i.qty + 1})">+</button>
          </div>
        </div>
      `;
    }).join("");
    proceedCheckoutBtn.disabled = false;
  }
}

// On a product detail page the floating bar carries an ADD control for that
// item on the left, alongside "View cart" on the right.
function renderFloatingPdpAddSlot() {
  const slot = document.getElementById("floatPdpSlot");
  if (!slot || !mobileFloatingCartBar) return;

  const onPdp = state.currentView === "productDetail";
  const product = onPdp ? ALL_PRODUCTS.find(p => p.sku_id === state.activeProductSku) : null;

  mobileFloatingCartBar.classList.toggle("pdp-mode", !!product);

  if (!product) {
    slot.innerHTML = "";
    return;
  }

  const qty = state.cartMap[product.sku_id] ? state.cartMap[product.sku_id].qty : 0;

  slot.innerHTML = qty === 0
    ? `<button class="float-add-btn" onclick="updateQty(${product.sku_id}, 1)">
         <span class="float-add-label">ADD TO CART</span>
         <span class="float-add-price">₹${product.price}</span>
       </button>`
    : `<div class="float-add-stepper">
         <button onclick="updateQty(${product.sku_id}, ${qty - 1})">−</button>
         <span>${qty} in cart</span>
         <button onclick="updateQty(${product.sku_id}, ${qty + 1})">+</button>
       </div>`;
}

// Drawer Controls
if (headerCartBtn) {
  headerCartBtn.addEventListener("click", () => {
    if (cartSidebar) cartSidebar.classList.add("open");
  });
}

if (mobileViewCartBtn) {
  mobileViewCartBtn.addEventListener("click", () => {
    if (cartSidebar) {
      cartSidebar.classList.add("open");
      cartSidebar.classList.add("mobile-open");
    }
  });
}

if (closeDrawerBtn) {
  closeDrawerBtn.addEventListener("click", () => {
    if (cartSidebar) {
      cartSidebar.classList.remove("open");
      cartSidebar.classList.remove("mobile-open");
    }
  });
}

// 6. Trigger AI Nearline Simulation
async function triggerNearlineSimulation() {
  const items = Object.values(state.cartMap);
  if (items.length === 0) return;

  const cartItemsPayload = [];
  items.forEach(i => {
    for (let k = 0; k < i.qty; k++) {
      cartItemsPayload.push({
        sku_id: i.product.sku_id,
        l1_id: i.product.l1_id,
        l2_id: i.product.l2_id,
        name: i.product.name,
        price_paise: i.product.price * 100,
      });
    }
  });

  const subtotalPaise = items.reduce((sum, i) => sum + (i.product.price * i.qty * 100), 0);

  try {
    const payload = {
      user_id: state.userId,
      cart_id: `cart_${state.userId}_${Date.now()}`,
      cart_subtotal_paise: subtotalPaise,
      cart_items: cartItemsPayload,
      store_id: 1,
      time_of_day: getSystemTimeOfDay(),
      weather: getSystemWeather(),
    };

    const res = await fetch(`${API_BASE_URL}/v1/discovery/simulate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (res.status === 200) {
      const data = await res.json();
      state.lastDecision = data;
    }
  } catch (err) {
    console.error("Discovery API Simulation Exception:", err);
  }
}

// 7. Place Order Click (Pops Up AI Recommendation Sheet)
proceedCheckoutBtn.addEventListener("click", async () => {
  // 1. Show modal immediately with animated loading spinner
  slotABannerTitle.textContent = "AI Smart Recommendations";
  contextPillTag.textContent = `✨ Personalized For Your Order`;
  showRecLoadingState(multiRecsGrid);

  if (cartSidebar) {
    cartSidebar.classList.remove("open");
    cartSidebar.classList.remove("mobile-open");
  }
  slotAModalOverlay.classList.remove("hidden");

  // 2. Await fresh AI nearline simulation
  await triggerNearlineSimulation();
  stopRecLoadingState();

  // 3. Render fresh Groq AI recommendations
  const recs = (state.lastDecision && state.lastDecision.multi_recommendations) || [];
  slotABannerTitle.textContent = (state.lastDecision && state.lastDecision.reason_line) || "AI Recommendations for your Order";

  if (recs.length === 0) {
    multiRecsGrid.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 20px; color: #64748b;">
        <h4>Items in your basket are ready for checkout!</h4>
      </div>
    `;
    return;
  }

  multiRecsGrid.innerHTML = recs.map(recCardHTML).join("");
});

function addRecommendedSku(skuId) {
  let product = ALL_PRODUCTS.find(p => p.sku_id === skuId);
  if (!product) {
    product = {
      sku_id: skuId,
      l1_id: 20,
      l2_id: 201,
      name: "Himalaya Baby Gentle Wipes",
      pack: "72 wipes",
      price: 129,
      mrp: 150,
      cat: "baby",
      emoji: "👶",
    };
  }

  const existing = state.cartMap[skuId];
  const qty = existing ? existing.qty + 1 : 1;
  state.cartMap[skuId] = { product, qty };

  renderCurrentView();
  renderCartSidebar();
  closeModal();
}

dialogCloseBtn.addEventListener("click", closeModal);
modalSkipBtn.addEventListener("click", () => {
  closeModal();
  finalizeCheckout();
});

function closeModal() {
  slotAModalOverlay.classList.add("hidden");
}

// 8. Event Listeners for Category Navigation & Views
document.addEventListener("click", (e) => {
  const catTile = e.target.closest("[data-cat]");
  if (catTile) {
    const catSlug = catTile.dataset.cat;
    showView("category", catSlug);
    return;
  }

  const navItem = e.target.closest("[data-nav]");
  if (navItem) {
    const navVal = navItem.dataset.nav;
    if (navVal === "home") showView("home");
  }
});

if (backToHomeBtn) {
  backToHomeBtn.addEventListener("click", () => showView("home"));
}

if (searchBackBtn) {
  searchBackBtn.addEventListener("click", () => showView("home"));
}

if (sortSelect) {
  sortSelect.addEventListener("change", (e) => {
    state.sortBy = e.target.value;
    renderCategoryView();
  });
}

// Search Input Listener
if (searchInput) {
  searchInput.addEventListener("input", (e) => {
    state.searchQuery = e.target.value;
    if (clearSearchBtn) {
      if (state.searchQuery.trim() !== "") clearSearchBtn.classList.remove("hidden");
      else clearSearchBtn.classList.add("hidden");
    }

    if (state.searchQuery.trim() !== "") {
      showView("search");
    } else if (state.currentView === "search") {
      showView("home");
    }
  });
}

if (clearSearchBtn) {
  clearSearchBtn.addEventListener("click", () => {
    searchInput.value = "";
    state.searchQuery = "";
    clearSearchBtn.classList.add("hidden");
    showView("home");
  });
}

// PDP Action Buttons
const pdpBackBtn = document.getElementById("pdpBackBtn");
if (pdpBackBtn) {
  pdpBackBtn.addEventListener("click", () => {
    showView(state.previousView || "home");
  });
}

const pdpSearchBtn = document.getElementById("pdpSearchBtn");
if (pdpSearchBtn) {
  pdpSearchBtn.addEventListener("click", () => {
    showView("search");
    if (searchInput) searchInput.focus();
  });
}

// Location Modal Controls
const locationModalOverlay = document.getElementById("locationModalOverlay");
const closeLocationModalBtn = document.getElementById("closeLocationModalBtn");
const btnDetectGps = document.getElementById("btnDetectGps");
const locationSearchInput = document.getElementById("locationSearchInput");
const quickLocChips = document.getElementById("quickLocChips");
const headerAddressBtn = document.getElementById("headerAddressBtn");

function openLocationModal() {
  if (locationModalOverlay) locationModalOverlay.classList.remove("hidden");
}

function closeLocationModal() {
  if (locationModalOverlay) locationModalOverlay.classList.add("hidden");
}

if (headerAddressBtn) {
  headerAddressBtn.addEventListener("click", () => {
    openLocationModal();
  });
}

if (closeLocationModalBtn) {
  closeLocationModalBtn.addEventListener("click", () => {
    closeLocationModal();
  });
}

if (btnDetectGps) {
  btnDetectGps.addEventListener("click", async () => {
    closeLocationModal();
    await detectUserLocationAndWeather();
  });
}

if (locationSearchInput) {
  locationSearchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && locationSearchInput.value.trim()) {
      updateHeaderAddressDisplay(locationSearchInput.value.trim(), "search");
      closeLocationModal();
    }
  });
}

if (quickLocChips) {
  quickLocChips.addEventListener("click", (e) => {
    const btn = e.target.closest("button.loc-chip-btn");
    if (btn && btn.dataset.loc) {
      document.querySelectorAll("#quickLocChips .loc-chip-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      updateHeaderAddressDisplay(btn.dataset.loc, "picker");
      closeLocationModal();
    }
  });
}

// ============================================================================
// 9. ACCOUNTS — Log In / Sign Up (two distinct actions) & My Account page
// ============================================================================

const authView = document.getElementById("authView");
const authModeTabs = document.getElementById("authModeTabs");
const authForm = document.getElementById("authForm");
const authUsernameInput = document.getElementById("authUsernameInput");
const authPasswordInput = document.getElementById("authPasswordInput");
const authSubmitBtn = document.getElementById("authSubmitBtn");
const authErrorBox = document.getElementById("authErrorBox");
const authPageHeading = document.getElementById("authPageHeading");
const authContextNote = document.getElementById("authContextNote");
const authSwitchPrompt = document.getElementById("authSwitchPrompt");
const authSwitchLink = document.getElementById("authSwitchLink");
const authBackBtn = document.getElementById("authBackBtn");
const headerAccountBtn = document.getElementById("headerAccountBtn");
const accountBackBtn = document.getElementById("accountBackBtn");
const accountLogoutBtn = document.getElementById("accountLogoutBtn");

function authHeaders() {
  const headers = { "Content-Type": "application/json" };
  if (state.auth && state.auth.token) headers["Authorization"] = `Bearer ${state.auth.token}`;
  return headers;
}

function saveAuthSession(auth) {
  state.auth = auth;
  try {
    if (auth) localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(auth));
    else localStorage.removeItem(AUTH_STORAGE_KEY);
  } catch (e) {}
}

function restoreAuthSession() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && parsed.token && parsed.user) state.auth = parsed;
    }
  } catch (e) {}
}

function showAuthError(message) {
  if (!authErrorBox) return;
  authErrorBox.textContent = message;
  authErrorBox.classList.remove("hidden");
}

function clearAuthError() {
  if (authErrorBox) authErrorBox.classList.add("hidden");
}

// Opens the Log In / Sign Up page. `mode` picks which of the two actions is active.
function openAuthPage(mode = "login", opts = {}) {
  state.authMode = mode;
  state.pendingCheckout = !!opts.pendingCheckout;
  if (state.currentView !== "auth") state.returnView = state.currentView;
  clearAuthError();
  if (authUsernameInput) authUsernameInput.value = "";
  if (authPasswordInput) authPasswordInput.value = "";
  showView("auth");
}

function renderAuthView() {
  const isSignup = state.authMode === "signup";

  document.querySelectorAll(".auth-tab-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.authMode === state.authMode);
  });

  if (authPageHeading) authPageHeading.textContent = isSignup ? "Create your account" : "Log in to your account";
  if (authSubmitBtn) authSubmitBtn.textContent = isSignup ? "SIGN UP & CONTINUE" : "LOG IN";
  if (authPasswordInput) authPasswordInput.setAttribute("autocomplete", isSignup ? "new-password" : "current-password");

  if (authContextNote) {
    if (state.pendingCheckout) {
      authContextNote.textContent = isSignup
        ? "Almost there! Create an account to place your order — we'll save this delivery location and your order history to it."
        : "Almost there! Log in to place your order.";
    } else {
      authContextNote.textContent = isSignup
        ? "Sign up with a user name and password to start tracking your orders."
        : "Log in with your user name and password to see your account.";
    }
  }

  if (authSwitchPrompt) authSwitchPrompt.textContent = isSignup ? "Already have an account?" : "New to Blinkit?";
  if (authSwitchLink) authSwitchLink.textContent = isSignup ? "Log in instead" : "Create an account";
}

if (authModeTabs) {
  authModeTabs.addEventListener("click", (e) => {
    const btn = e.target.closest("button.auth-tab-btn");
    if (!btn) return;
    state.authMode = btn.dataset.authMode;
    clearAuthError();
    renderAuthView();
  });
}

if (authSwitchLink) {
  authSwitchLink.addEventListener("click", () => {
    state.authMode = state.authMode === "signup" ? "login" : "signup";
    clearAuthError();
    renderAuthView();
  });
}

if (authBackBtn) {
  authBackBtn.addEventListener("click", () => {
    state.pendingCheckout = false;
    showView(state.returnView === "auth" ? "home" : (state.returnView || "home"));
  });
}

// Log In and Sign Up hit different endpoints and mean different things:
// signup creates the account record, login only verifies against it.
if (authForm) {
  authForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAuthError();

    const username = (authUsernameInput.value || "").trim();
    const password = authPasswordInput.value || "";
    const isSignup = state.authMode === "signup";

    if (!username || !password) {
      showAuthError("Please enter both a user name and a password.");
      return;
    }
    if (isSignup && username.length < 3) {
      showAuthError("User name must be at least 3 characters long.");
      return;
    }
    if (isSignup && password.length < 4) {
      showAuthError("Password must be at least 4 characters long.");
      return;
    }

    authSubmitBtn.disabled = true;
    authSubmitBtn.textContent = isSignup ? "CREATING ACCOUNT..." : "LOGGING IN...";

    try {
      const endpoint = isSignup ? "/v1/auth/signup" : "/v1/auth/login";
      const body = isSignup
        ? {
            username,
            password,
            // Brand-new account record captures the guest session's history
            location_history: state.locationHistory,
            purchase_history: [],
          }
        : { username, password };

      const res = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        const detail = typeof data.detail === "string"
          ? data.detail
          : (isSignup ? "Could not create that account. Try a different user name." : "Incorrect username or password");
        showAuthError(detail);
        return;
      }

      saveAuthSession({ token: data.token, user: data.user });

      if (state.pendingCheckout) {
        state.pendingCheckout = false;
        await placeOrder();
      } else {
        await openAccountPage();
      }
    } catch (err) {
      console.error("Auth request failed:", err);
      showAuthError("Could not reach the server. Please try again.");
    } finally {
      authSubmitBtn.disabled = false;
      renderAuthView();
    }
  });
}

// ---- Checkout ----------------------------------------------------------

// Final checkout step, reached after the AI recommendation sheet.
function finalizeCheckout() {
  if (Object.keys(state.cartMap).length === 0) return;

  if (!state.auth) {
    // New user: send them to the Log In / Sign Up page before the order lands.
    openAuthPage("signup", { pendingCheckout: true });
    return;
  }
  placeOrder();
}

async function placeOrder() {
  const items = Object.values(state.cartMap);
  if (items.length === 0) {
    await openAccountPage();
    return;
  }

  const itemTotalRupees = items.reduce((sum, i) => sum + (i.product.price * i.qty), 0);
  const grandTotal = itemTotalRupees + 4;

  const payload = {
    items: items.map(i => ({
      sku_id: i.product.sku_id,
      name: i.product.name,
      pack: i.product.pack || "",
      emoji: i.product.emoji || "🛍️",
      qty: i.qty,
      price_paise: i.product.price * 100,
    })),
    total_paise: grandTotal * 100,
    location: liveUserLocation,
  };

  // Keep the category ids too — the tracking page reuses them to ask the
  // discovery engine for recommendations that suit what was just ordered.
  const trackedItems = items.map(i => ({
    sku_id: i.product.sku_id,
    l1_id: i.product.l1_id,
    l2_id: i.product.l2_id,
    name: i.product.name,
    pack: i.product.pack || "",
    emoji: i.product.emoji || "🛍️",
    qty: i.qty,
    price_paise: i.product.price * 100,
  }));

  try {
    const res = await fetch(`${API_BASE_URL}/v1/orders`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(payload),
    });

    if (res.status === 401) {
      saveAuthSession(null);
      openAuthPage("login", { pendingCheckout: true });
      showAuthError("Your session expired. Please log in again to place the order.");
      return;
    }

    if (!res.ok) {
      alert("Sorry, we could not place your order. Please try again.");
      return;
    }

    const data = await res.json();
    state.cartMap = {};
    renderCartSidebar();

    // The tracking page is the confirmation — it replaces the old alert().
    openTrackingPage({
      order_id: data.order_id,
      placed_at_ms: Date.now(),
      total_paise: payload.total_paise,
      location: payload.location,
      items: trackedItems,
    });
  } catch (err) {
    console.error("Order placement failed:", err);
    alert("Could not reach the server to place your order. Please try again.");
  }
}

// ---- Live order tracking (10-minute window) ----------------------------

function saveActiveOrder(order) {
  state.activeOrder = order;
  try {
    if (order) localStorage.setItem(TRACKING_STORAGE_KEY, JSON.stringify(order));
    else localStorage.removeItem(TRACKING_STORAGE_KEY);
  } catch (e) {}
}

function restoreActiveOrder() {
  try {
    const raw = localStorage.getItem(TRACKING_STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    // Only resume while the 10-minute window is still open.
    if (parsed && parsed.placed_at_ms && Date.now() - parsed.placed_at_ms < TRACKING_WINDOW_MS) {
      state.activeOrder = parsed;
    } else {
      localStorage.removeItem(TRACKING_STORAGE_KEY);
    }
  } catch (e) {}
}

function trackingElapsedMs() {
  if (!state.activeOrder) return 0;
  return Math.max(0, Date.now() - state.activeOrder.placed_at_ms);
}

function trackingIsLive() {
  return !!state.activeOrder && trackingElapsedMs() < TRACKING_WINDOW_MS;
}

function startTrackingTimer() {
  stopTrackingTimer();
  state.trackingTimer = setInterval(() => {
    if (state.currentView !== "tracking") return;
    renderTrackingClock();
    if (!trackingIsLive()) stopTrackingTimer();
  }, 1000);
}

function stopTrackingTimer() {
  if (state.trackingTimer) {
    clearInterval(state.trackingTimer);
    state.trackingTimer = null;
  }
}

// Opens the tracker for the order that was just placed.
function openTrackingPage(order) {
  saveActiveOrder(order);
  showView("tracking");
  startTrackingTimer();
  loadTrackingRecommendations();
}

// Ticking parts only — cheap enough to run every second.
function renderTrackingClock() {
  const order = state.activeOrder;
  if (!order) return;

  const elapsedMs = trackingElapsedMs();
  const remainingMs = Math.max(0, TRACKING_WINDOW_MS - elapsedMs);
  const delivered = remainingMs === 0;

  const label = document.getElementById("trackEtaLabel");
  const clock = document.getElementById("trackEtaClock");
  const fill = document.getElementById("trackProgressFill");
  const badge = document.getElementById("trackRiderBadge");
  const list = document.getElementById("trackStageList");
  const recsBox = document.getElementById("trackRecsBox");
  const recsSub = document.getElementById("trackRecsSub");

  if (label) label.textContent = delivered ? "Delivered" : "Arriving in";
  if (clock) {
    const mins = Math.floor(remainingMs / 60000);
    const secs = Math.floor((remainingMs % 60000) / 1000);
    clock.textContent = delivered ? "Enjoy! 🎉" : `${mins}:${String(secs).padStart(2, "0")}`;
  }
  if (fill) fill.style.width = `${Math.min(100, (elapsedMs / TRACKING_WINDOW_MS) * 100)}%`;
  if (badge) badge.textContent = delivered ? "✅" : "🛵";

  const elapsedSec = elapsedMs / 1000;
  const stages = delivered
    ? TRACKING_STAGES.concat([{ at: 600, icon: "🎉", label: "Delivered", sub: "Your order is at your door" }])
    : TRACKING_STAGES;

  if (list) {
    list.innerHTML = stages.map((s, idx) => {
      const reached = delivered || elapsedSec >= s.at;
      const next = stages[idx + 1];
      const isCurrent = reached && (!next || elapsedSec < next.at);
      const cls = ["track-stage-row", reached ? "done" : "pending", isCurrent ? "current" : ""].join(" ").trim();
      return `
        <div class="${cls}">
          <div class="track-stage-icon">${reached ? s.icon : "○"}</div>
          <div class="track-stage-text">
            <span class="track-stage-label">${s.label}</span>
            <span class="track-stage-sub">${isCurrent ? s.sub : ""}</span>
          </div>
          ${reached ? '<span class="track-stage-tick">✓</span>' : ""}
        </div>
      `;
    }).join("");
  }

  // The recommendation block belongs to the live window only.
  if (recsBox) recsBox.classList.toggle("hidden", delivered);
  if (recsSub && !delivered) {
    const minsLeft = Math.ceil(remainingMs / 60000);
    recsSub.textContent = `Still ${minsLeft} minute${minsLeft === 1 ? "" : "s"} to fill your cart again`;
  }
}

function renderTrackingView() {
  const order = state.activeOrder;
  if (!order) {
    showView("home");
    return;
  }

  const orderIdEl = document.getElementById("trackOrderId");
  const addrEl = document.getElementById("trackOrderAddr");
  const totalEl = document.getElementById("trackOrderTotal");
  const itemsEl = document.getElementById("trackOrderItems");

  if (orderIdEl) orderIdEl.textContent = `Order #${order.order_id}`;
  if (addrEl) addrEl.textContent = `📍 ${order.location || "your address"}`;
  if (totalEl) totalEl.textContent = `₹${Math.round(order.total_paise / 100)}`;

  if (itemsEl) {
    itemsEl.innerHTML = (order.items || []).map(i => `
      <div class="track-item-row">
        <span class="track-item-name">${i.emoji || "🛍️"} ${i.name}</span>
        <span class="track-item-qty">× ${i.qty}</span>
      </div>
    `).join("");
  }

  renderTrackingClock();
}

// Same witty engine as checkout, seeded with what they just ordered.
async function loadTrackingRecommendations() {
  const grid = document.getElementById("trackRecsGrid");
  const title = document.getElementById("trackRecsTitle");
  const order = state.activeOrder;
  if (!grid || !order) return;

  showRecLoadingState(grid);

  const cartItemsPayload = [];
  (order.items || []).forEach(i => {
    for (let k = 0; k < i.qty; k++) {
      cartItemsPayload.push({
        sku_id: i.sku_id,
        l1_id: i.l1_id || 0,
        l2_id: i.l2_id || 0,
        name: i.name,
        price_paise: i.price_paise,
      });
    }
  });

  try {
    const res = await fetch(`${API_BASE_URL}/v1/discovery/simulate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: state.userId,
        cart_id: `track_${order.order_id}`,
        cart_subtotal_paise: order.total_paise,
        cart_items: cartItemsPayload,
        store_id: 1,
        time_of_day: getSystemTimeOfDay(),
        weather: getSystemWeather(),
      }),
    });

    if (!res.ok) throw new Error(`simulate ${res.status}`);
    const data = await res.json();
    const recs = data.multi_recommendations || [];
    stopRecLoadingState();

    if (title) title.textContent = data.reason_line || "While you wait…";

    if (recs.length === 0) {
      grid.innerHTML = `<div class="rec-empty-note"><h4>Sit tight — your order is on its way.</h4></div>`;
      return;
    }

    grid.innerHTML = recs.map(recCardHTML).join("");
  } catch (err) {
    console.error("Tracking recommendations failed:", err);
    stopRecLoadingState();
    grid.innerHTML = `<div class="rec-empty-note"><h4>Sit tight — your order is on its way.</h4></div>`;
  }
}

const trackContinueBtn = document.getElementById("trackContinueBtn");
if (trackContinueBtn) {
  trackContinueBtn.addEventListener("click", () => showView("home"));
}

// ---- My Account page ---------------------------------------------------

// The 👤 icon: account page when signed in, Log In / Sign Up page when not.
async function openAccountPage() {
  if (!state.auth) {
    openAuthPage("login");
    return;
  }

  try {
    const res = await fetch(`${API_BASE_URL}/v1/account`, { headers: authHeaders() });

    if (res.status === 401) {
      saveAuthSession(null);
      openAuthPage("login");
      showAuthError("Your session expired. Please log in again.");
      return;
    }

    if (!res.ok) throw new Error(`Account fetch failed: ${res.status}`);
    state.accountData = await res.json();
    if (state.currentView !== "account") state.returnView = state.currentView;
    showView("account");
  } catch (err) {
    console.error("Could not load account:", err);
    alert("Could not load your account right now. Please try again.");
  }
}

function formatOrderTimestamp(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString([], {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function renderAccountView() {
  const data = state.accountData;
  const ordersList = document.getElementById("accountOrdersList");
  const locationsList = document.getElementById("accountLocationsList");
  if (!data || !ordersList || !locationsList) return;

  const username = data.user.username;

  document.getElementById("accountNameValue").textContent = username;
  document.getElementById("accountAvatarInitial").textContent = username.charAt(0);
  document.getElementById("accountMetaLine").textContent = `Member since ${formatOrderTimestamp(data.user.created_at)}`;

  const orders = data.orders || [];
  const locations = data.location_history || [];
  const totalSpent = orders.reduce((sum, o) => sum + o.total_paise, 0) / 100;

  document.getElementById("accountOrderCount").textContent = orders.length;
  document.getElementById("accountSpendTotal").textContent = `₹${Math.round(totalSpent)}`;
  document.getElementById("accountLocationCount").textContent = locations.length;

  if (orders.length === 0) {
    ordersList.innerHTML = `
      <div class="account-empty-state">
        <div class="empty-icon">🧾</div>
        <h4>No orders yet</h4>
        <p>Your placed orders will show up here.</p>
      </div>
    `;
  } else {
    ordersList.innerHTML = orders.map(o => `
      <div class="account-order-card">
        <div class="account-order-top-row">
          <div>
            <div class="account-order-id">Order #${o.order_id}</div>
            <div class="account-order-date">${formatOrderTimestamp(o.placed_at)}</div>
          </div>
          <div class="account-order-total">₹${Math.round(o.total_paise / 100)}</div>
        </div>
        ${o.location ? `<div class="account-order-loc">📍 Delivered to ${o.location}</div>` : ""}
        <div class="account-order-items">
          ${o.items.map(i => `
            <div class="account-order-item-row">
              <span>${i.emoji || "🛍️"} ${i.name}${i.pack ? ` <span class="qty-tag">(${i.pack})</span>` : ""}</span>
              <span class="qty-tag">× ${i.qty} · ₹${Math.round(i.price_paise / 100) * i.qty}</span>
            </div>
          `).join("")}
        </div>
      </div>
    `).join("");
  }

  if (locations.length === 0) {
    locationsList.innerHTML = `
      <div class="account-empty-state">
        <div class="empty-icon">📍</div>
        <h4>No saved locations yet</h4>
      </div>
    `;
  } else {
    locationsList.innerHTML = locations.map(l => `
      <div class="account-loc-row">
        <span>📍 ${l.location}</span>
        <span class="loc-time">${formatOrderTimestamp(l.recorded_at)}</span>
      </div>
    `).join("");
  }
}

if (headerAccountBtn) {
  headerAccountBtn.addEventListener("click", () => {
    openAccountPage();
  });
}

if (accountBackBtn) {
  accountBackBtn.addEventListener("click", () => showView("home"));
}

if (accountLogoutBtn) {
  accountLogoutBtn.addEventListener("click", async () => {
    try {
      await fetch(`${API_BASE_URL}/v1/auth/logout`, { method: "POST", headers: authHeaders() });
    } catch (e) {}
    saveAuthSession(null);
    state.accountData = null;
    showView("home");
  });
}

// Initial Setup
restoreAuthSession();
restoreActiveOrder();
updateHeaderAddressDisplay("NextLeap Office, Koramangala, Bangalore", "default");

// A reload during the 10-minute window drops you back on the tracker
// rather than the location picker.
if (trackingIsLive()) {
  showView("tracking");
  startTrackingTimer();
  loadTrackingRecommendations();
} else {
  openLocationModal();
}

loadFullCatalog();
renderCartSidebar();
