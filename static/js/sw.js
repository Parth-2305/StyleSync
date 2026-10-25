// Service worker: a tiny program the browser keeps alive in the background.
// When our server pushes a message it wakes up, even if StyleSync is closed, and shows a notification.

// Take over at once when this file changes, so an updated version works without closing every tab.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (error) {
    data = { body: event.data ? event.data.text() : "" };
  }
  event.waitUntil(
    Promise.all([
      self.registration.showNotification(data.title || "StyleSync", {
        body: data.body || "",
        icon: "/static/images/favicon.png",
        badge: "/static/images/favicon.png",
        data: { url: data.url || "/dashboard" },
      }),
      // Tell any open StyleSync page, so its bell updates at once instead of waiting for the next check.
      self.clients.matchAll({ type: "window" }).then((pages) => pages.forEach((page) => page.postMessage({ type: "push" }))),
    ])
  );
});

// Clicking the notification opens (or focuses) the page it points to. Only OUR own pages are ever opened.
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL(event.notification.data.url, self.location.origin);
  if (target.origin !== self.location.origin) return;
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      for (const win of windows) {
        if (new URL(win.url).origin === self.location.origin && "focus" in win) {
          win.navigate(target.href);
          return win.focus();
        }
      }
      return clients.openWindow(target.href);
    })
  );
});
