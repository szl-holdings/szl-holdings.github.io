/* CI-only parent harness. Served dynamically; never injected into protected pages. */
"use strict";

(async () => {
  const prefix = "/__browser_policy_smoke__/";
  const session = new URL(location.href).searchParams.get("session");
  const result = { status: "INCOMPLETE", session, routes: [], assertions: [] };
  const output = document.getElementById("result");
  const targets = [
    ["root", "/"],
    ["brain", "/brain/"],
    ["khipu", "/khipu/"],
    ["frontier", "/frontier/"],
    ["showcase", "/frontier/showcase-public.html"],
    ["products", "/products/"],
  ];
  const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
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
  async function exercise(key, w) {
    const d = w.document;
    if (key === "root") {
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
    }
  }

  try {
    assert(/^[0-9a-f]{32}$/.test(session || ""), "fresh test session exists");
    const control = await fetch(endpoint("connect", "control"));
    assert(control.ok && (await control.json()).sentinel === "reachable", "sentinel is reachable from unprotected parent");
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
