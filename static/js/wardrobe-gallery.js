// Wardrobe gallery: category pills + search box filter the cards, and each card has a delete button.
// The cards themselves are drawn by the server (templates/includes/macros.html).

const filter = { category: "all", search: "" };

function applyFilter() {
  const cards = document.querySelectorAll("#item-grid .item-card");
  let visible = 0;
  cards.forEach((card) => {
    const inCategory = filter.category === "all" || card.dataset.category === filter.category;
    const matchesSearch = !filter.search || card.dataset.search.includes(filter.search);
    card.hidden = !(inCategory && matchesSearch);
    if (!card.hidden) visible += 1;
  });
  document.getElementById("result-count").textContent =
    `Showing ${visible} of ${cards.length} ${cards.length === 1 ? "piece" : "pieces"}`;
  document.getElementById("wardrobe-empty").hidden = visible > 0 || cards.length === 0;
}

function resetFilter() {
  filter.category = "all";
  filter.search = "";
  document.getElementById("wardrobe-search").value = "";
  document.querySelectorAll("#category-pills .pill").forEach((pill) => {
    const isAll = pill.dataset.filter === "all";
    pill.classList.toggle("is-active", isAll);
    pill.setAttribute("aria-pressed", String(isAll));
  });
  applyFilter();
}

// Delete needs two clicks: the first turns the button into "Sure?" for 3 seconds.
// (A pop-up confirm() would clash with the theme.)
async function handleDeleteClick(event) {
  const button = event.target.closest(".item-delete");
  if (!button) return;

  if (!button.classList.contains("is-armed")) {
    button.classList.add("is-armed");
    button.textContent = "Sure?";
    setTimeout(() => {
      button.classList.remove("is-armed");
      button.innerHTML = '<i class="bi bi-trash3" aria-hidden="true"></i>';
    }, 3000);
    return;
  }

  const { ok, data } = await api("DELETE", `/api/items/${button.dataset.id}`);
  if (!ok) return showToast(data.error || "Couldn't remove that piece.", "alert");
  toastAfterReload("Piece removed.");
  window.location.reload();
}

function initWardrobeGallery() {
  const grid = document.getElementById("item-grid");
  if (!grid) return;

  setupSinglePillGroup(document.getElementById("category-pills"), (value) => {
    filter.category = value || "all";
    applyFilter();
  });
  document.getElementById("wardrobe-search").addEventListener("input", (e) => {
    filter.search = e.target.value.trim().toLowerCase();
    applyFilter();
  });
  document.getElementById("clear-filters").addEventListener("click", resetFilter);
  grid.addEventListener("click", handleDeleteClick);
}

document.addEventListener("DOMContentLoaded", initWardrobeGallery);
