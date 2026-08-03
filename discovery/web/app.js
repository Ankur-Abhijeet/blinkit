// Authentic Blinkit Quick Commerce Client Script — Multi-Page & Multi-Section Routing

let ALL_PRODUCTS = [];
let state = {
  userId: 101,
  cartMap: {}, // sku_id -> { product, qty }
  currentView: "home", // "home" | "category" | "search"
  activeCategory: "all",
  activeCategoryTitle: "All Items",
  searchQuery: "",
  sortBy: "popular",
  lastDecision: null,
};

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
  // Wipe all legacy address strings cached in browser storage
  localStorage.clear();
  sessionStorage.clear();
} catch (e) {}

let liveUserLocation = "Select Location";
let liveWeatherCondition = "Pleasant & Breezy, 24°C";

function updateHeaderAddressDisplay(locText) {
  liveUserLocation = locText;
  const addressText = document.getElementById("headerAddressText");
  if (addressText) addressText.textContent = locText;
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
          updateHeaderAddressDisplay(`${locality}${city ? ", " + city : ""}`);
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

  if (homeView) homeView.classList.add("hidden");
  if (categoryView) categoryView.classList.add("hidden");
  if (searchView) searchView.classList.add("hidden");
  if (productDetailView) productDetailView.classList.add("hidden");
  if (pdpStickyBottomBar) pdpStickyBottomBar.classList.add("hidden");

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
    if (pdpStickyBottomBar) pdpStickyBottomBar.classList.remove("hidden");
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
  }
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

// Product Cards Generator
function renderProductCardsHTML(productsList) {
  return productsList.map(p => {
    const inCart = state.cartMap[p.sku_id];
    const qty = inCart ? inCart.qty : 0;

    return `
      <div class="blinkit-card" onclick="openProductDetail(${p.sku_id}, event)">
        <div class="card-top">
          <span class="time-badge">8 MINS</span>
        </div>
        <div class="card-img">${p.emoji || "🛍️"}</div>
        <div class="card-title">${p.name}</div>
        <div class="card-pack">${p.pack}</div>
        <div class="card-bottom" onclick="event.stopPropagation()">
          <div class="price-box">
            <span class="price-main">₹${p.price}</span>
            <span class="price-mrp">₹${p.mrp}</span>
          </div>
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
  const discountPct = Math.round((savings / (p.mrp || p.price)) * 100);

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
          <span class="pdp-pack-price">₹${Math.round(p.price * 1.9)}</span>
          <span class="pdp-pack-save">SAVE ₹${Math.round(p.mrp * 2 - p.price * 1.9)}</span>
        </div>
        <div class="pdp-pack-option-btn">
          <span class="pdp-pack-weight">4x Family</span>
          <span class="pdp-pack-price">₹${Math.round(p.price * 3.6)}</span>
          <span class="pdp-pack-save">SAVE ₹${Math.round(p.mrp * 4 - p.price * 3.6)}</span>
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
  if (pdpBottomMrp) pdpBottomMrp.textContent = `₹${p.mrp}`;

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
      <div class="pdp-mini-img">${p.emoji || "🛍️"}</div>
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

  if (floatThumbPreviews && items.length > 0) {
    floatThumbPreviews.textContent = items.slice(0, 3).map(i => i.product.emoji || "🛍️").join("");
  }

  if (totalCount > 0) {
    if (mobileFloatingCartBar) mobileFloatingCartBar.classList.remove("hidden");
  } else {
    if (mobileFloatingCartBar) mobileFloatingCartBar.classList.add("hidden");
    if (cartSidebar) {
      cartSidebar.classList.remove("open");
      cartSidebar.classList.remove("mobile-open");
    }
  }

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
    cartItemsWrapper.innerHTML = items.map(i => `
      <div class="cart-item-row">
        <div class="item-info">
          <span class="title">${i.product.name}</span>
          <span class="price">₹${i.product.price} × ${i.qty}</span>
        </div>
        <div class="stepper">
          <button onclick="updateQty(${i.product.sku_id}, ${i.qty - 1})">-</button>
          <span>${i.qty}</span>
          <button onclick="updateQty(${i.product.sku_id}, ${i.qty + 1})">+</button>
        </div>
      </div>
    `).join("");
    proceedCheckoutBtn.disabled = false;
  }
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
  multiRecsGrid.innerHTML = `
    <div style="grid-column: 1 / -1; text-align: center; padding: 30px 10px; color: #16a34a;">
      <div style="font-size: 36px; margin-bottom: 8px; animation: pulse 1s infinite alternate;">✨</div>
      <h4 style="font-size: 14px; font-weight: 800; color: #0f172a;">AI Engine Analyzing Basket Synergy...</h4>
      <p style="font-size: 11px; color: #64748b; margin-top: 4px;">Groq LLM is crafting personalized recommendations based on time, weather & basket context</p>
    </div>
  `;

  if (cartSidebar) {
    cartSidebar.classList.remove("open");
    cartSidebar.classList.remove("mobile-open");
  }
  slotAModalOverlay.classList.remove("hidden");

  // 2. Await fresh AI nearline simulation
  await triggerNearlineSimulation();

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

  multiRecsGrid.innerHTML = recs.map(r => {
    const cand = r.candidate;
    const priceRupees = (cand.price_paise / 100).toFixed(0);
    const mrpRupees = (cand.mrp_paise / 100).toFixed(0);

    let emoji = cand.emoji || "🛍️";
    if (!cand.emoji) {
      if (cand.l1_id === 20) emoji = "👶";
      else if (cand.l1_id === 25) emoji = "🐶";
      else if (cand.l1_id === 18) emoji = "🍫";
      else if (cand.l1_id === 88) emoji = "💊";
      else if (cand.l1_id === 35) emoji = "🧴";
      else if (cand.l1_id === 42) emoji = "🥤";
    }

    return `
      <div class="rec-card-item">
        <div class="rec-img-box">${emoji}</div>
        <div style="flex:1;">
          <div class="rec-title">${cand.name}</div>
          <div class="rec-reason">😏 ${r.headline || "Buying healthy food for your conscience and chips for your soul? We admire the duality of man. 🥔"}</div>
        </div>
        <div class="rec-price-row">
          <div>
            <strong style="font-size:13px;">₹${priceRupees}</strong>
            <span style="font-size:9px; text-decoration:line-through; color:#94a3b8; margin-left:3px;">₹${mrpRupees}</span>
          </div>
          <button class="rec-btn-add" onclick="addRecommendedSku(${cand.sku_id})">+ ADD</button>
        </div>
      </div>
    `;
  }).join("");
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
  alert("Order Placed Successfully! Your 10-Minute Blinkit Delivery has been dispatched. ⏱️");
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
      updateHeaderAddressDisplay(locationSearchInput.value.trim());
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
      updateHeaderAddressDisplay(btn.dataset.loc);
      closeLocationModal();
    }
  });
}

// Initial Setup
updateHeaderAddressDisplay("Select Location");
openLocationModal();
loadFullCatalog();
renderCartSidebar();
