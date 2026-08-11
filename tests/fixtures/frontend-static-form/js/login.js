document.querySelector("form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const token = sessionStorage.getItem("token");
  await fetch("/login", { method: "POST", headers: { Authorization: `Bearer ${token}` } });
});
