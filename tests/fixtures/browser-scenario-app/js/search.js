// Deterministic, local-only fixture search data -- no network, no external
// service (used by Phase 11 scenario tests).
document.getElementById("search-button").addEventListener("click", function () {
  var query = document.getElementById("query").value.toLowerCase();
  var data = {
    widget: ["Widget A", "Widget B", "Widget C"],
    gadget: ["Gadget X"],
  };
  var results = data[query] || [];
  document.getElementById("result-count").textContent = results.length + " results found";
  var list = document.getElementById("results");
  list.innerHTML = "";
  results.forEach(function (name) {
    var item = document.createElement("li");
    item.textContent = name;
    list.appendChild(item);
  });
});
