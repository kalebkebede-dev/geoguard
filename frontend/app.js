const TOKEN_KEY = "geoguard_token";
const EMAIL_KEY = "geoguard_email";

let lastLookup = null; // { lat, lon } of the most recent map click

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function setLoggedIn(email) {
  localStorage.setItem(EMAIL_KEY, email);
  document.getElementById("login-form").classList.add("hidden");
  document.getElementById("logged-in-panel").classList.remove("hidden");
  document.getElementById("logged-in-email").textContent = email;
  document.getElementById("saved-locations-panel").classList.remove("hidden");
  refreshSavedLocations();
  // If a lookup already happened before login (or on page reload with an
  // existing session), the save button needs to reflect that now -- it's
  // not only set at lookup time.
  if (lastLookup) {
    document.getElementById("save-location-btn").classList.remove("hidden");
  }
}

function setLoggedOut() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(EMAIL_KEY);
  document.getElementById("login-form").classList.remove("hidden");
  document.getElementById("logged-in-panel").classList.add("hidden");
  document.getElementById("saved-locations-panel").classList.add("hidden");
  document.getElementById("save-location-btn").classList.add("hidden");
}

// ---- Map + AQI lookup ----

const map = L.map("map").setView([39.5, -98.35], 4); // continental US

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "&copy; OpenStreetMap contributors",
  maxZoom: 18,
}).addTo(map);

let lookupMarker = null;

function categoryClass(category) {
  return "category-" + category.toLowerCase().replace(/ /g, "-");
}

async function lookupAqi(lat, lon) {
  const resultEl = document.getElementById("lookup-result");
  resultEl.textContent = "Loading…";

  const response = await fetch(`/aqi/current?lat=${lat}&lon=${lon}`);
  const data = await response.json();

  if (data.count === 0) {
    resultEl.textContent = "No stations found within range of this point.";
  } else {
    resultEl.innerHTML = data.readings
      .map(
        (r) => `
        <div class="reading-card ${categoryClass(r.category)}">
          <strong>${r.station_name}</strong><br/>
          ${r.pollutant}: AQI ${r.aqi_value} (${r.category})
        </div>`
      )
      .join("");
  }

  lastLookup = { lat, lon };
  if (getToken()) {
    document.getElementById("save-location-btn").classList.remove("hidden");
  }
}

map.on("click", (e) => {
  if (lookupMarker) map.removeLayer(lookupMarker);
  lookupMarker = L.marker(e.latlng).addTo(map);
  lookupAqi(e.latlng.lat, e.latlng.lng);
});

// ---- Auth ----

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  await doAuth("/auth/login");
});

document.getElementById("signup-btn").addEventListener("click", async () => {
  await doAuth("/auth/signup");
});

async function doAuth(path) {
  const email = document.getElementById("email-input").value;
  const password = document.getElementById("password-input").value;
  const errorEl = document.getElementById("auth-error");
  errorEl.textContent = "";

  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const detail = (await response.json().catch(() => ({}))).detail;
    errorEl.textContent = detail || "Something went wrong.";
    return;
  }

  const data = await response.json();
  localStorage.setItem(TOKEN_KEY, data.access_token);
  setLoggedIn(email);
}

document.getElementById("logout-btn").addEventListener("click", setLoggedOut);

// ---- Saved locations ----

async function refreshSavedLocations() {
  const response = await fetch("/locations", { headers: authHeaders() });
  if (!response.ok) {
    if (response.status === 401) setLoggedOut();
    return;
  }
  const locations = await response.json();

  const listEl = document.getElementById("saved-locations-list");
  listEl.innerHTML = locations
    .map(
      (loc) => `
      <li>
        <span>${loc.label} (${loc.latitude.toFixed(2)}, ${loc.longitude.toFixed(2)})</span>
        <button data-id="${loc.id}" class="remove-location-btn">Remove</button>
      </li>`
    )
    .join("");

  document.querySelectorAll(".remove-location-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await fetch(`/locations/${btn.dataset.id}`, { method: "DELETE", headers: authHeaders() });
      refreshSavedLocations();
    });
  });
}

document.getElementById("save-location-btn").addEventListener("click", async () => {
  if (!lastLookup) return;
  const label = prompt("Label for this location?", "My location");
  if (!label) return;

  await fetch("/locations", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ label, latitude: lastLookup.lat, longitude: lastLookup.lon }),
  });
  refreshSavedLocations();
});

// ---- Init ----

if (getToken()) {
  setLoggedIn(localStorage.getItem(EMAIL_KEY));
}
