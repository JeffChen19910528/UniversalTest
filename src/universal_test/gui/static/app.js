(function () {
  "use strict";

  const state = {
    lang: localStorage.getItem("ut_lang") || "zh",
    projectPath: "",
    openapiPath: "",
    baselinePath: "",
    databaseProfilePath: "",
    runId: null,
    result: null,
    usedBaseline: false,
    selectedPerfEndpoint: null, // {method, path} | null
    starting: false,
  };

  function t(key) {
    return (I18N[state.lang] && I18N[state.lang][key]) || key;
  }

  function applyI18n() {
    document.documentElement.lang = state.lang === "zh" ? "zh-Hant" : "en";
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      el.textContent = t(el.getAttribute("data-i18n"));
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      el.setAttribute("placeholder", t(el.getAttribute("data-i18n-placeholder")));
    });
    document.getElementById("lang-zh").classList.toggle("active", state.lang === "zh");
    document.getElementById("lang-en").classList.toggle("active", state.lang === "en");
  }

  function show(screenId) {
    ["screen-welcome", "screen-main", "screen-progress", "screen-results"].forEach((id) => {
      document.getElementById(id).classList.toggle("hidden", id !== screenId);
    });
  }

  async function api(method, path, body) {
    const res = await fetch(path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    return res.json();
  }

  // -- Welcome ---------------------------------------------------------
  document.getElementById("btn-start-welcome").addEventListener("click", () => {
    localStorage.setItem("ut_seen_welcome", "1");
    show("screen-main");
  });

  // -- Language ----------------------------------------------------------
  document.querySelectorAll(".lang-toggle button").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.lang = btn.getAttribute("data-lang");
      localStorage.setItem("ut_lang", state.lang);
      applyI18n();
    });
  });

  // -- Project folder ------------------------------------------------------
  document.getElementById("btn-pick-folder").addEventListener("click", async () => {
    const res = await api("POST", "/api/pick-folder");
    if (res.error === "folder_picker_unavailable") {
      showValidation(t("folder_picker_unavailable"), true);
      return;
    }
    if (!res.path) return;
    state.projectPath = res.path;
    document.getElementById("project-path").value = res.path;
    const validation = await api("POST", "/api/validate-project", { path: res.path });
    if (!validation.valid) {
      const key = validation.reason === "empty_directory" ? "invalid_folder_empty" : "invalid_folder_not_dir";
      showValidation(t(key), true);
    } else {
      hideValidation();
    }
    if (document.getElementById("chk-performance").checked) {
      loadPerfEndpoints();
    }
  });

  function showValidation(msg, warn) {
    const el = document.getElementById("project-validation");
    el.textContent = msg;
    el.classList.remove("hidden");
    el.classList.toggle("warn", !!warn);
  }
  function hideValidation() {
    document.getElementById("project-validation").classList.add("hidden");
  }

  function bindFilePicker(buttonId, targetInputId, stateKey, kind) {
    document.getElementById(buttonId).addEventListener("click", async () => {
      const res = await api("POST", "/api/pick-file", { kind: kind });
      if (!res.path) return;
      state[stateKey] = res.path;
      document.getElementById(targetInputId).value = res.path;
    });
  }
  bindFilePicker("btn-pick-openapi", "adv-openapi", "openapiPath", "openapi");
  bindFilePicker("btn-pick-baseline", "adv-baseline", "baselinePath", "baseline");
  bindFilePicker("btn-pick-database-profile", "database-profile-path", "databaseProfilePath", "database_profile");

  // -- Checkbox interactions ------------------------------------------------
  document.getElementById("chk-performance").addEventListener("change", (e) => {
    document.getElementById("perf-confirm-box").classList.toggle("hidden", !e.target.checked);
    if (!e.target.checked) {
      document.getElementById("chk-performance-confirm").checked = false;
      document.getElementById("perf-endpoint-section").classList.add("hidden");
      state.selectedPerfEndpoint = null;
    } else {
      loadPerfEndpoints();
    }
  });
  document.getElementById("chk-database").addEventListener("change", (e) => {
    document.getElementById("database-fields").classList.toggle("hidden", !e.target.checked);
  });

  // -- Authentication (Advanced Settings) ------------------------------------
  const AUTH_FIELD_GROUPS = {
    none: [],
    bearer: ["auth-fields-bearer"],
    api_key: ["auth-fields-apikey-env", "auth-fields-apikey-header"],
    basic: ["auth-fields-basic-user", "auth-fields-basic-pass"],
  };
  document.getElementById("auth-type").addEventListener("change", (e) => {
    const active = new Set(AUTH_FIELD_GROUPS[e.target.value] || []);
    document.querySelectorAll(".auth-fields").forEach((el) => {
      el.classList.toggle("hidden", !active.has(el.id));
    });
  });

  function authFieldsFromForm() {
    const authType = document.getElementById("auth-type").value;
    if (authType === "bearer") {
      return { bearer_token_env: document.getElementById("auth-bearer-env").value.trim() || null };
    }
    if (authType === "api_key") {
      return {
        api_key_env: document.getElementById("auth-apikey-env").value.trim() || null,
        api_key_header: document.getElementById("auth-apikey-header").value.trim() || null,
      };
    }
    if (authType === "basic") {
      return {
        basic_auth_user_env: document.getElementById("auth-basic-user-env").value.trim() || null,
        basic_auth_pass_env: document.getElementById("auth-basic-pass-env").value.trim() || null,
      };
    }
    return {};
  }

  // -- Performance endpoint selection ----------------------------------------
  async function loadPerfEndpoints() {
    const section = document.getElementById("perf-endpoint-section");
    const list = document.getElementById("perf-endpoint-list");
    const status = document.getElementById("perf-endpoint-status");
    state.selectedPerfEndpoint = null;
    list.innerHTML = "";
    status.classList.add("hidden");

    if (!state.projectPath) {
      section.classList.add("hidden");
      return;
    }
    section.classList.remove("hidden");
    const res = await api("POST", "/api/perf/endpoints", {
      project_path: state.projectPath, openapi_override: state.openapiPath || null,
    });
    if (res.reason) {
      status.textContent = t("perf_endpoint_reason_" + res.reason) || res.reason;
      status.classList.remove("hidden");
      return;
    }
    if (!res.endpoints || res.endpoints.length === 0) {
      status.textContent = t("perf_endpoint_reason_no_openapi_spec_found");
      status.classList.remove("hidden");
      return;
    }
    if (res.endpoints.length === 1) {
      state.selectedPerfEndpoint = res.endpoints[0];
      const only = res.endpoints[0];
      status.textContent = `${t("perf_endpoint_auto_selected")}: ${only.method} ${only.path}`;
      status.classList.remove("hidden");
      return;
    }
    res.endpoints.forEach((ep, i) => {
      const id = `perf-ep-${i}`;
      const row = document.createElement("div");
      row.className = "checkbox-row";
      row.innerHTML = `
        <input type="radio" name="perf-endpoint" id="${id}">
        <label for="${id}">${ep.method} ${escapeHtml(ep.path)}${ep.summary ? " — " + escapeHtml(ep.summary) : ""}</label>
      `;
      row.querySelector("input").addEventListener("change", () => {
        state.selectedPerfEndpoint = { method: ep.method, path: ep.path };
      });
      list.appendChild(row);
    });
  }

  // -- Start assessment ------------------------------------------------------
  document.getElementById("btn-start-assess").addEventListener("click", async () => {
    if (state.starting) return; // Final QA Known Issue I: block accidental double-clicks
    if (!state.projectPath) {
      showValidation(t("invalid_folder_empty_path"), true);
      return;
    }
    const startBtn = document.getElementById("btn-start-assess");
    state.starting = true;
    startBtn.disabled = true;
    try {
      const body = {
        project_path: state.projectPath,
        target: document.getElementById("target-url").value.trim() || null,
        run_functional: document.getElementById("chk-functional").checked,
        run_performance: document.getElementById("chk-performance").checked,
        performance_confirmed: document.getElementById("chk-performance-confirm").checked,
        run_database: document.getElementById("chk-database").checked,
        database_profile_path: state.databaseProfilePath || null,
        openapi_override: state.openapiPath || null,
        baseline_path: state.baselinePath || null,
        output_dir: document.getElementById("adv-output-dir").value.trim() || null,
        perf_profile: document.getElementById("adv-perf-profile").value,
        perf_endpoint: state.selectedPerfEndpoint ? state.selectedPerfEndpoint.path : null,
        perf_method: state.selectedPerfEndpoint ? state.selectedPerfEndpoint.method : null,
        timeout_seconds: parseFloat(document.getElementById("adv-timeout").value) || 10,
        ...authFieldsFromForm(),
      };
      state.usedBaseline = !!body.baseline_path;
      const started = await api("POST", "/api/assess", body);
      if (started.error) {
        const key = started.error === "assessment_already_running" ? "error_already_running" : null;
        showValidation((key && t(key)) || started.detail || t("error_generic"), true);
        return;
      }
      state.runId = started.run_id;
      startProgress();
    } finally {
      state.starting = false;
      startBtn.disabled = false;
    }
  });

  // -- Progress ------------------------------------------------------------
  const BASE_STAGE_ORDER = [
    "project_scan", "functional_test", "performance_test", "database_assessment", "assessment", "report_generation",
  ];

  function currentStageOrder() {
    // Regression only ever executes when a baseline was supplied for this
    // run (Final QA Known Issue D) -- mirrors `application/service.py`'s
    // `if request.baseline_path:` gate exactly, so the progress checklist
    // never shows a stage that cannot possibly run.
    if (!state.usedBaseline) return BASE_STAGE_ORDER;
    const order = BASE_STAGE_ORDER.slice();
    order.splice(order.indexOf("assessment") + 1, 0, "regression");
    return order;
  }

  function renderProgressList(statusByStage) {
    const stageOrder = currentStageOrder();
    const list = document.getElementById("progress-list");
    list.innerHTML = "";
    let doneCount = 0;
    stageOrder.forEach((stage) => {
      const status = statusByStage[stage] || "pending";
      const li = document.createElement("li");
      let dot = "○"; // ○ pending
      if (status === "started") { dot = "●"; li.className = "active"; } // ●
      else if (status === "completed") { dot = "✓"; li.className = "done"; doneCount++; } // ✓
      else if (status === "skipped") { dot = "○"; doneCount++; }
      else if (status === "failed") { dot = "✗"; li.className = "done"; doneCount++; }
      li.innerHTML = `<span class="dot">${dot}</span><span>${t("stage_" + stage)}</span>`;
      list.appendChild(li);
    });
    document.getElementById("progress-counter").textContent = `${doneCount} / ${stageOrder.length}`;
  }

  function startProgress() {
    show("screen-progress");
    const statusByStage = {};
    renderProgressList(statusByStage);

    const source = new EventSource(`/api/assess/${state.runId}/stream`);
    source.onmessage = (evt) => {
      const payload = JSON.parse(evt.data);
      if (payload.name === "done") {
        source.close();
        fetchResult();
        return;
      }
      if (payload.stage && payload.phase) {
        statusByStage[payload.stage] = payload.phase;
        renderProgressList(statusByStage);
      }
    };
    source.onerror = () => {
      // The browser's EventSource auto-retries; final state always arrives via
      // /result once the run thread finishes, so no explicit handling is needed.
    };
  }

  async function fetchResult() {
    const res = await api("GET", `/api/assess/${state.runId}/result`);
    if (res.status === "error") {
      renderFatalError(res.error, res.error_id);
      return;
    }
    state.result = res.result;
    renderResults(res.result);
  }

  function renderFatalError(message, errorId) {
    // The server never sends a raw traceback or exception text here (Final
    // QA Known Issue E) -- only a human-readable message plus an opaque
    // error_id a user can quote when asking for help or checking logs.
    show("screen-results");
    const idLine = errorId
      ? `<p class="field-hint">${t("error_id_label")}: <code>${escapeHtml(errorId)}</code></p>`
      : "";
    document.getElementById("overall-status").innerHTML =
      `<div class="status-badge fail">${STATUS_ICON.fail} ${escapeHtml(message || t("error_generic"))}</div>${idLine}
       <p class="field-hint">${t("error_see_logs_hint")}</p>`;
    document.getElementById("quality-gate-card").classList.add("hidden");
    document.getElementById("regression-card").classList.add("hidden");
    document.getElementById("category-grid").innerHTML = "";
    document.getElementById("findings-list").innerHTML = "";
    document.getElementById("unassessed-list").innerHTML = "";
  }

  // -- Results ---------------------------------------------------------------
  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function statusBadge(status) {
    return `<span class="status-badge ${status}">${STATUS_ICON[status] || ""} ${t("status_" + status)}</span>`;
  }

  // Backend category names are stable English strings (skill.md: internal
  // values stay English/machine-readable); this is presentation-only, never
  // fed back into any request (Final QA Known Issue J).
  function categoryLabel(name) {
    const key = "category_" + name;
    const translated = t(key);
    return translated === key ? name : translated;
  }

  function renderQualityGate(qualityGate) {
    // Renders the backend's already-evaluated Quality Gate result as-is
    // (Final QA Known Issue C) -- the frontend never re-derives pass/fail
    // from the assessment/regression data itself.
    const body = document.getElementById("quality-gate-body");
    if (!qualityGate) {
      body.innerHTML = `<p class="field-hint">-</p>`;
      return;
    }
    let html = statusBadge(qualityGate.status);
    if (qualityGate.reason) {
      html += `<p><strong>${t("quality_gate_reason_label")}:</strong> ${escapeHtml(qualityGate.reason)}</p>`;
    }
    if (qualityGate.findings && qualityGate.findings.length > 0) {
      html += qualityGate.findings.map((f) => `
        <div class="finding ${f.level}">
          <h4>${escapeHtml(f.title)}</h4>
          <p>${escapeHtml(f.description)}</p>
        </div>
      `).join("");
    }
    body.innerHTML = html;
  }

  function renderRegression(regression) {
    // Renders the backend's already-computed regression comparison (Final
    // QA Known Issue B) -- no regression math happens in this file.
    const card = document.getElementById("regression-card");
    const body = document.getElementById("regression-body");
    if (!regression) {
      card.classList.add("hidden");
      return;
    }
    card.classList.remove("hidden");
    let html = statusBadge(regression.status);
    const notable = regression.findings.filter((f) => f.change === "regressed" || f.change === "improved");
    if (notable.length === 0) {
      html += `<p class="field-hint">${t("regression_no_changes")}</p>`;
    } else {
      html += notable.map((f) => `
        <div class="finding ${f.change === "regressed" ? "fail" : "pass"}">
          <h4>${escapeHtml(f.title)}</h4>
          <p>${escapeHtml(f.description)}</p>
        </div>
      `).join("");
    }
    body.innerHTML = html;
  }

  function renderResults(result) {
    show("screen-results");
    document.getElementById("quality-gate-card").classList.remove("hidden");
    const assessment = result.assessment;

    document.getElementById("overall-status").innerHTML = statusBadge(assessment.overall_status);
    renderQualityGate(result.quality_gate);
    renderRegression(result.regression);

    const grid = document.getElementById("category-grid");
    grid.innerHTML = "";
    assessment.categories.forEach((cat) => {
      const div = document.createElement("div");
      div.className = "category-card";
      div.innerHTML = `${statusBadge(cat.status)}<h3>${escapeHtml(categoryLabel(cat.name))}</h3><p>${escapeHtml(cat.summary || cat.reason || "")}</p>`;
      div.addEventListener("click", () => {
        document.getElementById("findings-card").scrollIntoView({ behavior: "smooth" });
      });
      grid.appendChild(div);
    });

    const unassessedList = document.getElementById("unassessed-list");
    unassessedList.innerHTML = "";
    if (assessment.unassessed.length === 0) {
      document.getElementById("unassessed-card").classList.add("hidden");
    } else {
      document.getElementById("unassessed-card").classList.remove("hidden");
      assessment.unassessed.forEach((u) => {
        const div = document.createElement("div");
        div.className = "unassessed-item";
        div.textContent = `${u.name} — ${u.reason}`;
        unassessedList.appendChild(div);
      });
    }

    const findingsList = document.getElementById("findings-list");
    findingsList.innerHTML = "";
    const notable = assessment.findings.filter((f) => f.status === "fail" || f.status === "warning");
    if (notable.length === 0) {
      const p = document.createElement("p");
      p.className = "field-hint";
      p.textContent = "-";
      findingsList.appendChild(p);
    }
    notable.forEach((f) => {
      const div = document.createElement("div");
      div.className = `finding ${f.status}`;
      const techId = `tech-${f.id}`;
      div.innerHTML = `
        ${statusBadge(f.status)}
        <h4>${escapeHtml(f.title)}</h4>
        <p>${escapeHtml(f.description)}</p>
        ${f.recommendation ? `<p class="recommendation"><strong>${state.lang === "zh" ? "建議" : "Recommendation"}:</strong> ${escapeHtml(f.recommendation)}</p>` : ""}
        <button class="tech-toggle" data-target="${techId}">${t("view_technical_details")}</button>
        <pre class="tech-detail hidden" id="${techId}">${escapeHtml(JSON.stringify({ evidence: f.evidence, severity: f.severity, confidence: f.confidence }, null, 2))}</pre>
      `;
      findingsList.appendChild(div);
    });
    findingsList.querySelectorAll(".tech-toggle").forEach((btn) => {
      btn.addEventListener("click", () => {
        const pre = document.getElementById(btn.getAttribute("data-target"));
        const hidden = pre.classList.toggle("hidden");
        btn.textContent = hidden ? t("view_technical_details") : t("hide_technical_details");
      });
    });
  }

  // -- Report actions ----------------------------------------------------
  function bindOpenReport(buttonId, format) {
    document.getElementById(buttonId).addEventListener("click", async () => {
      await api("POST", "/api/open/report", { run_id: state.runId, format: format });
    });
  }
  bindOpenReport("btn-open-html", "html");
  bindOpenReport("btn-open-json", "json");
  bindOpenReport("btn-open-md", "markdown");
  document.getElementById("btn-open-folder").addEventListener("click", async () => {
    await api("POST", "/api/open/folder", { run_id: state.runId });
  });

  document.getElementById("btn-new-assessment").addEventListener("click", () => {
    state.runId = null;
    state.result = null;
    show("screen-main");
  });

  // -- Init ---------------------------------------------------------------
  applyI18n();
  if (localStorage.getItem("ut_seen_welcome")) {
    show("screen-main");
  } else {
    show("screen-welcome");
  }
})();
