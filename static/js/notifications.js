// Notification bell: unread badge, dropdown list, and browser push registration (Web Push).
// Wrapped in (() => { ... })() so its names can never clash with other scripts on the page.
(() => {
  const POLL_MS = 15000; // ask the server every 15 seconds (a push makes the bell update at once, see below)
  const el = (id) => document.getElementById(id);
  const bell = el("bell-btn");
  if (!bell) return;

  let lastUnread = null; // null until the first answer, so we don't announce old notifications as "new"
  let isOpen = false;

  function timeAgo(iso) {
    const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
    if (seconds < 60) return "just now";
    if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)} h ago`;
    return `${Math.floor(seconds / 86400)} d ago`;
  }

  const ICONS = { scan: "bi-check2-circle", unknown_tag: "bi-question-circle", nudge: "bi-hourglass-split", info: "bi-info-circle" };

  function render(data) {
    const badge = el("bell-badge");
    badge.hidden = data.unread === 0;
    badge.textContent = data.unread > 99 ? "99+" : data.unread;
    el("bell-list").innerHTML = data.items.length
      ? data.items.map((n) => {
          const inner = `<i class="bi ${ICONS[n.kind] || ICONS.info}" aria-hidden="true"></i><span><span class="bell-msg">${escapeHtml(n.message)}</span><small>${timeAgo(n.created_at)}</small></span>`;
          const cls = n.is_read ? "bell-item" : "bell-item is-unread";
          return `<li>${n.link ? `<a class="${cls}" href="${escapeHtml(n.link)}">${inner}</a>` : `<div class="${cls}">${inner}</div>`}</li>`;
        }).join("")
      : '<li class="bell-empty">You\'re all caught up.</li>';
    el("bell-foot").hidden = !(data.push && "serviceWorker" in navigator && "PushManager" in window);
  }

  async function poll() {
    const { ok, data } = await api("GET", "/api/notifications");
    if (!ok) return;
    if (lastUnread !== null && data.unread > lastUnread && !isOpen) {
      const newest = data.items.find((n) => !n.is_read);
      if (newest) showToast(newest.message); // a new one arrived while the page is open
    }
    lastUnread = data.unread;
    render(data);
  }

  async function togglePanel(forceClose) {
    isOpen = forceClose ? false : !isOpen;
    el("bell-panel").hidden = !isOpen;
    bell.setAttribute("aria-expanded", String(isOpen));
    if (!isOpen) return;
    await poll(); // fresh list, still showing which ones were unread
    refreshPushButton();
    await api("POST", "/api/notifications/read", {}); // opening the bell = "seen"
    lastUnread = 0;
    el("bell-badge").hidden = true;
  }

  // ---------------------------------------------------------------- browser push
  const base64ToBytes = (b64) => {
    const raw = atob((b64 + "=".repeat((4 - (b64.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/"));
    return Uint8Array.from(raw, (c) => c.charCodeAt(0));
  };

  async function currentSubscription() {
    const reg = await navigator.serviceWorker.getRegistration("/");
    return reg ? reg.pushManager.getSubscription() : null;
  }

  async function refreshPushButton() {
    if (el("bell-foot").hidden) return;
    const subscribed = !!(await currentSubscription());
    el("push-label").textContent = subscribed ? "Turn off browser notifications" : "Turn on browser notifications";
  }

  async function togglePush() {
    const existing = await currentSubscription();
    if (existing) {
      await api("POST", "/api/push/unsubscribe", { endpoint: existing.endpoint });
      await existing.unsubscribe();
      showToast("Browser notifications are off.");
      return refreshPushButton();
    }
    if ((await Notification.requestPermission()) !== "granted") {
      return showToast("Notifications are blocked. Allow them in your browser's site settings.", "alert");
    }
    try {
      const registration = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
      await navigator.serviceWorker.ready;
      const { data: key } = await api("GET", "/api/push/key");
      const subscription = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: base64ToBytes(key.public_key) });
      const { ok, data } = await api("POST", "/api/push/subscribe", subscription.toJSON());
      if (!ok) { await subscription.unsubscribe(); return showToast(data.error || "Couldn't turn notifications on.", "alert"); }
      showToast("Browser notifications are on.");
    } catch (error) {
      showToast("This browser couldn't turn notifications on.", "alert");
    }
    refreshPushButton();
  }

  bell.addEventListener("click", () => togglePanel());
  el("bell-read-all").addEventListener("click", async () => { await api("POST", "/api/notifications/read", {}); poll(); });
  el("push-btn").addEventListener("click", togglePush);
  document.addEventListener("click", (e) => { if (isOpen && !e.target.closest(".bell-wrap")) togglePanel(true); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && isOpen) togglePanel(true); });

  poll();
  setInterval(poll, POLL_MS);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) poll(); }); // coming back to the tab: refresh now
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.addEventListener("message", (e) => { if (e.data && e.data.type === "push") poll(); }); // a push just arrived
  }
})();
