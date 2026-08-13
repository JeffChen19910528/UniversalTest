// Deterministic, local-only fixture credential check -- fixture data only,
// never a real authentication system (used by Phase 11 scenario tests).
document.getElementById("login-button").addEventListener("click", function () {
  var username = document.getElementById("username").value;
  var password = document.getElementById("password").value;
  if (username === "demo" && password === "demo123") {
    window.location.href = "dashboard.html";
  } else {
    document.getElementById("login-error").style.display = "block";
  }
});
