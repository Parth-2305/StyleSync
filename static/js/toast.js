// Small in-app messages that replace browser alert() popups.
// Other pages can call showToast("Saved") after a form action.
// A message stays 7 seconds (9 for a problem), pauses while the mouse is on it, and has a close button.

function showToast(message, type) {
  var wrap = document.querySelector(".toast-wrap");
  if (!wrap) {
    wrap = document.createElement("div");
    wrap.className = "toast-wrap";
    wrap.setAttribute("aria-live", "polite");
    document.body.appendChild(wrap);
  }

  var toast = document.createElement("div");
  toast.className = type === "alert" ? "app-toast is-alert" : "app-toast";
  toast.setAttribute("role", type === "alert" ? "alert" : "status");

  var text = document.createElement("span");
  text.className = "toast-text";
  text.textContent = message; // textContent, never HTML: a piece's name can't inject anything here

  var close = document.createElement("button");
  close.type = "button";
  close.className = "toast-close";
  close.setAttribute("aria-label", "Dismiss message");
  close.innerHTML = '<i class="bi bi-x-lg" aria-hidden="true"></i>'; // a fixed icon, no user text

  toast.appendChild(text);
  toast.appendChild(close);
  wrap.appendChild(toast);

  var remaining = type === "alert" ? 9000 : 7000; // milliseconds left before it disappears
  var startedAt = 0;
  var timer = null;

  function dismiss() {
    window.clearTimeout(timer);
    toast.remove();
  }
  function startTimer() {
    startedAt = Date.now();
    timer = window.setTimeout(dismiss, remaining);
  }
  function pauseTimer() { // while you are reading it (mouse over, or keyboard focus), the clock stops
    window.clearTimeout(timer);
    remaining = Math.max(remaining - (Date.now() - startedAt), 2500);
  }

  close.addEventListener("click", dismiss);
  toast.addEventListener("mouseenter", pauseTimer);
  toast.addEventListener("mouseleave", startTimer);
  toast.addEventListener("focusin", pauseTimer);
  toast.addEventListener("focusout", startTimer);
  startTimer();
}
