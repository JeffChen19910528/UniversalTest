async function loadUsers() {
  const res = await fetch("/api/users");
  const users = await res.json();
  document.getElementById("users").textContent = JSON.stringify(users);
}

const socket = new WebSocket("wss://example.invalid/updates");
loadUsers();
