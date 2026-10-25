// "Add New Piece" popup: pick a photo, check the form, send it to the server (POST /api/items).
// The server re-checks everything and shrinks the photo (images.py); these checks are for instant feedback.

const MAX_PHOTO_BYTES = 5 * 1024 * 1024;
const REQUIRED_FIELDS = ["item-name", "item-category", "item-color", "item-season", "item-occasion"];
const byId = (id) => document.getElementById(id);

let photoFile = null; // the chosen photo, sent with the form on submit

// Shows (or clears, when file is null) the photo preview inside the popup.
function setPhoto(file) {
  photoFile = file;
  const preview = byId("item-photo-preview");
  if (preview.src.startsWith("blob:")) URL.revokeObjectURL(preview.src); // free the old preview
  preview.src = file ? URL.createObjectURL(file) : "";
  preview.hidden = !file;
  byId("item-photo-clear").hidden = !file;
}

function handlePhotoFile(file) {
  if (!file) return;
  if (!/^image\/(jpeg|png|webp)$/.test(file.type)) return showToast("Please choose a JPG, PNG or WebP image.", "alert");
  if (file.size > MAX_PHOTO_BYTES) return showToast("That photo is over 5 MB — try a smaller one.", "alert");
  setPhoto(file);
}

// Click, keyboard and drag-and-drop all lead to handlePhotoFile.
function setupDropzone() {
  const zone = byId("item-dropzone");
  const input = byId("item-photo");

  zone.addEventListener("click", () => input.click());
  zone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); }
  });
  input.addEventListener("change", () => {
    handlePhotoFile(input.files[0]);
    input.value = ""; // lets you pick the same file again after removing it
  });
  ["dragenter", "dragover"].forEach((type) => zone.addEventListener(type, (e) => {
    e.preventDefault();
    zone.classList.add("is-dragover");
  }));
  ["dragleave", "drop"].forEach((type) => zone.addEventListener(type, (e) => {
    e.preventDefault();
    zone.classList.remove("is-dragover");
  }));
  zone.addEventListener("drop", (e) => handlePhotoFile(e.dataTransfer.files[0]));
  byId("item-photo-clear").addEventListener("click", () => setPhoto(null));
}

// Choosing "Other…" in a dropdown reveals a box for typing your own value.
function setupOtherFields() {
  document.querySelectorAll("select[data-other]").forEach((select) => {
    const box = byId(select.dataset.other);
    select.addEventListener("change", () => {
      box.hidden = select.value !== "__other";
      if (!box.hidden) box.focus();
    });
    box.addEventListener("input", () => clearFieldError(box));
  });
}

// Marks every empty required field (including a visible "Other" box) and returns true only if none are empty.
function validateForm() {
  const required = [...REQUIRED_FIELDS.map(byId), ...document.querySelectorAll(".other-input:not([hidden])")];
  const empty = required.filter((field) => !field.value.trim());
  empty.forEach(showFieldError);
  if (empty.length) empty[0].focus();
  return empty.length === 0;
}

function resetForm() {
  byId("add-item-form").reset();
  setPhoto(null);
  REQUIRED_FIELDS.forEach((id) => clearFieldError(byId(id)));
  document.querySelectorAll(".other-input").forEach((box) => { box.hidden = true; clearFieldError(box); });
}

async function handleSubmit(event) {
  event.preventDefault();
  if (!validateForm()) return showToast("A few details are missing.", "alert");

  const button = byId("add-item-submit");
  button.disabled = true; // stops a double click from adding the piece twice

  const form = new FormData(event.currentTarget); // gathers every field by its name=""
  form.delete("image");
  if (photoFile) form.append("image", photoFile);

  const { ok, data } = await api("POST", "/api/items", form);
  button.disabled = false;
  if (!ok) return showToast(data.error || "We couldn't save that piece.", "alert");

  toastAfterReload(`${data.item.name} added to your closet.`);
  window.location.reload(); // the server renders every page from the database, so reload shows the truth
}

function initAddItemModal() {
  const modalEl = byId("addItemModal");
  if (!modalEl) return;

  setupDropzone();
  setupOtherFields();
  byId("add-item-form").addEventListener("submit", handleSubmit);
  REQUIRED_FIELDS.forEach((id) => {
    ["input", "change"].forEach((type) => byId(id).addEventListener(type, () => clearFieldError(byId(id))));
  });

  modalEl.addEventListener("shown.bs.modal", () => byId("item-name").focus());
  modalEl.addEventListener("hidden.bs.modal", resetForm); // cancelling gives a clean form next time

  // /wardrobe/add redirects to /wardrobe?add=1: open the popup straight away.
  if (new URLSearchParams(window.location.search).get("add") === "1") {
    bootstrap.Modal.getOrCreateInstance(modalEl).show();
    window.history.replaceState(null, "", window.location.pathname);
  }
}

document.addEventListener("DOMContentLoaded", initAddItemModal);
