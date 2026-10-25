// Outfit Matcher page: sends your choices to the server (POST /api/outfits/suggest), draws the look it
// returns, and saves or wears it (POST /api/outfits). The scoring itself lives in outfit_engine.py.

const SLOT_LABELS = { top: "Top", bottom: "Bottom", footwear: "Shoes", outerwear: "Layer", accessory: "Finish" };
const $ = (id) => document.getElementById(id);

let current = null; // the look on screen: { outfit, choices, total }
let seen = [];      // keys of looks already shown for these choices, so Shuffle never repeats until all are used
let busy = false;   // ignore clicks while a look is loading

function getChoices() {
  const choices = {};
  document.querySelectorAll("[data-option]").forEach((group) => {
    choices[group.dataset.option] = getActivePillValue(group);
  });
  return choices;
}

// Asks the server for a look. `seen` makes it skip looks we've already shown.
async function requestLook(choices) {
  busy = true;
  const prefs = readStore(STORAGE_KEYS.profile, { styles: [], colors: [] }); // from the Profile page
  const { ok, data } = await api("POST", "/api/outfits/suggest", { ...choices, seen, prefs });
  busy = false;
  if (!ok) {
    showToast(data.error || "We couldn't build a look just now.", "alert");
    return null;
  }
  return data;
}

function renderMissing(missing, choices) {
  const names = missing.map((slot) => getCategoryLabel(slot).toLowerCase());
  $("outfit-grid").innerHTML =
    '<div class="empty-state"><span class="empty-icon"><i class="bi bi-puzzle" aria-hidden="true"></i></span>' +
    `<h3>Almost there</h3><p>Your closet has no ${escapeHtml(names.join(" or "))} that suits ${escapeHtml(choices.season.toLowerCase())} yet. ` +
    'Add one and the matcher can finish this look.</p>' +
    '<button class="btn-coral" type="button" data-bs-toggle="modal" data-bs-target="#addItemModal"><i class="bi bi-plus-lg"></i>Add a piece</button></div>';
}

function showResult(data, choices) {
  $("canvas-empty").hidden = true;
  const result = $("outfit-result");
  result.hidden = false;
  result.classList.remove("is-fresh");
  void result.offsetWidth; // restart the fade-in animation
  result.classList.add("is-fresh");

  const complete = !data.missing;
  document.querySelectorAll(".outfit-actions, .outfit-reason, #outfit-score").forEach((el) => { el.hidden = !complete; });
  if (!complete) {
    current = null;
    $("outfit-title").textContent = "Not enough pieces yet";
    return renderMissing(data.missing, choices);
  }

  const { outfit, total } = data;
  current = { outfit, choices, total };
  $("outfit-title").textContent = `Your ${choices.occasion.toLowerCase()} look`;
  $("outfit-score").textContent = `${outfit.match_percent}% match · look ${seen.length} of ${total}`;
  $("outfit-reasons").innerHTML = outfit.reasons.map((reason) => `<li>${escapeHtml(reason)}</li>`).join("");
  $("outfit-grid").innerHTML = outfit.items.map(({ slot, item }) =>
    `<div class="outfit-slot"><span class="slot-label">${SLOT_LABELS[slot]}</span>${renderItemCard(item)}</div>`).join("");
}

function flagMissingOption(key) {
  const group = document.querySelector(`[data-option="${key}"]`);
  group.classList.remove("is-invalid");
  void group.offsetWidth;
  group.classList.add("is-invalid");
  setTimeout(() => group.classList.remove("is-invalid"), 400);
}

async function handleMatch(event) {
  const choices = getChoices();
  const unpicked = ["occasion", "season"].filter((key) => !choices[key]);
  if (unpicked.length) {
    unpicked.forEach(flagMissingOption);
    return showToast("Pick an occasion and a season first.", "alert");
  }
  if (busy) return;

  const box = event.currentTarget.getBoundingClientRect();
  sparkleBurst({ x: box.left + box.width / 2, y: box.top + box.height / 2 }); // starts at once, so it feels instant
  seen = []; // new choices: start a fresh list of shown looks
  const data = await requestLook(choices);
  if (!data) return;
  if (data.outfit) seen.push(data.outfit.key);
  showResult(data, choices);
}

async function handleShuffle() {
  if (!current || busy) return;
  const data = await requestLook(current.choices);
  if (!data) return;
  if (data.exhausted) {
    showToast(`You've seen all ${data.total} looks your closet can make for this. Starting over.`);
    seen = [];
  }
  seen.push(data.outfit.key);
  showResult(data, current.choices);
}

// "Wear this today" and "Save look" both post the current look; only `source` differs.
async function logCurrentLook(source, button) {
  if (!current || button.disabled) return;
  button.disabled = true;
  const { choices, outfit } = current;
  const { ok, data } = await api("POST", "/api/outfits", {
    item_ids: outfit.items.map(({ item }) => item.id), occasion: choices.occasion, season: choices.season, source,
  });
  button.disabled = false;
  showToast(ok ? data.message : data.error || "We couldn't save that look.", ok ? undefined : "alert");
}

function resetMatcher() {
  document.querySelectorAll("[data-option] .pill").forEach((pill) => {
    pill.classList.remove("is-active");
    pill.setAttribute("aria-pressed", "false");
  });
  current = null;
  seen = [];
  $("outfit-result").hidden = true;
  $("canvas-empty").hidden = false;
}

document.addEventListener("DOMContentLoaded", () => {
  if (!$("match-btn")) return;
  document.querySelectorAll("[data-option]").forEach((group) => {
    const optional = ["style", "color"].includes(group.dataset.option); // optional groups can be un-picked
    setupSinglePillGroup(group, null, optional);
  });
  $("match-btn").addEventListener("click", handleMatch);
  $("shuffle-btn").addEventListener("click", handleShuffle);
  $("reset-btn").addEventListener("click", resetMatcher);
  $("save-btn").addEventListener("click", (e) => logCurrentLook("saved", e.currentTarget));
  $("wear-btn").addEventListener("click", (e) => logCurrentLook("worn", e.currentTarget));
});
