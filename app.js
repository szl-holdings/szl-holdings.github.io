/* ============ SZL Holdings — interactions ============ */
(function () {
  "use strict";

  /* ---------- config ---------- */
  // Public concierge endpoint. Runtime identity and provenance are accepted only from the
  // response payload and are never inferred from this configured URL.
  var ROUTER_ENDPOINT = "https://alloyszlholdings.com/szl-concierge/chat";
  var PUBKEY_ENDPOINT = "https://alloyszlholdings.com/szl-concierge/pubkey";
  var PROOF_PROMPT = "In one sentence, what does a szl-receipt guarantee?";

  /* ---------- year ---------- */
  var y = document.getElementById("year");
  if (y) y.textContent = new Date().getFullYear();

  /* ---------- nav ---------- */
  var nav = document.getElementById("nav");
  var toggle = document.getElementById("navToggle");
  var links = document.querySelector(".nav-links");
  if (nav) {
    window.addEventListener("scroll", function () {
      nav.classList.toggle("scrolled", window.scrollY > 24);
    }, { passive: true });
  }
  if (toggle && links) {
    var desktopNav = window.matchMedia("(min-width: 861px)");
    var setMenu = function (open, returnFocus) {
      var mobileOpen = open && !desktopNav.matches;
      links.classList.toggle("open", mobileOpen);
      toggle.classList.toggle("open", mobileOpen);
      toggle.setAttribute("aria-expanded", mobileOpen ? "true" : "false");
      toggle.setAttribute("aria-label", mobileOpen ? "Close navigation" : "Open navigation");
      document.body.classList.toggle("menu-open", mobileOpen);
      links.inert = !desktopNav.matches && !mobileOpen;
      if (mobileOpen) links.removeAttribute("aria-hidden");
      else if (!desktopNav.matches) links.setAttribute("aria-hidden", "true");
      else links.removeAttribute("aria-hidden");
      if (!mobileOpen && returnFocus) toggle.focus();
    };

    toggle.addEventListener("click", function () {
      setMenu(toggle.getAttribute("aria-expanded") !== "true");
    });
    links.querySelectorAll("a").forEach(function (a) {
      a.addEventListener("click", function () { setMenu(false); });
    });
    document.addEventListener("keydown", function (event) {
      if (toggle.getAttribute("aria-expanded") !== "true") return;
      if (event.key === "Escape") {
        event.preventDefault();
        setMenu(false, true);
        return;
      }
      if (event.key !== "Tab") return;
      var menuLinks = Array.prototype.slice.call(links.querySelectorAll("a"));
      var first = menuLinks[0];
      var last = menuLinks[menuLinks.length - 1];
      if (!event.shiftKey && document.activeElement === toggle) {
        event.preventDefault();
        first.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        toggle.focus();
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        toggle.focus();
      } else if (event.shiftKey && document.activeElement === toggle) {
        event.preventDefault();
        last.focus();
      }
    });
    var resetMenu = function () { setMenu(false); };
    if (desktopNav.addEventListener) desktopNav.addEventListener("change", resetMenu);
    else desktopNav.addListener(resetMenu);
    setMenu(false);
  }

  /* ---------- ecosystem (real szl-holdings repos, grouped by function) ---------- */
  var GH = "https://github.com/szl-holdings/";
  var ECOSYSTEM = [
    { g: "Flagship applications", no: "A",
      note: "Product surfaces; runtime and receipt claims remain scoped to each interface's evidence labels.",
      items: [
        { name: "a11oy", lang: "Python", title: "The orchestrator", href: "https://a-11-oy.com",
          desc: "Full governed-inference application — Command Center, Five Superpowers, Observability, Mesh, Evidence, LLM Router. The signed-receipt substrate itself." },
        { name: "killinchu", lang: "Python", title: "Counter-UAS", href: "https://szlholdings-killinchu.hf.space/elite",
          desc: "Public counter-UAS interface. Live read feeds and simulated effectors are labeled separately, with human-on-the-loop authority explicit." },
        { name: "immune", lang: "TypeScript", title: "Verifiable-AI defense", href: "https://szlholdings-immune.hf.space",
          desc: "The IMMUNE Defense Matrix — append-only SHA-256 receipt chain (YAWAR), SENTRA/GATE admission, HUKLLA tripwires. Live on Hugging Face." },
        { name: "yarqa", lang: "Python", title: "Signed flow networks", href: GH + "yarqa",
          desc: "Turns CFD velocity fields into auditable compartmental networks with signed provenance receipts. Quechua: the canal that divides flow." },
        { name: "khipu-sda-core", lang: "Python", title: "Sovereign SDA", href: GH + "khipu-sda-core",
          desc: "Clean-room anomaly / space-domain-awareness engine — signed receipts and Λ-gated honest confidence. Kalman-grounded, doctrine v11." }
      ] },
    { g: "The signing substrate", no: "B",
      note: "The receipt bus itself: one primitive, hash-chained storage, and multi-party witnessing.",
      items: [
        { name: "szl-receipt", lang: "Python", title: "The signing primitive", href: GH + "szl-receipt",
          desc: "Shared signed-receipt library — DSSE / ECDSA-P256, cosign-compatible, UNSIGNED-honest fallback. Every SZL component shares this one." },
        { name: "khipu-consensus", lang: "Python", title: "Multi-party witnessed AI", href: GH + "khipu-consensus",
          desc: "3-of-4 BFT agreement — each witness cosigns an action hash with its own ECDSA P-256 key over DSSE. The category SZL invents." },
        { name: "szl-mesh", lang: "Python", title: "Doctrine-pinned mesh", href: GH + "szl-mesh",
          desc: "A CRDT mesh over BFT wiring with a 3-of-4 Khipu quorum — air-gap-friendly replication that never loses the receipt chain." },
        { name: "szl-lake", lang: "Python", title: "Append-only receipt lake", href: GH + "szl-lake",
          desc: "Append-only DSSE receipt store, GitHub-origin with a Hugging Face dataset mirror. The durable memory behind the substrate." },
        { name: "szl-trust", lang: "Shell", title: "Public trust portal", href: GH + "szl-trust",
          desc: "Covenant Proof Standard run artifacts and deterministic replay receipts — verify a run without trusting the operator." }
      ] },
    { g: "Sovereign inference & metering", no: "C",
      note: "The reasoning cortex: your models, your keys, honest joules — paid providers unarmed.",
      items: [
        { name: "szl-router", lang: "Python", title: "Sovereign LLM router", href: GH + "szl-router",
          desc: "Our own OpenAI-compatible gateway — sovereign-first, honest provenance. The brain behind every concierge on this page." },
        { name: "governed-inference-meter", lang: "Python", title: "Energy-metered proof", href: GH + "governed-inference-meter",
          desc: "Energy-metered inference receipts — NVML joules, tokens/joule, advisory policy gate. Honest UNAVAILABLE when NVML is unset." },
        { name: "szl-energy-attest", lang: "Python", title: "Attestable energy", href: GH + "szl-energy-attest",
          desc: "MEASURED-NVML joules or an honest UNAVAILABLE null — never fabricates a joule. Cheapest-watt placement with signable receipts." },
        { name: "szl-lambda-gate", lang: "Python", title: "The Λ aggregator", href: GH + "szl-lambda-gate",
          desc: "Weighted geometric mean over axis scores with an ADVISORY governance gate and A1–A4 axiom self-checks. Λ = Conjecture 1 — not proven trust." },
        { name: "szl-governed-norm", lang: "Python", title: "Governed kernels", href: GH + "szl-governed-norm",
          desc: "Correctness-verified RMSNorm / LayerNorm with optional SHA3-256 hash-chained provenance. Governance down at the kernel." }
      ] },
    { g: "Formal methods & research", no: "D",
      note: "Machine-checked truth — and honesty about what is proven versus conjectured.",
      items: [
        { name: "lutar-lean", lang: "Lean", title: "Machine-checked Λ", href: "https://doi.org/10.5281/zenodo.20434308",
          desc: "Lean 4 + Mathlib formalization of the Λ aggregator. 749 declarations · 14 axioms · 163 tracked sorries. Λ-uniqueness stated as Conjecture 1." },
        { name: "lean-kernel", lang: "Python", title: "Live proof kernel", href: GH + "lean-kernel",
          desc: "Live Lean v4.13.0 kernel for the Lutar Invariant, source-mirrored from a Hugging Face Space. The proofs, running — not just claimed." },
        { name: "szl-papers", lang: "TeX", title: "Academic corpus", href: GH + "szl-papers",
          desc: "Preprints, thesis lineage, bounty problems and prior-art disclosures. The written record behind the doctrine." },
        { name: "anatomy", lang: "JavaScript", title: "Living anatomy", href: GH + "anatomy",
          desc: "3D navigable substrate visualizing the five organs — reasoning cortex, trust gate, receipt bus, consensus, egress — powering a11oy + killinchu." }
      ] },
    { g: "Platform, runtime & developer tooling", no: "E",
      note: "Everything needed to build on the substrate — and to prove your build did what it says.",
      items: [
        { name: "platform", lang: "TypeScript", title: "Substrate runtime", href: GH + "platform",
          desc: "The monorepo: substrate runtime, agentic loops, an MCP server (11 tools), reusable workflows and CI gates. Doctrine v11 LOCKED." },
        { name: "hatun-mcp", lang: "Python", title: "Doctrine-aware MCP", href: GH + "hatun-mcp",
          desc: "Model Context Protocol server — 16 SZL tools under governance (Yuyay-13 gate, Khipu receipts, DSSE-signed). Streamable HTTP + SSE." },
        { name: "ouroboros", lang: "TypeScript", title: "Bounded recursion", href: GH + "ouroboros",
          desc: "Agentic-loop runtime with dual-witness emitters and governance budgets — recursion that provably terminates." },
        { name: "vsp-otel", lang: "TypeScript", title: "Λ-signed telemetry", href: GH + "vsp-otel",
          desc: "OpenTelemetry exporter for SZL audit fibers — every span Λ-signed. The egress organ, made observable." },
        { name: "developers", lang: "HTML", title: "Developer hub", href: GH + "developers",
          desc: "Build on SZL — API reference for all five flagships, a 5-minute quickstart, MCP integration for Claude / Cursor, runnable examples." },
        { name: "docs-site", lang: "JavaScript", title: "Unified docs", href: GH + "docs-site",
          desc: "Math-grounded, Quechua-rooted governed-AI documentation (VitePress). One place for the whole doctrine." },
        { name: "szl-build-env", lang: "Shell", title: "10-minute stack", href: GH + "szl-build-env",
          desc: "kind + Istio ambient mesh + OpenTelemetry + the 5-organ stack with a cosign verification gate. Local, reproducible, fast." }
      ] }
  ];
  var groups = document.getElementById("ecosystemGroups");
  if (groups) {
    ECOSYSTEM.forEach(function (grp) {
      var cards = grp.items.map(function (p, i) {
        return '<a class="card reveal" data-d="' + ((i % 4) + 1) + '" href="' + p.href + '" target="_blank" rel="noopener">' +
          '<div class="card-top"><span class="card-name">' + p.name + '</span>' +
          '<span class="card-lang">' + p.lang + '</span></div>' +
          '<h3>' + p.title + '</h3><p>' + p.desc + '</p>' +
          '<span class="card-link">view →</span></a>';
      }).join("");
      var sec = document.createElement("div");
      sec.className = "eco-group reveal";
      sec.innerHTML =
        '<div class="eco-group-head"><span class="eco-no">' + grp.no + '</span>' +
        '<h3>' + grp.g + '</h3><span class="eco-count">' + grp.items.length + '</span></div>' +
        '<p class="eco-note">' + grp.note + '</p>' +
        '<div class="grid">' + cards + '</div>';
      groups.appendChild(sec);
    });
  }

  /* ---------- reveal on scroll ---------- */
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
    });
  }, { threshold: 0.12, rootMargin: "0px 0px -8% 0px" });
  document.querySelectorAll(".reveal").forEach(function (el) { io.observe(el); });

  /* ---------- hero grid canvas ---------- */
  var canvas = document.getElementById("heroGrid");
  if (canvas && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    var ctx = canvas.getContext("2d");
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var t = 0, W, H;
    function resize() {
      W = canvas.clientWidth; H = canvas.clientHeight;
      canvas.width = W * dpr; canvas.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize(); window.addEventListener("resize", resize);
    function draw() {
      ctx.clearRect(0, 0, W, H);
      var gap = 46, ox = (t * 0.15) % gap, oy = (t * 0.08) % gap;
      ctx.strokeStyle = "rgba(28,41,66,0.5)"; ctx.lineWidth = 1;
      for (var x = -gap; x < W + gap; x += gap) { ctx.beginPath(); ctx.moveTo(x + ox, 0); ctx.lineTo(x + ox, H); ctx.stroke(); }
      for (var yy = -gap; yy < H + gap; yy += gap) { ctx.beginPath(); ctx.moveTo(0, yy + oy); ctx.lineTo(W, yy + oy); ctx.stroke(); }
      // pulsing nodes
      for (var i = 0; i < 5; i++) {
        var nx = (Math.sin(t * 0.006 + i * 1.7) * 0.5 + 0.5) * W;
        var ny = (Math.cos(t * 0.005 + i * 2.3) * 0.5 + 0.5) * H;
        var r = 2 + Math.sin(t * 0.03 + i) * 1.2;
        var g = ctx.createRadialGradient(nx, ny, 0, nx, ny, 60);
        g.addColorStop(0, "rgba(58,244,200,0.45)"); g.addColorStop(1, "rgba(58,244,200,0)");
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(nx, ny, 60, 0, 6.29); ctx.fill();
        ctx.fillStyle = "rgba(58,244,200,0.9)"; ctx.beginPath(); ctx.arc(nx, ny, r, 0, 6.29); ctx.fill();
      }
      t++; requestAnimationFrame(draw);
    }
    draw();
  }

  /* ---------- holographic anatomy projection (canvas, no libraries) ---------- */
  var holo = document.getElementById("holoCanvas");
  if (holo && holo.getContext) {
    var hx = holo.getContext("2d");
    var hdpr = Math.min(window.devicePixelRatio || 1, 2);
    var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var HW, HH, ht = 0;
    var LABELS = ["01 cortex", "02 gate", "03 bus", "04 consensus", "05 egress"];
    function hresize() {
      HW = holo.clientWidth; HH = holo.clientHeight;
      holo.width = HW * hdpr; holo.height = HH * hdpr; hx.setTransform(hdpr, 0, 0, hdpr, 0, 0);
    }
    hresize(); window.addEventListener("resize", hresize);
    function rad() { return Math.min(HW * 0.34, 220); }
    function nodeAt(i, rot) {
      var ang = (i / 5) * Math.PI * 2 + rot, rx = rad(), ry = rx * 0.34;
      return { x: HW / 2 + Math.cos(ang) * rx, y: HH * 0.52 + Math.sin(ang) * ry, d: (Math.sin(ang) + 1) / 2 };
    }
    // chromatic holographic double-stroke (teal + pale-green offset, purple-free)
    function hline(x1, y1, x2, y2, alpha, w) {
      hx.lineWidth = w || 1;
      hx.strokeStyle = "rgba(58,244,200," + alpha + ")"; hx.beginPath(); hx.moveTo(x1, y1); hx.lineTo(x2, y2); hx.stroke();
      hx.strokeStyle = "rgba(150,255,225," + (alpha * 0.5) + ")"; hx.beginPath(); hx.moveTo(x1 + 0.9, y1); hx.lineTo(x2 + 0.9, y2); hx.stroke();
    }
    function frame() {
      hx.clearRect(0, 0, HW, HH);
      var rot = reduce ? 0.6 : ht * 0.006, cx = HW / 2, baseY = HH * 0.9;
      // projector base + emitter cone
      var bg = hx.createRadialGradient(cx, baseY, 0, cx, baseY, HW * 0.32);
      bg.addColorStop(0, "rgba(58,244,200,0.32)"); bg.addColorStop(1, "rgba(58,244,200,0)");
      hx.fillStyle = bg; hx.beginPath(); hx.ellipse(cx, baseY, HW * 0.30, 10, 0, 0, 6.29); hx.fill();
      hline(cx - 6, baseY, cx - rad(), HH * 0.52, 0.10, 1);
      hline(cx + 6, baseY, cx + rad(), HH * 0.52, 0.10, 1);
      var ns = []; for (var i = 0; i < 5; i++) ns.push(nodeAt(i, rot));
      // receipt bus (ring edges)
      for (var e = 0; e < 5; e++) { var a = ns[e], b = ns[(e + 1) % 5]; hline(a.x, a.y, b.x, b.y, 0.16 + 0.24 * ((a.d + b.d) / 2), 1.2); }
      // one signed receipt traveling the bus
      var per = reduce ? 0.5 : (ht * 0.004) % 1, seg = per * 5, si = Math.floor(seg), f = seg - si;
      var pa = ns[si % 5], pb = ns[(si + 1) % 5], px = pa.x + (pb.x - pa.x) * f, py = pa.y + (pb.y - pa.y) * f;
      var pg = hx.createRadialGradient(px, py, 0, px, py, 26);
      pg.addColorStop(0, "rgba(220,255,245,0.95)"); pg.addColorStop(1, "rgba(58,244,200,0)");
      hx.fillStyle = pg; hx.beginPath(); hx.arc(px, py, 26, 0, 6.29); hx.fill();
      // organ nodes, depth-sorted
      ns.map(function (n, i) { return { n: n, i: i }; }).sort(function (A, B) { return A.n.d - B.n.d; }).forEach(function (o) {
        var n = o.n, r = 2.5 + 3.5 * n.d, al = 0.35 + 0.6 * n.d, gr = 22 * n.d + 8;
        var g = hx.createRadialGradient(n.x, n.y, 0, n.x, n.y, gr);
        g.addColorStop(0, "rgba(58,244,200," + (al * 0.5) + ")"); g.addColorStop(1, "rgba(58,244,200,0)");
        hx.fillStyle = g; hx.beginPath(); hx.arc(n.x, n.y, gr, 0, 6.29); hx.fill();
        hx.fillStyle = "rgba(224,255,246," + al + ")"; hx.beginPath(); hx.arc(n.x, n.y, r, 0, 6.29); hx.fill();
        if (n.d > 0.55) {
          hx.font = "10px 'IBM Plex Mono',ui-monospace,monospace"; hx.textAlign = "center";
          hx.fillStyle = "rgba(174,220,210," + (al * 0.9) + ")"; hx.fillText(LABELS[o.i], n.x, n.y - 12);
        }
      });
      ht++;
      if (!reduce) requestAnimationFrame(frame);
    }
    frame();
  }

  /* ---------- verifiable DSSE receipts (WebCrypto, ECDSA P-256) ---------- */
  function hex(n) { var s = "", c = "0123456789abcdef"; for (var i = 0; i < n; i++) s += c[Math.floor(Math.random() * 16)]; return s; }
  function b64bytes(b64) { var bin = atob(b64), n = bin.length, out = new Uint8Array(n); for (var i = 0; i < n; i++) out[i] = bin.charCodeAt(i); return out; }
  function paeBytes(type, bodyBytes) {
    var enc = new TextEncoder();
    var head = enc.encode("DSSEv1 " + enc.encode(type).length + " " + type + " " + bodyBytes.length + " ");
    var out = new Uint8Array(head.length + bodyBytes.length);
    out.set(head, 0); out.set(bodyBytes, head.length);
    return out;
  }
  var _pubkey = null, _pubkeyTried = false;
  async function getPubkey() {
    if (_pubkey || _pubkeyTried) return _pubkey;
    _pubkeyTried = true;
    if (!(window.crypto && window.crypto.subtle && window.TextEncoder && window.TextDecoder)) return null;
    try {
      var meta = await (await fetch(PUBKEY_ENDPOINT)).json();
      _pubkey = await crypto.subtle.importKey("spki", b64bytes(meta.spki_b64), { name: "ECDSA", namedCurve: "P-256" }, false, ["verify"]);
      return _pubkey;
    } catch (e) { return null; }
  }
  // Verify a DSSE envelope entirely in the browser against szl-router's pinned P-256 key.
  async function verifyReceipt(receipt) {
    try {
      var bodyBytes = b64bytes(receipt.payload);
      var payload = JSON.parse(new TextDecoder().decode(bodyBytes));
      var key = await getPubkey();
      if (!key) return { ok: false, payload: payload, reason: "no-key" };
      var sig = b64bytes(receipt.signatures[0].sig);
      var ok = await crypto.subtle.verify({ name: "ECDSA", hash: "SHA-256" }, key, sig, paeBytes(receipt.payloadType, bodyBytes));
      return { ok: ok, payload: payload, keyid: receipt.signatures[0].keyid || "" };
    } catch (e) { return { ok: false, reason: "error" }; }
  }

  /* ---------- proof-section receipt (real, fetched + live-verified) ---------- */
  var RECEIPT_SAMPLE = [
    [['k', '{']],
    [['k', '  "_type"        : '], ['v', '"https://in-toto.io/Statement/v1",']],
    [['k', '  "component"    : '], ['v', '"szl-router",']],
    [['k', '  "decision"     : '], ['v', '"governed-inference",']],
    [['k', '  "receipts.in"  : '], ['s', '"sha256:' + hex(56) + '",']],
    [['k', '  "receipts.out" : '], ['s', '"sha256:' + hex(56) + '",']],
    [['k', '  "invariant"    : '], ['v', '"receipts.in \u2261 receipts.out",']],
    [['k', '  "sig.alg"      : '], ['v', '"ECDSA-P256 / DSSE",']],
    [['k', '  "sig"          : '], ['s', '"MEUCIQD' + hex(40) + '",']],
    [['k', '  "status"       : '], ['v', '"illustrative"']],
    [['k', '}']]
  ];
  function buildReceiptLines(env, p) {
    var sig = env.signatures[0];
    function L(k, v, cls) { return [['k', k], [cls || 'v', v]]; }
    var lines = [
      [['k', '{']],
      L('  "payloadType"  : ', '"' + env.payloadType + '",'),
      L('  "typ"          : ', '"' + p.typ + '",'),
      L('  "model"        : ', '"' + p.model + '",'),
      L('  "served_by"    : ', '"' + p.served_by + '",'),
      L('  "sovereign"    : ', String(p.sovereign) + ','),
      L('  "receipts.in"  : ', '"sha256:' + p.message_sha256 + '",', 's'),
      L('  "receipts.out" : ', '"sha256:' + p.reply_sha256 + '",', 's')
    ];
    if (p.sources && p.sources.length) {
      lines.push(L('  "sources"      : ', '[' + p.sources.map(function (s) { return '"' + s + '"'; }).join(', ') + '],', 's'));
      if (p.retrieval_sha256) lines.push(L('  "retrieval"    : ', '"sha256:' + String(p.retrieval_sha256).slice(0, 32) + '\u2026",', 's'));
    }
    lines.push(
      L('  "invariant"    : ', '"receipts.in \u2261 receipts.out",'),
      L('  "sig.alg"      : ', '"ECDSA-P256 / DSSE",'),
      L('  "keyid"        : ', '"' + sig.keyid + '",'),
      L('  "sig"          : ', '"' + String(sig.sig).slice(0, 38) + '\u2026",', 's'),
      L('  "ts"           : ', '"' + p.ts + '"'),
      [['k', '}']]
    );
    return lines;
  }
  var body = document.getElementById("receiptBody");
  var badge = document.getElementById("verifyBadge");
  function typeReceiptLines(lines, onDone) {
    if (!body) return;
    body.innerHTML = ""; if (badge) badge.classList.remove("show");
    var cursor = document.createElement("span"); cursor.className = "cursor";
    body.appendChild(cursor);
    var li = 0;
    function nextLine() {
      if (li >= lines.length) { if (cursor.parentNode) cursor.remove(); if (onDone) onDone(); return; }
      var segs = lines[li], si = 0;
      function nextSeg() {
        if (si >= segs.length) { body.insertBefore(document.createTextNode("\n"), cursor); li++; setTimeout(nextLine, 45); return; }
        var cls = segs[si][0], txt = segs[si][1];
        var span = document.createElement("span"); span.className = cls;
        body.insertBefore(span, cursor);
        var ch = 0, speed = txt.length > 30 ? 4 : 13;
        (function typeChar() {
          span.textContent = txt.slice(0, ch); ch++;
          if (ch <= txt.length) setTimeout(typeChar, speed);
          else { si++; nextSeg(); }
        })();
      }
      nextSeg();
    }
    nextLine();
  }
  async function initProofReceipt() {
    if (!body) return;
    body.innerHTML = '<span class="k">// requesting a live signed receipt from szl-router\u2026</span>';
    var env = null, payload = null, verified = false, live = false;
    try {
      var res = await fetch(ROUTER_ENDPOINT, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: PROOF_PROMPT }) });
      if (res.ok) {
        var d = await res.json();
        if (d && d.provenance && d.provenance.receipt) {
          env = d.provenance.receipt;
          var v = await verifyReceipt(env);
          payload = v.payload; verified = !!v.ok; live = !!payload;
        }
      }
    } catch (e) { /* fall through to illustrative sample */ }
    var lines = live ? buildReceiptLines(env, payload) : RECEIPT_SAMPLE;
    typeReceiptLines(lines, function () {
      if (!badge) return;
      badge.classList.add("show"); badge.classList.remove("bad", "muted");
      if (live && verified) { badge.textContent = "VERIFIED"; }
      else if (live) { badge.textContent = "UNVERIFIED"; badge.classList.add("bad"); }
      else { badge.textContent = "ILLUSTRATIVE"; badge.classList.add("muted"); }
    });
  }
  if (body) {
    var rObs = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { initProofReceipt(); rObs.unobserve(e.target); } });
    }, { threshold: 0.4 });
    rObs.observe(body);
  }

  /* ---------- concierge ---------- */
  var chat = document.getElementById("chat");
  var form = document.getElementById("chatForm");
  var input = document.getElementById("chatInput");

  var KB = [
    { q: /receipt|sign|dsse|ecdsa|verify/i,
      a: "Receipt-aware components can emit DSSE evidence. Treat a receipt as VERIFIED only after its payload, signature, public key, and source binding validate; missing evidence remains UNSIGNED or UNAVAILABLE." },
    { q: /sovereign|router|brain|inference|model/i,
      a: "Live concierge responses are requested from szl-router. This page reports the served_by and sovereign fields returned by that response and falls back to an explicitly labeled offline sample when the endpoint is unavailable." },
    { q: /lean|theorem|proof|conjecture|lambda|\u039b|math/i,
      a: "The governance aggregator \u039b is formalized in Lean 4 + Mathlib: 749 declarations, 14 axioms, 163 tracked sorries. We state \u039b-uniqueness as Conjecture 1 \u2014 not a closed theorem. Being honest about that distinction is the point (DOI 10.5281/zenodo.20434308)." },
    { q: /killinchu|drone|uas|defense|counter/i,
      a: "killinchu is the public counter-UAS interface at szlholdings-killinchu.hf.space/elite. The surface labels live read feeds separately from simulated effectors and keeps human-on-the-loop authority explicit; inspect its current evidence labels before treating any control as operational." },
    { q: /immune|matrix|hugging/i,
      a: "IMMUNE is our Verifiable-AI Defense Matrix: an append-only SHA-256 receipt chain (YAWAR) with SENTRA/GATE admission and HUKLLA tripwires. It runs live as a Hugging Face Space." },
    { q: /portfolio|ecosystem|product|repos?|company|what.*(do|make)|szl/i,
      a: "SZL Holdings builds governed-AI products, receipt and policy libraries, formal-methods research, and developer tooling. Each repository and live surface keeps its own deployment, trust-root, and evidence state; the portfolio view does not collapse them into one runtime claim." },
    { q: /standard|slsa|in.?toto|sigstore|cosign|supply.?chain|interoper|walled/i,
      a: "SZL components use open provenance and signing formats where their checked-in contracts declare them. Verify the exact envelope with its declared algorithm and public key; format compatibility alone does not prove origin or operational status." },
    { q: /anatomy|organ|cortex|\bgate\b|\bbus\b|egress|nervous/i,
      a: "The five-organ diagram is an architecture model for reasoning, policy, receipt handling, witnesses, and egress. A live product must prove which stages executed and whether its evidence verified; the diagram itself is not runtime proof." },
    { q: /energy|joule|nvml|meter|watt|carbon|power/i,
      a: "governed-inference-meter and szl-energy-attest record MEASURED-NVML joules and tokens/joule per inference, hash-chained and signable \u2014 and report an honest UNAVAILABLE null when NVML is unset. We never fabricate a joule." },
    { q: /mesh|crdt|air.?gap|replicat|offline/i,
      a: "szl-mesh defines CRDT replication and Khipu witness contracts. Durability, quorum, and offline recovery are accepted only when the named deployment supplies corresponding evidence." },
    { q: /mcp|tool|integrat|cursor|claude|developer|platform|build/i,
      a: "Start with the docs-site and each repository's checked-in quickstart. MCP endpoints and tool inventories are live-state claims: discover them at the named endpoint, authenticate where required, and do not rely on a static tool count." },
    { q: /regulat|eu ai act|compliance|audit|nist|record.?keep|\blaw\b/i,
      a: "When the EU AI Act's high-risk obligations \u2014 logging, transparency, record-keeping \u2014 become enforceable on Aug 2, 2026, a signed, replayable receipt is exactly that record-keeping infrastructure. Verifiable AI has moved from research to production, and SZL's substrate is built for it." },
    { q: /frontier|confidential|\btee\b|enclave|roadmap|future|next/i,
      a: "The frontier we track: confidential computing / TEE attestation (H100/H200, TDX) is becoming the enterprise default for inference, and formal methods are going mainstream. SZL is sovereign-first today; hardware-attested inference is on the roadmap \u2014 stated honestly, not claimed as shipped." },
    { q: /consensus|khipu|bft|witness/i,
      a: "khipu-consensus defines a 3-of-4 witnessed-action contract. A completed quorum requires the corresponding independently signed witness set; absent signatures remain unavailable rather than inferred." },
    { q: /stephen|lutar|founder|who/i,
      a: "Stephen Lutar is Founder & CEO of SZL Holdings. His premise: if a decision matters, it should leave a receipt \u2014 and if a guarantee matters, it should be a theorem, or honestly labeled a conjecture." },
  ];
  function answerFor(text) {
    for (var i = 0; i < KB.length; i++) if (KB[i].q.test(text)) return KB[i].a;
    return "SZL Holdings builds cryptographic proof infrastructure for consequential AI \u2014 sovereign inference, DSSE-signed receipts, and machine-checked formal methods. Ask me about the receipts, the sovereign router, the Lean 4 proofs, or any product in the portfolio.";
  }

  function addMsg(role, html, prov) {
    var m = document.createElement("div");
    m.className = "msg " + role;
    m.innerHTML = html + (prov ? '<span class="prov">' + prov + "</span>" : "");
    chat.appendChild(m); chat.scrollTop = chat.scrollHeight;
    return m;
  }
  function typingMsg() {
    var m = document.createElement("div");
    m.className = "msg bot typing";
    m.innerHTML = "<span></span><span></span><span></span>";
    chat.appendChild(m); chat.scrollTop = chat.scrollHeight;
    return m;
  }
  function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function provenance(mode, p) {
    if (mode === "live" && p) {
      var by = p.served_by || "szl-router";
      var sov = p.sovereign ? "sovereign" : "external";
      var sha = (p.sha256 || "").slice(0, 12);
      return 'via <b>szl-router</b> · ' + sov + ' · <b>' + esc(by) + '</b>' +
        (sha ? ' · receipt <b>sha256:' + sha + '</b>' : '');
    }
    return 'offline sample · live concierge unavailable';
  }

  var greeted = false;
  function greet() {
    if (greeted) return; greeted = true;
    addMsg("bot", "Ask about the portfolio, evidence states, or developer routes. Live answers and offline samples are labeled separately.");
  }
  if (chat) {
    var cObs = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { greet(); cObs.unobserve(e.target); } });
    }, { threshold: 0.3 });
    cObs.observe(chat);
  }

  function renderReceipt(msgEl, receipt) {
    if (!receipt || !receipt.signatures || !receipt.signatures[0]) return;
    var sig = receipt.signatures[0];
    var chip = document.createElement("button");
    chip.type = "button"; chip.className = "receipt-chip";
    chip.innerHTML = '<span class="dot"></span> verifying receipt\u2026';
    var env = document.createElement("pre");
    env.className = "receipt-env";
    msgEl.appendChild(chip); msgEl.appendChild(env);
    chip.addEventListener("click", function () { env.classList.toggle("show"); });
    verifyReceipt(receipt).then(function (r) {
      if (r.ok) {
        chip.classList.add("ok");
        chip.innerHTML = '<span class="dot"></span> receipt verified \u00b7 ECDSA&nbsp;P-256 \u00b7 key ' + esc(String(sig.keyid || "").slice(0, 8));
      } else {
        chip.classList.add("bad");
        chip.innerHTML = '<span class="dot"></span> receipt ' + (r.reason === "no-key" ? "unchecked" : "unverified");
      }
      var pj = r.payload ? JSON.stringify(r.payload, null, 2) : "(payload unavailable)";
      env.textContent =
        "DSSE envelope\n" +
        "payloadType : " + receipt.payloadType + "\n" +
        "keyid       : " + (sig.keyid || "") + "\n" +
        "alg         : " + (sig.alg || "ecdsa-p256-sha256") + "\n" +
        "sig (P1363) : " + String(sig.sig || "").slice(0, 44) + "\u2026\n\n" +
        "payload (signed):\n" + pj + "\n\n" +
        "verified in-browser via DSSE PAE + WebCrypto ECDSA-P256/SHA-256\nagainst szl-router's pinned public key.";
      // Citations rendered ONLY from the cryptographically-verified payload (never top-level provenance).
      if (r.ok && r.payload && Array.isArray(r.payload.sources) && r.payload.sources.length) {
        var src = document.createElement("div");
        src.className = "receipt-sources";
        src.innerHTML = '<span class="src-label">grounded in \u00b7 attested</span>' +
          r.payload.sources.map(function (id) {
            var safe = String(id).replace(/[^a-z0-9._-]/gi, "");
            return '<a class="src-link" href="https://github.com/szl-holdings/' + safe + '" target="_blank" rel="noopener">' + esc(id) + '</a>';
          }).join("");
        msgEl.insertBefore(src, env);
      }
    });
  }

  // Rolling conversation memory (last few turns) so follow-up questions have context.
  var convo = [];
  function remember(role, content) {
    convo.push({ role: role, content: String(content).slice(0, 1000) });
    if (convo.length > 6) convo = convo.slice(-6);
  }
  async function ask(text) {
    var typing = typingMsg();
    if (ROUTER_ENDPOINT) {
      try {
        var res = await fetch(ROUTER_ENDPOINT, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text, history: convo.slice() })
        });
        if (res.ok) {
          var data = await res.json();
          if (data && data.reply) {
            typing.remove();
            remember("user", text); remember("assistant", data.reply);
            var m = addMsg("bot", esc(data.reply).replace(/\n/g, "<br>"), provenance("live", data.provenance));
            if (data.provenance && data.provenance.receipt) renderReceipt(m, data.provenance.receipt);
            return;
          }
        }
      } catch (err) { /* fall through to honest sample */ }
      typing.remove();
      addMsg("bot", answerFor(text), provenance("sample"));
      return;
    }
    setTimeout(function () {
      typing.remove();
      addMsg("bot", answerFor(text), provenance("sample"));
    }, 520 + Math.random() * 420);
  }

  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var text = (input.value || "").trim();
      if (!text) return;
      addMsg("user", text.replace(/</g, "&lt;"));
      input.value = "";
      ask(text);
    });
  }

  var suggest = document.getElementById("chatSuggest");
  if (suggest && chat) {
    suggest.addEventListener("click", function (e) {
      var b = e.target.closest ? e.target.closest(".suggest") : null;
      if (!b) return;
      var q = (b.getAttribute("data-q") || b.textContent || "").trim();
      if (!q) return;
      greet();
      addMsg("user", q.replace(/</g, "&lt;"));
      ask(q);
      suggest.classList.add("used");
    });
  }
})();
