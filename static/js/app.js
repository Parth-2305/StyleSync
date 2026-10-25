// Shared helpers used by every logged-in page script.
// Wardrobe items and outfit history live in the database. Only profile preferences are still kept
// in this browser's localStorage.

var STORAGE_KEYS = {
  profile: "stylesync.profile"
};

// localStorage can throw (private mode, quota full), so every read/write is guarded
// and falls back to a safe default instead of breaking the page.
function readStore(key, fallback) {
  try {
    var raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (error) {
    return fallback;
  }
}

function writeStore(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch (error) {
    showToast("Couldn't save in this browser — storage may be full.", "alert");
    return false;
  }
}

// Item names and notes come from user input, so escape before putting them in innerHTML.
function escapeHtml(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function getCategoryLabel(category) {
  return (window.STYLESYNC && window.STYLESYNC.categoryLabels[category]) || category;
}

function getColorHex(colorName) {
  var colors = (window.STYLESYNC && window.STYLESYNC.colors) || [];
  var match = colors.find(function (color) { return color.name === colorName; });
  return match ? match.hex : "#D1D5DB";
}

// Draws an item card for the Outfit Matcher results (the gallery uses the Jinja macro in macros.html).
// The hanger-tag line under a card (only the matcher sends item.tagged, so other pages are unchanged).
function tagStatus(item) {
  if (item.tagged === undefined) return "";
  return item.tagged
    ? '<p class="tag-status is-tagged"><span class="status-dot" aria-hidden="true"></span><i class="bi bi-tags" aria-hidden="true"></i>Hanger tag assigned</p>'
    : '<p class="tag-status"><span class="status-dot" aria-hidden="true"></span>No hanger tag</p>';
}

function renderItemCard(item, extraClass) {
  var photo = item.image_url
    ? '<img src="' + escapeHtml(item.image_url) + '" alt="' + escapeHtml(item.color + " " + item.name) + '" loading="lazy">'
    : '<div class="item-photo-empty"><i class="bi bi-image" aria-hidden="true"></i></div>';
  var searchText = (item.name + " " + item.color + " " + item.style).toLowerCase();

  return (
    '<article class="item-card' + (extraClass ? " " + extraClass : "") + '" data-category="' + escapeHtml(item.category) + '" data-search="' + escapeHtml(searchText) + '">' +
      '<div class="item-photo">' + photo +
        '<span class="tag">' + escapeHtml(getCategoryLabel(item.category)) + "</span>" +
      "</div>" +
      '<div class="item-body">' +
        "<h3>" + escapeHtml(item.name) + "</h3>" +
        '<div class="item-meta">' +
          '<span class="d-inline-flex align-items-center gap-1">' +
            '<span class="swatch" style="background: ' + escapeHtml(getColorHex(item.color)) + '"></span>' + escapeHtml(item.color) +
          "</span>" +
          '<span class="dot"></span><span>' + escapeHtml(item.season.join(", ")) + "</span>" +
          '<span class="dot"></span><span>' + escapeHtml(item.style) + "</span>" +
        "</div>" +
        tagStatus(item) +
      "</div>" +
    "</article>"
  );
}

// Makes a row of .pill buttons behave like a radio group (one active at a time).
// Pass allowNone=true to let a second click deselect the active pill.
function setupSinglePillGroup(container, onChange, allowNone) {
  container.addEventListener("click", function (event) {
    var pill = event.target.closest(".pill");
    if (!pill || !container.contains(pill)) {
      return;
    }
    var wasActive = pill.classList.contains("is-active");
    container.querySelectorAll(".pill").forEach(function (other) {
      other.classList.remove("is-active");
      other.setAttribute("aria-pressed", "false");
    });
    if (!(wasActive && allowNone)) {
      pill.classList.add("is-active");
      pill.setAttribute("aria-pressed", "true");
    }
    if (onChange) {
      onChange(getActivePillValue(container));
    }
  });
}

function getActivePillValue(container) {
  var active = container.querySelector(".pill.is-active");
  return active ? active.getAttribute("data-value") || active.getAttribute("data-filter") : "";
}

// Makes a row of .chip buttons behave like checkboxes (multi-select).
function setupChipGroup(container) {
  container.addEventListener("click", function (event) {
    var chip = event.target.closest(".chip");
    if (!chip || !container.contains(chip)) {
      return;
    }
    var selected = chip.getAttribute("aria-pressed") !== "true";
    chip.setAttribute("aria-pressed", selected ? "true" : "false");
  });
}

function getSelectedChipValues(container) {
  return Array.prototype.map.call(container.querySelectorAll('.chip[aria-pressed="true"]'), function (chip) {
    return chip.getAttribute("data-value");
  });
}

function setSelectedChipValues(container, values) {
  container.querySelectorAll(".chip").forEach(function (chip) {
    var selected = values.indexOf(chip.getAttribute("data-value")) !== -1;
    chip.setAttribute("aria-pressed", selected ? "true" : "false");
  });
}

// Shared field-error helpers: red border + shake + a text message (never colour alone).
function showFieldError(field) {
  field.classList.remove("is-invalid");
  void field.offsetWidth; // restart the shake animation if it's already invalid
  field.classList.add("is-invalid");
  field.setAttribute("aria-invalid", "true");
  var message = document.querySelector('[data-error-for="' + field.id + '"]');
  if (message) {
    message.classList.add("is-visible");
  }
}

function clearFieldError(field) {
  field.classList.remove("is-invalid");
  field.removeAttribute("aria-invalid");
  var message = document.querySelector('[data-error-for="' + field.id + '"]');
  if (message) {
    message.classList.remove("is-visible");
  }
}

// Talks to our Flask server. `body` may be a plain object (sent as JSON) or FormData (for photo uploads).
// Adds the CSRF token every non-GET request needs. Never throws: resolves to {ok, data}, and
// data.error is already a safe, generic message you can show in a toast.
async function api(method, url, body) {
  const headers = { "X-CSRFToken": document.querySelector('meta[name="csrf-token"]').content };
  if (body && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(body);
  }
  try {
    const response = await fetch(url, { method, headers, body });
    const data = await response.json().catch(() => ({}));
    return { ok: response.ok, data };
  } catch (error) {
    return { ok: false, data: { error: "Can't reach the server. Check your connection." } };
  }
}

// A page reload wipes any toast, so we stash the message and show it after the reload.
function toastAfterReload(message) {
  try { sessionStorage.setItem("stylesync.toast", message); } catch (error) { /* just skip the toast */ }
}

document.addEventListener("DOMContentLoaded", () => {
  try {
    const message = sessionStorage.getItem("stylesync.toast");
    if (message) {
      sessionStorage.removeItem("stylesync.toast");
      showToast(message);
    }
  } catch (error) { /* storage blocked: nothing to show */ }
});

document.addEventListener("click", async (event) => {
  if (!event.target.closest("#logout-btn")) return;
  const { data } = await api("POST", "/auth/logout");
  window.location.href = data.redirect || "/";
});
