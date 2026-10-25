// Profile: style + colour preference chips. Saved preferences are read by
// outfit-matcher.js to break ties in favour of pieces that "feel like you".
// BACKEND TODO: persist to the `profiles` table instead of localStorage.

var DEFAULT_PROFILE = { styles: [], colors: [], city: "" };

function applyProfileToForm(profile) {
  setSelectedChipValues(document.getElementById("style-chips"), profile.styles || []);
  setSelectedChipValues(document.getElementById("color-chips"), profile.colors || []);
  document.getElementById("profile-city").value = profile.city || "";
}

function handleProfileSave() {
  var profile = {
    styles: getSelectedChipValues(document.getElementById("style-chips")),
    colors: getSelectedChipValues(document.getElementById("color-chips")),
    city: document.getElementById("profile-city").value.trim()
  };
  if (writeStore(STORAGE_KEYS.profile, profile)) {
    showToast("Preferences saved — the matcher will use them.");
  }
}

function handleProfileReset() {
  applyProfileToForm(DEFAULT_PROFILE);
  writeStore(STORAGE_KEYS.profile, DEFAULT_PROFILE);
  showToast("Preferences cleared.");
}

function initProfile() {
  var styleChips = document.getElementById("style-chips");
  if (!styleChips) {
    return;
  }
  setupChipGroup(styleChips);
  setupChipGroup(document.getElementById("color-chips"));
  applyProfileToForm(readStore(STORAGE_KEYS.profile, DEFAULT_PROFILE));

  document.getElementById("profile-save").addEventListener("click", handleProfileSave);
  document.getElementById("profile-reset").addEventListener("click", handleProfileReset);
  // Pressing Enter in the city field should save, not reload the page.
  document.getElementById("profile-details").addEventListener("submit", function (event) {
    event.preventDefault();
    handleProfileSave();
  });
}

document.addEventListener("DOMContentLoaded", initProfile);
