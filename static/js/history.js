// History page: the Worn / Saved tabs, and "Remove from saved".
// The cards are drawn by the server (templates/history.html); this file only switches tabs and removes.

const TABS = ["worn", "saved"];

// Shows one tab's list (or its empty message) and hides the other.
function showTab(name) {
  TABS.forEach((tab) => {
    const hasCards = document.querySelectorAll(`#list-${tab} .history-card`).length > 0;
    document.getElementById(`list-${tab}`).hidden = tab !== name || !hasCards;
    document.getElementById(`empty-${tab}`).hidden = tab !== name || hasCards;
  });
  document.querySelectorAll("#history-tabs .pill").forEach((pill) => {
    const active = pill.dataset.filter === name;
    pill.classList.toggle("is-active", active);
    pill.setAttribute("aria-pressed", String(active));
  });
}

async function removeSaved(button) {
  button.disabled = true; // no double clicks
  const { ok, data } = await api("DELETE", `/api/outfits/${button.dataset.remove}`);
  if (!ok) {
    button.disabled = false;
    return showToast(data.error || "Couldn't remove that look.", "alert");
  }
  const card = button.closest(".history-card");
  card.classList.add("is-removing"); // fade out, then take it away
  setTimeout(() => {
    card.remove();
    document.getElementById("count-saved").textContent = document.querySelectorAll("#list-saved .history-card").length;
    showTab("saved");
    showToast("Removed from saved.");
  }, 250);
}

document.addEventListener("DOMContentLoaded", () => {
  const page = document.getElementById("history-page");
  if (!page) return;

  document.getElementById("history-tabs").addEventListener("click", (e) => {
    const pill = e.target.closest(".pill");
    if (pill) showTab(pill.dataset.filter);
  });
  page.addEventListener("click", (e) => {
    const button = e.target.closest("[data-remove]");
    if (button) removeSaved(button);
  });
  showTab(page.dataset.startTab); // "?tab=saved" (from the dashboard card) opens Saved first
});
