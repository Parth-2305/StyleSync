// Dashboard: shows today's date in the greeting. (The numbers and cards are drawn by the server.)

document.addEventListener("DOMContentLoaded", () => {
  const date = document.getElementById("greeting-date");
  if (date) {
    date.textContent = new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
  }
});
