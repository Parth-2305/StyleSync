// Hangers page: pair a reader, link tags to pieces, simulate a scan. All data changes go through the server (api() in app.js).

const $ = (id) => document.getElementById(id);

// Two-click safety for destructive buttons: the first click turns the button into "Sure?" for 3 seconds.
function confirmClick(button, action) {
  if (!button.classList.contains("is-armed")) {
    const original = button.innerHTML;
    button.classList.add("is-armed");
    button.textContent = "Sure?";
    setTimeout(() => { button.classList.remove("is-armed"); button.innerHTML = original; }, 3000);
    return;
  }
  action();
}

async function sendAndReload(method, url, body, message) {
  const { ok, data } = await api(method, url, body);
  if (!ok) return showToast(data.error || "Something went wrong.", "alert");
  toastAfterReload(data.message || message || "Done.");
  window.location.reload();
}

async function addDevice(event) {
  event.preventDefault();
  const name = $("device-name").value.trim();
  if (!name) return showToast("Give the reader a name first.", "alert");
  const { ok, data } = await api("POST", "/api/devices", { name });
  if (!ok) return showToast(data.error || "Couldn't pair the reader.", "alert");
  $("key-value").textContent = data.key; // shown once: the server keeps only a hash
  $("key-reveal").hidden = false;
  $("device-name").value = "";
}

async function linkTag(tag, itemId) {
  if (!itemId) return showToast("Choose a piece first.", "alert");
  return sendAndReload("POST", "/api/tags/link", { tag_uid: tag, item_id: itemId }, "Tag linked. Scanning it now logs that piece as worn.");
}

// Live updates: every 3 seconds ask "has any tag changed?". If yes (a scan happened), show the message and reload the lists.
// We never reload while you are typing or while the one-time reader key is on screen.
function startLiveUpdates() {
  const page = $("hangers-page");
  let busy = false;
  setInterval(async () => {
    if (document.hidden || busy) return;
    busy = true;
    const { ok, data } = await api("GET", "/api/tags/feed");
    busy = false;
    if (!ok || data.state === page.dataset.state) return;
    const typing = ["INPUT", "SELECT"].includes(document.activeElement && document.activeElement.tagName);
    if (!$("key-reveal").hidden || typing) return; // try again at the next tick, once it is safe
    if (data.latest) toastAfterReload(data.latest);
    window.location.reload();
  }, 3000);
}

document.addEventListener("DOMContentLoaded", () => {
  if (!$("hangers-page")) return;
  startLiveUpdates();

  $("add-device-form").addEventListener("submit", addDevice);
  $("key-copy").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText($("key-value").textContent); showToast("Key copied."); }
    catch (error) { showToast("Select the key and copy it by hand.", "alert"); }
  });
  $("key-done").addEventListener("click", () => window.location.reload()); // hides the key and shows the new reader

  $("manual-link-form").addEventListener("submit", (e) => {
    e.preventDefault();
    linkTag($("manual-tag").value, $("manual-item").value);
  });
  $("simulate-form").addEventListener("submit", (e) => {
    e.preventDefault();
    sendAndReload("POST", "/api/tags/simulate", { tag_uid: $("simulate-tag").value });
  });

  // One listener for every button in the lists (the lists are drawn by the server).
  $("hangers-page").addEventListener("click", (e) => {
    const link = e.target.closest("[data-link]");
    if (link) return linkTag(link.dataset.link, link.closest("li").querySelector(".link-select").value);
    const sim = e.target.closest("[data-simulate]");
    if (sim) return sendAndReload("POST", "/api/tags/simulate", { tag_uid: sim.dataset.simulate });
    const forget = e.target.closest("[data-forget]");
    if (forget) return confirmClick(forget, () => sendAndReload("DELETE", `/api/tags/${forget.dataset.forget}`, null, "Tag removed."));
    const device = e.target.closest("[data-remove-device]");
    if (device) return confirmClick(device, () => sendAndReload("DELETE", `/api/devices/${device.dataset.removeDevice}`, null, "Reader removed. Its key no longer works."));
  });
});
