// Landing (auth) page: Log in / Sign up tabs plus client-side validation.
// The forms post to /auth/login and /auth/signup. These checks are only for instant
// feedback; the server re-checks everything (validators.py) because it can't trust the browser.

var EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function selectAuthTab(tabId) {
  document.querySelectorAll(".auth-tab").forEach(function (tab) {
    var isSelected = tab.id === tabId;
    tab.setAttribute("aria-selected", isSelected ? "true" : "false");
    tab.tabIndex = isSelected ? 0 : -1;
    document.getElementById(tab.getAttribute("aria-controls")).hidden = !isSelected;
  });
}

// Left/right arrow keys move between tabs, per the WAI-ARIA tabs pattern.
function handleTabKeydown(event) {
  if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") {
    return;
  }
  var tabs = Array.prototype.slice.call(document.querySelectorAll(".auth-tab"));
  var index = tabs.indexOf(event.currentTarget);
  var next = tabs[(index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length];
  selectAuthTab(next.id);
  next.focus();
}

function isFieldValid(field) {
  var value = field.value.trim();
  if (field.type === "email") {
    return EMAIL_PATTERN.test(value);
  }
  if (field.id === "signup-password") {
    return value.length >= 8 && /[A-Za-z]/.test(value) && /\d/.test(value);
  }
  return value.length > 0;
}

async function handleAuthSubmit(event) {
  event.preventDefault();
  var form = event.currentTarget;
  var firstInvalid = null;

  form.querySelectorAll(".form-input").forEach(function (field) {
    if (isFieldValid(field)) {
      clearFieldError(field);
    } else {
      showFieldError(field);
      firstInvalid = firstInvalid || field;
    }
  });

  if (firstInvalid) {
    firstInvalid.focus();
    return;
  }

  var submit = form.querySelector('[type="submit"]');
  var label = submit.innerHTML;
  submit.disabled = true;
  submit.textContent = form.id === "panel-signup" ? "Creating your closet…" : "Logging in…";

  var body = {};
  new FormData(form).forEach(function (value, key) { body[key] = value; });
  var result = await api("POST", form.getAttribute("data-endpoint"), body);

  if (result.ok && result.data.redirect) {
    window.location.href = result.data.redirect;
    return;
  }
  submit.disabled = false;
  submit.innerHTML = label;
  showToast(result.data.error || "Something went wrong. Please try again.", "alert");
}


function initLanding() {
  document.querySelectorAll(".auth-tab").forEach(function (tab) {
    tab.addEventListener("click", function () { selectAuthTab(tab.id); });
    tab.addEventListener("keydown", handleTabKeydown);
  });

  document.querySelectorAll("[data-switch-tab]").forEach(function (button) {
    button.addEventListener("click", function () {
      var tabId = button.getAttribute("data-switch-tab");
      selectAuthTab(tabId);
      document.getElementById(tabId).focus();
    });
  });

  document.querySelectorAll(".auth-form").forEach(function (form) {
    form.addEventListener("submit", handleAuthSubmit);
    form.querySelectorAll(".form-input").forEach(function (field) {
      field.addEventListener("input", function () { clearFieldError(field); });
    });
  });
}

document.addEventListener("DOMContentLoaded", initLanding);
