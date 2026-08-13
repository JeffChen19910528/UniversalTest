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
    // A previously analyzed Web Assessment plan describes the *old* project --
    // showing it against a newly picked folder would mislead a non-programmer
    // into starting a run based on stale detection info (Phase 10 UX review).
    document.getElementById("web-assess-plan").classList.add("hidden");
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
  document.getElementById("chk-browser").addEventListener("change", (e) => {
    document.getElementById("browser-confirm-box").classList.toggle("hidden", !e.target.checked);
    if (!e.target.checked) {
      document.getElementById("chk-browser-confirm").checked = false;
    }
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
  // Shared by both entry points (Full Assessment form and the guided Web
  // Assessment card) so there is exactly one place that calls `/api/assess`
  // and exactly one run-tracking/progress/results flow (spec section 4/22/41)
  // -- the two forms only differ in how `body` gets built.
  async function startAssessmentRun(body, startBtn) {
    if (state.starting) return; // Final QA Known Issue I: block accidental double-clicks
    if (!state.projectPath) {
      showValidation(t("invalid_folder_empty_path"), true);
      return;
    }
    state.starting = true;
    if (startBtn) startBtn.disabled = true;
    try {
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
      if (startBtn) startBtn.disabled = false;
    }
  }

  document.getElementById("btn-start-assess").addEventListener("click", () => {
    const startBtn = document.getElementById("btn-start-assess");
    const body = {
      project_path: state.projectPath,
      target: document.getElementById("target-url").value.trim() || null,
      run_functional: document.getElementById("chk-functional").checked,
      run_performance: document.getElementById("chk-performance").checked,
      performance_confirmed: document.getElementById("chk-performance-confirm").checked,
      run_database: document.getElementById("chk-database").checked,
      database_profile_path: state.databaseProfilePath || null,
      run_browser: document.getElementById("chk-browser").checked,
      browser_confirmed: document.getElementById("chk-browser-confirm").checked,
      browser_target: document.getElementById("target-url").value.trim() || null,
      browser_allow_external: document.getElementById("chk-browser-allow-external").checked,
      browser_screenshots: document.getElementById("chk-browser-screenshots").checked,
      openapi_override: state.openapiPath || null,
      baseline_path: state.baselinePath || null,
      output_dir: document.getElementById("adv-output-dir").value.trim() || null,
      perf_profile: document.getElementById("adv-perf-profile").value,
      perf_endpoint: state.selectedPerfEndpoint ? state.selectedPerfEndpoint.path : null,
      perf_method: state.selectedPerfEndpoint ? state.selectedPerfEndpoint.method : null,
      timeout_seconds: parseFloat(document.getElementById("adv-timeout").value) || 10,
      ...authFieldsFromForm(),
    };
    startAssessmentRun(body, startBtn);
  });

  // -- Web Assessment: guided one-click workflow (Phase 10) -------------------
  // Local-only heuristic, presentation purposes only (deciding whether to show
  // the external-target warning box) -- the backend's `target_policy.py` is
  // still the sole safety authority regardless of what this shows (spec
  // section 15/16: "The GUI confirmation is additional UX protection, not
  // the security boundary").
  function looksLikeLocalTarget(target) {
    if (!target) return true;
    return /^(https?:\/\/(localhost|127\.0\.0\.1|\[::1\])(:\d+)?\/?|file:\/\/)/i.test(target.trim());
  }

  function updateWebAssessStartState() {
    const target = document.getElementById("web-target-url").value.trim();
    const confirmed = document.getElementById("chk-web-confirm").checked;
    const allowExternal = document.getElementById("chk-web-allow-external").checked;
    const isExternal = target && !looksLikeLocalTarget(target);
    document.getElementById("web-external-warning").classList.toggle("hidden", !isExternal);
    if (isExternal) {
      document.getElementById("web-external-warning-target").textContent = target;
    }
    const startBtn = document.getElementById("btn-start-web-assess");
    const hint = document.getElementById("web-assess-start-hint");
    if (!target) {
      // Spec section 9/14: a project with no web target is not a failure --
      // static analysis alone is still a complete, valid Web Assessment.
      startBtn.disabled = false;
      hint.classList.remove("hidden");
    } else if (isExternal && !allowExternal) {
      startBtn.disabled = true;
      hint.classList.add("hidden");
    } else if (!confirmed) {
      startBtn.disabled = true;
      hint.classList.add("hidden");
    } else {
      startBtn.disabled = false;
      hint.classList.add("hidden");
    }
  }

  ["web-target-url"].forEach((id) => {
    document.getElementById(id).addEventListener("input", updateWebAssessStartState);
  });
  ["chk-web-confirm", "chk-web-allow-external"].forEach((id) => {
    document.getElementById(id).addEventListener("change", updateWebAssessStartState);
  });

  function renderWebAssessmentPlan(data) {
    const detected = document.getElementById("web-assess-detected");
    const notWeb = document.getElementById("web-assess-not-web");
    const checks = document.getElementById("web-assess-checks");

    if (!data.detected) {
      detected.innerHTML = "";
      notWeb.classList.remove("hidden");
      checks.classList.add("hidden");
      return;
    }
    notWeb.classList.add("hidden");
    checks.classList.remove("hidden");

    const fe = data.frontend || {};
    const typeLabel = t("web_type_" + (fe.frontend_type || "unknown_web"));
    const bits = [`<strong>${t("web_assess_detected_label")}:</strong> ${escapeHtml(typeLabel)}`];
    if (fe.entry_points && fe.entry_points.length) {
      bits.push(`${t("web_assess_entry_point_label")}: ${escapeHtml(fe.entry_points.join(", "))}`);
    }
    if (data.frameworks && data.frameworks.length) {
      bits.push(`${t("web_assess_framework_label")}: ${escapeHtml(data.frameworks.join(", "))}`);
    }
    if (fe.browser_apis && fe.browser_apis.length) {
      bits.push(`${t("web_assess_browser_apis_label")}: ${escapeHtml(fe.browser_apis.join(", "))}`);
    }
    detected.innerHTML = `<div class="notice">${bits.join("<br>")}</div>`;

    const plannedList = document.getElementById("web-assess-planned-list");
    plannedList.innerHTML = [
      "web_check_structure", "web_check_static_analysis", "web_check_browser_smoke",
      "web_check_console_errors",
    ].map((k) => `<li>${t(k)}</li>`).join("");

    const notIncludedList = document.getElementById("web-assess-not-included-list");
    notIncludedList.innerHTML = [
      "web_not_included_login", "web_not_included_permissions", "web_not_included_visual",
      "web_not_included_security", "web_not_included_accessibility",
    ].map((k) => `<li>${t(k)}</li>`).join("");
  }

  document.getElementById("btn-analyze-web").addEventListener("click", async () => {
    if (!state.projectPath) {
      showValidation(t("invalid_folder_empty_path"), true);
      return;
    }
    const res = await api("POST", "/api/web/detect", { project_path: state.projectPath });
    if (res.error) {
      showValidation(res.detail || t("error_generic"), true);
      return;
    }
    document.getElementById("web-assess-plan").classList.remove("hidden");
    renderWebAssessmentPlan(res);
    updateWebAssessStartState();
  });

  document.getElementById("btn-start-web-assess").addEventListener("click", () => {
    const startBtn = document.getElementById("btn-start-web-assess");
    const target = document.getElementById("web-target-url").value.trim() || null;
    const body = {
      project_path: state.projectPath,
      target: target,
      run_functional: true,
      run_performance: false,
      run_database: false,
      run_browser: !!target,
      browser_confirmed: document.getElementById("chk-web-confirm").checked,
      browser_target: target,
      browser_allow_external: document.getElementById("chk-web-allow-external").checked,
      browser_screenshots: document.getElementById("chk-web-screenshots").checked,
      output_dir: null,
    };
    startAssessmentRun(body, startBtn);
  });

  // -- Web Scenarios: explicit, repeatable multi-step workflows (Phase 11) ---
  const scenarioState = { collection: null, selected: null, running: false };

  function describeScenarioStepClientSide(step) {
    // Presentation-only formatting of already-safe, backend-provided data
    // (spec section 35: value_env-sourced values are never sent by the
    // backend in the first place) -- never re-derives a verdict, never
    // resolves a secret, just lays out the fields the same way the CLI's
    // `describe_step()` does.
    const sel = step.selector ? (step.selector.type === "role"
      ? `role=${step.selector.role} name='${step.selector.value}'`
      : `${step.selector.type}='${step.selector.value}'`) : "";
    if (step.action && step.action.indexOf("assert_") === 0) {
      return `${t("scenarios_assert_label")} ${step.action.slice(7)}: ${sel || step.value || ""}`;
    }
    if (step.action === "navigate") {
      return `${t("scenarios_navigate_label")} ${step.url || step.value || ""}`;
    }
    if (step.value_env) {
      return `${step.action} ${sel} (${t("scenarios_from_env_label")}: ${step.value_env})`;
    }
    return `${step.action} ${sel} ${step.value || ""}`.trim();
  }

  function renderScenarioList(collection) {
    const list = document.getElementById("scenarios-list");
    const none = document.getElementById("scenarios-none");
    if (!collection.scenarios || collection.scenarios.length === 0) {
      list.classList.add("hidden");
      none.classList.remove("hidden");
      return;
    }
    none.classList.add("hidden");
    list.classList.remove("hidden");
    list.innerHTML = "";
    collection.scenarios.forEach((scenario) => {
      const row = document.createElement("div");
      row.className = "checkbox-row";
      row.innerHTML = `<input type="radio" name="scenario-select" id="scn-${escapeHtml(scenario.id)}">
        <label for="scn-${escapeHtml(scenario.id)}"><strong>${escapeHtml(scenario.name)}</strong> (${escapeHtml(scenario.id)})</label>`;
      row.querySelector("input").addEventListener("change", () => selectScenario(scenario));
      list.appendChild(row);
    });
  }

  function selectScenario(scenario) {
    scenarioState.selected = scenario;
    document.getElementById("scenario-detail").classList.remove("hidden");
    document.getElementById("scenario-detail-name").textContent = scenario.name;
    document.getElementById("scenario-detail-description").textContent = scenario.description || "";
    const stepsList = document.getElementById("scenario-detail-steps");
    stepsList.innerHTML = (scenario.steps || [])
      .map((s) => `<li>${escapeHtml(describeScenarioStepClientSide(s))}</li>`).join("");
    document.getElementById("scenario-plan").classList.add("hidden");
    document.getElementById("scenario-result").classList.add("hidden");
    updateScenarioRunState();
  }

  function updateScenarioRunState() {
    const target = document.getElementById("scenario-target-url").value.trim();
    const confirmed = document.getElementById("chk-scenario-confirm").checked;
    const allowExternal = document.getElementById("chk-scenario-allow-external").checked;
    const isExternal = target && !looksLikeLocalTarget(target);
    document.getElementById("scenario-external-warning").classList.toggle("hidden", !isExternal);
    const runBtn = document.getElementById("btn-run-scenario");
    runBtn.disabled = !target || !confirmed || (isExternal && !allowExternal);
  }

  ["scenario-target-url"].forEach((id) => {
    document.getElementById(id).addEventListener("input", updateScenarioRunState);
  });
  ["chk-scenario-confirm", "chk-scenario-allow-external"].forEach((id) => {
    document.getElementById(id).addEventListener("change", updateScenarioRunState);
  });

  document.getElementById("btn-list-scenarios").addEventListener("click", async () => {
    if (!state.projectPath) {
      showValidation(t("invalid_folder_empty_path"), true);
      return;
    }
    const res = await api("POST", "/api/web/scenarios", { project_path: state.projectPath });
    if (res.error) {
      showValidation(res.detail || t("error_generic"), true);
      return;
    }
    scenarioState.collection = res;
    renderScenarioList(res);
  });

  document.getElementById("btn-dry-run-scenario").addEventListener("click", () => {
    if (!scenarioState.selected) return;
    const plan = document.getElementById("scenario-plan");
    plan.classList.remove("hidden");
    plan.innerHTML = `<div class="notice">${t("scenarios_dry_run_notice")}</div>`;
  });

  document.getElementById("btn-run-scenario").addEventListener("click", async () => {
    if (!scenarioState.selected || scenarioState.running) return;
    const runBtn = document.getElementById("btn-run-scenario");
    scenarioState.running = true;
    runBtn.disabled = true;
    const resultBox = document.getElementById("scenario-result");
    resultBox.classList.remove("hidden");
    resultBox.innerHTML = `<p class="field-hint">${t("scenarios_running")}</p>`;
    try {
      const res = await api("POST", "/api/web/scenario/run", {
        project_path: state.projectPath,
        scenario_id: scenarioState.selected.id,
        target: document.getElementById("scenario-target-url").value.trim(),
        allow_external: document.getElementById("chk-scenario-allow-external").checked,
        confirmed: document.getElementById("chk-scenario-confirm").checked,
      });
      if (res.error) {
        resultBox.innerHTML = `<div class="notice warn">${escapeHtml(res.detail || res.error)}</div>`;
        return;
      }
      renderScenarioResult(res.result, resultBox);
    } finally {
      scenarioState.running = false;
      updateScenarioRunState();
    }
  });

  function renderScenarioResult(result, container) {
    if (result.status === "not_assessed") {
      container.innerHTML = `${statusBadge("not_assessed")}<p>${escapeHtml(result.not_assessed_reason || "")}</p>`;
      return;
    }
    const stepRows = (result.steps || []).map((s) => {
      const badgeClass = { passed: "pass", failed: "fail", error: "error", skipped: "unknown" }[s.status] || "unknown";
      return `<li>${statusBadge(badgeClass)} ${escapeHtml(s.step_id)} (${escapeHtml(s.action)}) - ${escapeHtml(s.message)}</li>`;
    }).join("");
    container.innerHTML = `
      ${statusBadge(result.status)}
      <p>${result.passed_steps} / ${result.step_count} ${t("scenarios_steps_passed_label")}</p>
      <ul>${stepRows}</ul>
    `;
  }

  // -- Progress ------------------------------------------------------------
  const BASE_STAGE_ORDER = [
    "project_scan", "functional_test", "performance_test", "database_assessment", "browser_test", "assessment", "report_generation",
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
    if (qualityGate.status === "pass") {
      html += `<p class="field-hint">${t("quality_gate_clarify_pass")}</p>`;
    } else if (qualityGate.status === "fail") {
      html += `<p class="field-hint">${t("quality_gate_clarify_fail")}</p>`;
    }
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

  function renderAssessmentSummary(assessment) {
    // Application Health / Testability / Assessment Coverage are three
    // distinct dimensions (brief §10/§11/§29) - a WARNING category (e.g.
    // "no test framework detected") must not read the same as an actual
    // application defect. This renders alongside, never replacing, the
    // full category grid below.
    const testabilityCat = assessment.categories.find((c) => c.name === "Testability");
    const browserCat = assessment.categories.find((c) => c.name === "Browser Testing");
    const body = document.getElementById("assessment-summary-body");
    body.innerHTML = `
      <div class="finding">
        ${statusBadge(assessment.application_health)}
        <strong>${t("application_health_label")}</strong>
        <p class="field-hint">${t("application_health_hint")}</p>
      </div>
      <div class="finding">
        ${testabilityCat ? statusBadge(testabilityCat.status) : ""}
        <strong>${t("testability_label")}</strong>
        <p class="field-hint">${t("testability_hint")}</p>
      </div>
      <div class="finding">
        <span class="status-badge">${escapeHtml((assessment.assessment_completeness || "").toUpperCase())}</span>
        <strong>${t("assessment_coverage_label")}</strong>
        <p class="field-hint">${t("assessment_coverage_hint")}</p>
      </div>
      <div class="finding">
        ${browserCat ? statusBadge(browserCat.status) : ""}
        <strong>${t("browser_testing_label")}</strong>
        <p class="field-hint">${t(browserCat && browserCat.status !== "not_assessed" ? "browser_testing_hint" : "browser_testing_not_assessed_hint")}</p>
      </div>
    `;
  }

  function renderResults(result) {
    show("screen-results");
    document.getElementById("quality-gate-card").classList.remove("hidden");
    const assessment = result.assessment;

    document.getElementById("overall-status").innerHTML = statusBadge(assessment.overall_status);
    renderAssessmentSummary(assessment);
    renderQualityGate(result.quality_gate);
    renderRegression(result.regression);

    const grid = document.getElementById("category-grid");
    grid.innerHTML = "";
    assessment.categories.forEach((cat) => {
      const div = document.createElement("div");
      div.className = "category-card";
      // Frontend detected != frontend functionally tested (spec section 64: static
      // analysis and browser testing answer different questions). The note is shown
      // directly on the Frontend card, driven by the actual Browser Testing category
      // status the backend computed -- never a static "not assessed" claim once
      // browser testing has actually run (Phase 9).
      const isFrontend = cat.name === "Frontend / Web Application Health";
      let browserNote = "";
      if (isFrontend && cat.status !== "not_assessed") {
        const browserCat = assessment.categories.find((c) => c.name === "Browser Testing");
        browserNote = browserCat && browserCat.status !== "not_assessed"
          ? `<p class="field-hint">${t("frontend_browser_ui_status")}: ${statusBadge(browserCat.status)}</p>`
          : `<p class="field-hint">${t("frontend_browser_ui_not_assessed")}</p>`;
      }
      div.innerHTML = `${statusBadge(cat.status)}<h3>${escapeHtml(categoryLabel(cat.name))}</h3><p>${escapeHtml(cat.summary || cat.reason || "")}</p>${browserNote}`;
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
      const classificationLabel = f.classification ? t("classification_" + f.classification) : "";
      div.innerHTML = `
        ${statusBadge(f.status)}
        ${classificationLabel ? `<span class="status-badge">${escapeHtml(classificationLabel)}</span>` : ""}
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
