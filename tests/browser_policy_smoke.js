/* CI-only parent harness. Served dynamically; never injected into protected pages. */
"use strict";

(async () => {
  const prefix = "/__browser_policy_smoke__/";
  const session = new URL(location.href).searchParams.get("session");
  const result = { status: "INCOMPLETE", session, routes: [], script_probes: {}, assertions: [] };
  const output = document.getElementById("result");
  const targets = [
    ["root", "/"],
    ["brain", "/brain/"],
    ["khipu", "/khipu/"],
    ["frontier", "/frontier/"],
    ["showcase", "/frontier/showcase-public.html"],
    ["products", "/products/"],
    ["estate", "/estate/"],
  ];
  const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const pinnedRoutes = new Set(["root", "brain", "khipu"]);
  // A syntactically valid SHA-256 digest that is absent from every page policy.
  const wrongIntegrity = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  function assert(condition, name) {
    result.assertions.push({ name, ok: Boolean(condition) });
    if (!condition) throw new Error(name);
  }
  function endpoint(kind, token) {
    const url = new URL(prefix + kind, location.origin);
    url.searchParams.set("session", session);
    if (token) url.searchParams.set("token", token);
    return url.href;
  }
  async function until(check, label, timeout = 3000) {
    const deadline = Date.now() + timeout;
    while (!check()) {
      if (Date.now() >= deadline) throw new Error("Timed out: " + label);
      await delay(25);
    }
  }
  function type(w, id, value) {
    const input = w.document.getElementById(id);
    assert(Boolean(input), id + " exists");
    input.value = value;
    input.dispatchEvent(new w.Event("input", { bubbles: true }));
  }
  function filter(w, input, grid, count, prefixLabel) {
    const d = w.document;
    const original = d.querySelectorAll("#" + grid + " .card").length;
    assert(original > 0, prefixLabel + " initially renders cards");
    assert(Number.parseInt(d.getElementById(count).textContent, 10) === original,
      prefixLabel + " initial count agrees with cards");
    type(w, input, "__szl_browser_policy_no_match_8cf065cb__");
    assert(d.querySelectorAll("#" + grid + " .card").length === 0,
      prefixLabel + " search removes nonmatching cards");
    assert(Number.parseInt(d.getElementById(count).textContent, 10) === 0,
      prefixLabel + " search count reaches zero");
    type(w, input, "");
    assert(d.querySelectorAll("#" + grid + " .card").length === original,
      prefixLabel + " clearing search restores cards");
  }
  function sourcePins(key, w) {
    const d = w.document;
    const policies = d.querySelectorAll('meta[http-equiv="Content-Security-Policy"]');
    assert(policies.length === 1, key + " has exactly one CSP");
    const directives = policies[0].content.split(";").map((item) => item.trim().split(/\s+/));
    const scriptSources = directives.filter((item) => item[0] === "script-src");
    assert(scriptSources.length === 1, key + " has exactly one script-src");
    const allowed = scriptSources[0].slice(1);
    assert(allowed.length > 0 && !allowed.includes("'self'") && allowed.every((token) =>
      token === "'none'" || /^'sha256-[A-Za-z0-9+/]{43}='$/.test(token)),
    key + " script-src permits only hashes or denies all scripts");
    assert(!allowed.includes("'" + wrongIntegrity + "'"), key + " wrong-integrity probe is not authorized");
    const scripts = [...d.querySelectorAll("script[src]")];
    assert(Boolean(scripts.length) === pinnedRoutes.has(key), key + " external script coverage is explicit");
    for (const script of scripts) {
      assert(new URL(script.src).origin === location.origin, key + " approved external script is same-origin");
      assert(/^sha256-[A-Za-z0-9+/]{43}=$/.test(script.integrity) &&
        allowed.includes("'" + script.integrity + "'"),
      key + " external script has one exact CSP-authorized SRI hash: " + new URL(script.src).pathname);
    }
    return scripts;
  }
  async function scriptProbe(key, w, label, src, integrity, expectCsp) {
    const d = w.document;
    const script = d.createElement("script");
    const violations = [];
    const onViolation = (event) => {
      if ((event.effectiveDirective === "script-src" || event.effectiveDirective === "script-src-elem") &&
          event.blockedURI === src) violations.push(event);
    };
    d.addEventListener("securitypolicyviolation", onViolation);
    try {
      if (integrity !== null) script.integrity = integrity;
      script.src = src;
      const outcome = await new Promise((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error("Script probe timeout: " + key + " " + label)), 3000);
        script.onload = () => { clearTimeout(timer); resolve("load"); };
        script.onerror = () => { clearTimeout(timer); resolve("error"); };
        d.body.append(script);
      });
      assert(outcome === "error", key + " " + label + " raises script error instead of load");
      if (expectCsp) {
        await until(() => violations.length > 0, key + " " + label + " CSP violation");
        assert(violations.every((event) => event.disposition === "enforce"),
          key + " " + label + " has an enforced script-src violation");
      } else {
        await delay(25);
        assert(violations.length === 0, key + " " + label + " passes CSP before SRI rejects altered bytes");
      }
      assert(w.__szlDisallowedExternalScript === 0, key + " " + label + " never executes sentinel bytes");
      result.script_probes[key].push(label);
    } finally {
      d.removeEventListener("securitypolicyviolation", onViolation);
      script.remove();
    }
  }
  async function exercise(key, w) {
    const d = w.document;
    if (pinnedRoutes.has(key)) {
      assert(w.__SZL_APEX_RESPONSIVE_V3__ === true, key + " pinned responsive controller executes");
      assert(d.documentElement.dataset.szlViewport === "compact", key + " pinned responsive controller applies compact viewport");
    }
    if (key === "root") {
      assert(w.__SZL_FLOW_SHELL__ === true && d.documentElement.dataset.szlFlowReady === "true",
        "root pinned flow controller executes and initializes the shell");
      const toggle = d.getElementById("navToggle");
      const menu = d.getElementById("primaryNavigation");
      assert(w.innerWidth < 861 && w.getComputedStyle(toggle).display !== "none", "root mobile viewport");
      assert(toggle.getAttribute("aria-expanded") === "false" && menu.inert, "root menu initially closed");
      toggle.click();
      assert(toggle.getAttribute("aria-expanded") === "true" && !menu.inert, "root menu opens");
      d.dispatchEvent(new w.KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      assert(toggle.getAttribute("aria-expanded") === "false" && menu.inert && d.activeElement === toggle,
        "root Escape closes menu and restores focus");
      type(w, "chatInput", "What is the portfolio?");
      d.getElementById("chatForm").requestSubmit();
      await until(() => d.getElementById("chat").textContent.includes("offline sample · live concierge unavailable"),
        "labeled offline concierge sample");
      const chat = d.getElementById("chat");
      assert(chat.textContent.includes("offline sample · live concierge unavailable"), "root response is an offline sample");
      assert(chat.querySelector(".receipt-chip.ok") === null &&
        !/receipt verified|VERIFIED in-browser|served_by\s*[:=]/i.test(chat.textContent),
      "root offline response does not claim verification or live provenance");
    } else if (key === "brain") {
      type(w, "q", "Kantata");
      assert(d.querySelectorAll("#hits li").length === 1 && d.getElementById("hits").textContent.includes("Kantata"),
        "brain search returns matching handle");
      type(w, "q", "__szl_browser_policy_no_match_8cf065cb__");
      assert(d.querySelectorAll("#hits li").length === 0 && !d.getElementById("miss").hidden,
        "brain unknown search explicitly abstains");
    } else if (key === "khipu") {
      d.getElementById("score").click();
      let modeled = JSON.parse(d.getElementById("out-lambda").textContent);
      assert(modeled.value > 0 && modeled.blocked === false && modeled.proven_trust === false &&
        modeled.local_mode === "SIMULATED" && modeled.external_runtime === "NOT_MEASURED",
      "khipu score works and remains explicitly modeled");
      d.getElementById("zero").click();
      modeled = JSON.parse(d.getElementById("out-lambda").textContent);
      assert(modeled.value === 0 && modeled.blocked === true && modeled.reason === "zero-routed" &&
        modeled.proven_trust === false && modeled.local_mode === "SIMULATED",
      "khipu zero-route blocks without a proof claim");
    } else if (key === "frontier") {
      filter(w, "math-search", "math-grid", "math-count", "frontier software");
      filter(w, "model-search", "model-grid", "model-count", "frontier models");
    } else if (key === "showcase") {
      filter(w, "query", "grid", "count", "showcase");
    } else if (key === "products") {
      assert(d.querySelectorAll("a.card").length > 0 && d.body.textContent.includes("does not assert that a deployment is healthy"),
        "products remains a readable source-declared catalog");
    } else if (key === "estate") {
      const cards = [...d.querySelectorAll("[data-estate-asset]")];
      const visible = () => cards.filter((card) => !card.hidden);
      const count = d.getElementById("estate-count");
      const kind = d.getElementById("estate-kind");
      const category = d.getElementById("estate-category");
      const select = (input, value) => {
        input.value = value;
        input.dispatchEvent(new w.Event("change", { bubbles: true }));
      };
      const agrees = (label) => assert(Number.parseInt(count.textContent, 10) === visible().length, label);
      assert(cards.length > 0 && visible().length === cards.length, "estate initializes all inventory cards");
      agrees("estate initial live count agrees");
      assert(d.querySelectorAll(".research-exhibit").length === 3, "estate has three source-linked exhibits");
      assert(d.querySelectorAll('[data-kind="HF Kernel"] a.kernel-source').length > 0,
        "estate lists separate immutable Kernel Hub distributions");
      type(w, "estate-search", "__szl_browser_policy_no_match_8cf065cb__");
      assert(visible().length === 0, "estate unmatched search yields zero");
      agrees("estate zero-match live count agrees");
      type(w, "estate-search", "");
      for (const assetType of ["GitHub", "HF Model", "HF Dataset", "HF Space", "HF Kernel", "PyPI"]) {
        select(kind, assetType);
        assert(visible().length > 0 && visible().every((card) => card.dataset.kind === assetType), "estate filters " + assetType);
        agrees("estate count for " + assetType);
      }
      select(kind, "PyPI");
      select(category, "Python package");
      type(w, "estate-search", "szl-receipt-dsse");
      assert(visible().length === 1 && visible()[0].textContent.includes("py -m pip install szl-receipt-dsse=="), "estate PyPI search exposes a pinned release recipe");
      agrees("estate pinned package recipe count");
      type(w, "estate-search", "");
      select(category, "");
      select(kind, "HF Model");
      select(category, "Kernel / software");
      assert(visible().length > 0 && visible().every((card) =>
        card.dataset.kind === "HF Model" && card.dataset.category === "Kernel / software"),
      "estate kind and category filters intersect");
      agrees("estate combined filter live count agrees");
      type(w, "estate-search", visible()[0].dataset.id);
      assert(visible().length === 1, "estate search intersects selected kind and category");
      agrees("estate exact search live count agrees");
      type(w, "estate-search", "");
      select(kind, "");
      select(category, "");
      assert(visible().length === cards.length, "estate clearing all filters restores inventory only");
      agrees("estate restored count includes all six namespaces and excludes curated exhibits");
      assert(d.documentElement.scrollWidth <= w.innerWidth + 1, "estate compact viewport has no horizontal overflow");
    }
  }

  try {
    assert(/^[0-9a-f]{32}$/.test(session || ""), "fresh test session exists");
    const control = await fetch(endpoint("connect", "control"));
    assert(control.ok && (await control.json()).sentinel === "reachable", "sentinel is reachable from unprotected parent");
    window.__szlDisallowedExternalScript = 0;
    const controlScript = document.createElement("script");
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("Control script timeout")), 3000);
      controlScript.onload = () => { clearTimeout(timer); resolve(); };
      controlScript.onerror = () => { clearTimeout(timer); reject(new Error("Control script failed")); };
      controlScript.src = endpoint("script_no_integrity", "control");
      document.body.append(controlScript);
    });
    assert(window.__szlDisallowedExternalScript === 1, "same-origin sentinel bytes execute in unprotected parent");
    controlScript.remove();
    for (const [key, path] of targets) {
      const frame = document.createElement("iframe");
      frame.width = "390";
      frame.height = "844";
      frame.title = "Browser policy probe: " + key;
      await new Promise((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error("Frame load timeout: " + key)), 10000);
        frame.onload = () => { clearTimeout(timer); resolve(); };
        frame.onerror = () => { clearTimeout(timer); reject(new Error("Frame load failed: " + key)); };
        frame.src = path;
        document.getElementById("fixture").replaceChildren(frame);
      });
      const w = frame.contentWindow;
      const d = w.document;
      assert(new URL(w.location.href).pathname === path, key + " loaded exact target without redirect");
      assert(d.querySelectorAll("main").length === 1, key + " has one main landmark");
      const approvedScripts = sourcePins(key, w);
      const errors = [];
      const onError = (event) => { if (event.message) errors.push(event.message); };
      const onRejection = (event) => errors.push(String(event.reason));
      // Load-time compatibility is exercised by the actual page controllers below.
      // Capture subsequent application errors before intentional policy violations.
      w.addEventListener("error", onError);
      w.addEventListener("unhandledrejection", onRejection);
      await exercise(key, w);
      await delay(50);
      assert(errors.length === 0, key + " interaction has no uncaught script error: " + errors.join(" | "));
      w.removeEventListener("error", onError);
      w.removeEventListener("unhandledrejection", onRejection);

      w.__szlDisallowedScript = 0;
      const injected = d.createElement("script");
      injected.textContent = "window.__szlDisallowedScript += 1;";
      d.body.append(injected);
      const handler = d.createElement("button");
      handler.type = "button";
      handler.setAttribute("onclick", "window.__szlDisallowedScript += 10;");
      d.body.append(handler);
      handler.click();
      await delay(25);
      assert(w.__szlDisallowedScript === 0, key + " rejects unapproved inline script and HTML handler");
      injected.remove();
      handler.remove();

      result.script_probes[key] = [];
      w.__szlDisallowedExternalScript = 0;
      await scriptProbe(key, w, "no_integrity", endpoint("script_no_integrity", key), null, true);
      await scriptProbe(key, w, "wrong_integrity", endpoint("script_wrong_integrity", key), wrongIntegrity, true);
      if (pinnedRoutes.has(key)) {
        // Use the exact approved URL, including its original query. Cache behavior
        // is irrelevant: error + enforced CSP event must replace a load event.
        await scriptProbe(key, w, "approved_source_no_integrity", approvedScripts[0].src, null, true);
        // An authorized hash admits this same-origin request, but its different
        // response bytes must fail SRI before the executable sentinel can run.
        await scriptProbe(key, w, "tampered_bytes", endpoint("script_tampered", key), approvedScripts[0].integrity, false);
      }

      let rejected = false;
      await Promise.race([
        w.fetch(endpoint("connect", key)).then(() => {}, () => { rejected = true; }),
        delay(2500).then(() => { throw new Error("connect-src test timed out: " + key); }),
      ]);
      assert(rejected, key + " connect-src none rejects child fetch");
      const image = d.createElement("img");
      image.alt = "";
      await new Promise((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error("Allowed image timeout: " + key)), 3000);
        image.onload = () => { clearTimeout(timer); resolve(); };
        image.onerror = () => { clearTimeout(timer); reject(new Error("Allowed image rejected: " + key)); };
        image.src = endpoint("image", key);
        d.body.append(image);
      });
      const observations = await (await fetch(endpoint("observations"))).json();
      assert(observations[key].connect.length === 0, key + " forbidden fetch never reaches server");
      assert(observations[key].image.length === 1 && observations[key].image[0] === null,
        key + " allowed child image omits Referer");
      assert(observations[key].script_no_integrity.length === 0 &&
        observations[key].script_wrong_integrity.length === 0,
      key + " unapproved same-origin scripts never reach server");
      assert(observations[key].script_tampered.length === (pinnedRoutes.has(key) ? 1 : 0),
        key + " altered-byte script has exactly the expected server request count");
      if (pinnedRoutes.has(key)) {
        assert(observations[key].script_tampered[0] === null,
          key + " SRI-rejected script request omits Referer");
      }
      result.routes.push(key);
      frame.remove();
    }
    result.status = "PASS";
  } catch (error) {
    result.status = "FAIL";
    result.error = error instanceof Error ? error.message : String(error);
  } finally {
    output.textContent = JSON.stringify(result);
  }
})();
