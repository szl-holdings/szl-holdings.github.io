/* ============ SZL Holdings — interactions ============ */
(function () {
  "use strict";

  /* ---------- config ---------- */
  // Sovereign concierge endpoint — szl-router public proxy (server-side token, CORS-locked).
  // Reasoning runs on SZL-owned infrastructure; every reply carries honest provenance.
  var ROUTER_ENDPOINT = "https://alloyszlholdings.com/szl-concierge/chat";

  /* ---------- year ---------- */
  var y = document.getElementById("year");
  if (y) y.textContent = new Date().getFullYear();

  /* ---------- nav ---------- */
  var nav = document.getElementById("nav");
  var toggle = document.getElementById("navToggle");
  var links = document.querySelector(".nav-links");
  window.addEventListener("scroll", function () {
    nav.classList.toggle("scrolled", window.scrollY > 24);
  }, { passive: true });
  if (toggle) {
    toggle.addEventListener("click", function () {
      var open = links.classList.toggle("open");
      toggle.classList.toggle("open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
    links.querySelectorAll("a").forEach(function (a) {
      a.addEventListener("click", function () {
        links.classList.remove("open");
        toggle.classList.remove("open");
        toggle.setAttribute("aria-expanded", "false");
      });
    });
  }

  /* ---------- portfolio (real szl-holdings repos) ---------- */
  var PORTFOLIO = [
    { name: "a11oy", lang: "Python", title: "The orchestrator", href: "https://a-11-oy.com",
      desc: "Full governed-inference application — Command Center, Five Superpowers, Observability, Mesh, Evidence, LLM Router. The signed-receipt substrate itself." },
    { name: "killinchu", lang: "Python", title: "Counter-UAS", href: "https://a-11-oy.com/killinchu",
      desc: "16-view counter-drone application: sensor-fusion, ROE, 3-of-4 BFT, DSSE verifier, PQC, geofence, swarm. A DSSE receipt per interdiction." },
    { name: "immune", lang: "TypeScript", title: "Verifiable-AI defense", href: "https://szlholdings-immune.hf.space",
      desc: "The IMMUNE Defense Matrix — append-only SHA-256 receipt chain (YAWAR), SENTRA/GATE admission, HUKLLA tripwires. Live on Hugging Face." },
    { name: "szl-router", lang: "Python", title: "Sovereign LLM router", href: "https://github.com/szl-holdings/szl-router",
      desc: "Our own unified, OpenAI-compatible router — sovereign-first, honest provenance. The brain behind every concierge on this page." },
    { name: "khipu-consensus", lang: "Python", title: "Multi-party witnessed AI", href: "https://github.com/szl-holdings/khipu-consensus",
      desc: "3-of-4 BFT agreement — each witness cosigns an action hash with its own ECDSA P-256 key over DSSE. The category SZL invents." },
    { name: "lutar-lean", lang: "Lean", title: "Machine-checked Λ", href: "https://doi.org/10.5281/zenodo.20434308",
      desc: "Lean 4 + Mathlib formalization of the Λ aggregator. 749 declarations · 14 axioms · 163 tracked sorries. Λ-uniqueness stated as Conjecture 1." },
    { name: "szl-receipt", lang: "Python", title: "The signing primitive", href: "https://github.com/szl-holdings/szl-receipt",
      desc: "Shared signed-receipt library — DSSE / ECDSA-P256, cosign-compatible, UNSIGNED-honest fallback. Every SZL component shares this one." },
    { name: "anatomy", lang: "JavaScript", title: "Living anatomy", href: "https://a-11-oy.com",
      desc: "3D navigable substrate visualizing the five organs — reasoning cortex, trust gate, receipt bus, consensus, egress — powering a11oy + killinchu." },
    { name: "governed-inference-meter", lang: "Python", title: "Energy-metered proof", href: "https://github.com/szl-holdings/governed-inference-meter",
      desc: "Energy-metered governed-inference receipts — NVML joules, tokens/joule, advisory policy gate. Honest UNAVAILABLE when NVML is unset." },
  ];
  var grid = document.getElementById("portfolioGrid");
  if (grid) {
    PORTFOLIO.forEach(function (p, i) {
      var a = document.createElement("a");
      a.className = "card reveal";
      a.href = p.href; a.target = "_blank"; a.rel = "noopener";
      a.setAttribute("data-d", String((i % 4) + 1));
      a.innerHTML =
        '<div class="card-top"><span class="card-name">' + p.name + '</span>' +
        '<span class="card-lang">' + p.lang + '</span></div>' +
        '<h3>' + p.title + '</h3><p>' + p.desc + '</p>' +
        '<span class="card-link">view →</span>';
      grid.appendChild(a);
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

  /* ---------- signed receipt typewriter ---------- */
  function hex(n) { var s = ""; var c = "0123456789abcdef"; for (var i = 0; i < n; i++) s += c[Math.floor(Math.random() * 16)]; return s; }
  var RECEIPT = [
    [['k', '{']],
    [['k', '  "_type"        : '], ['v', '"https://in-toto.io/Statement/v1",']],
    [['k', '  "component"    : '], ['v', '"szl-router",']],
    [['k', '  "decision"     : '], ['v', '"governed-inference",']],
    [['k', '  "model"        : '], ['v', '"sovereign/local-primary",']],
    [['k', '  "lambda"       : '], ['v', '"Conjecture-1 (advisory)",']],
    [['k', '  "receipts.in"  : '], ['s', '"sha256:' + hex(56) + '",']],
    [['k', '  "receipts.out" : '], ['s', '"sha256:' + hex(56) + '",']],
    [['k', '  "invariant"    : '], ['v', '"receipts.in \u2261 receipts.out  \u2713",']],
    [['k', '  "witnesses"    : '], ['v', '"3-of-4 BFT",']],
    [['k', '  "sig.alg"      : '], ['v', '"ECDSA-P256 / DSSE",']],
    [['k', '  "sig"          : '], ['s', '"MEUCIQD' + hex(40) + '",']],
    [['k', '  "slsa"         : '], ['v', '"L1 (honest)",']],
    [['k', '  "status"       : '], ['v', '"VERIFIED"']],
    [['k', '}']]
  ];
  var body = document.getElementById("receiptBody");
  var badge = document.getElementById("verifyBadge");
  function typeReceipt() {
    if (!body) return;
    body.innerHTML = ""; if (badge) badge.classList.remove("show");
    var cursor = document.createElement("span"); cursor.className = "cursor";
    body.appendChild(cursor);
    var li = 0;
    function nextLine() {
      if (li >= RECEIPT.length) { if (cursor.parentNode) cursor.remove(); if (badge) badge.classList.add("show"); return; }
      var segs = RECEIPT[li]; var si = 0;
      function nextSeg() {
        if (si >= segs.length) { body.insertBefore(document.createTextNode("\n"), cursor); li++; setTimeout(nextLine, 55); return; }
        var cls = segs[si][0], txt = segs[si][1];
        var span = document.createElement("span"); span.className = cls;
        body.insertBefore(span, cursor);
        var ch = 0; var speed = txt.length > 30 ? 5 : 14;
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
  if (body) {
    var rObs = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { typeReceipt(); rObs.unobserve(e.target); } });
    }, { threshold: 0.4 });
    rObs.observe(body);
  }

  /* ---------- concierge ---------- */
  var chat = document.getElementById("chat");
  var form = document.getElementById("chatForm");
  var input = document.getElementById("chatInput");

  var KB = [
    { q: /receipt|sign|dsse|ecdsa|verify/i,
      a: "Every consequential action emits a DSSE envelope signed with ECDSA P-256 — cosign-compatible and hash-chained. You can verify it with any standard verifier; no SZL software required. The core invariant is receipts.in \u2261 receipts.out." },
    { q: /sovereign|router|brain|inference|model/i,
      a: "The concierge runs on szl-router — our own OpenAI-compatible gateway. It is sovereign-first: reasoning runs on infrastructure we own, and paid providers stay unarmed unless explicitly enabled. Honest provenance on every reply." },
    { q: /lean|theorem|proof|conjecture|lambda|\u039b|math/i,
      a: "The governance aggregator \u039b is formalized in Lean 4 + Mathlib: 749 declarations, 14 axioms, 163 tracked sorries. We state \u039b-uniqueness as Conjecture 1 \u2014 not a closed theorem. Being honest about that distinction is the point (DOI 10.5281/zenodo.20434308)." },
    { q: /killinchu|drone|uas|defense|counter/i,
      a: "killinchu is our counter-UAS application at a-11-oy.com/killinchu \u2014 16 operational views with sensor-fusion, 3-of-4 BFT agreement, a DSSE verifier and PQC. Each interdiction produces its own signed receipt." },
    { q: /immune|matrix|hugging/i,
      a: "IMMUNE is our Verifiable-AI Defense Matrix: an append-only SHA-256 receipt chain (YAWAR) with SENTRA/GATE admission and HUKLLA tripwires. It runs live as a Hugging Face Space." },
    { q: /portfolio|product|build|what.*do|company|szl/i,
      a: "SZL Holdings builds the proof layer beneath consequential AI \u2014 a11oy (the orchestrator), killinchu (counter-UAS), IMMUNE (defense matrix), szl-router (sovereign inference), khipu-consensus (multi-party witnessed AI) and lutar-lean (machine-checked \u039b). One doctrine, one signing primitive." },
    { q: /consensus|khipu|bft|witness/i,
      a: "khipu-consensus is 3-of-4 BFT, multi-party-witnessed agreement: every witness cosigns an action hash with its own ECDSA P-256 key over DSSE. No single node decides alone \u2014 the category we call multi-party-witnessed AI." },
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
    addMsg("bot", "I'm the SZL sovereign concierge. Ask me about the doctrine, the signed-receipt substrate, or any product in the portfolio.");
  }
  if (chat) {
    var cObs = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { greet(); cObs.unobserve(e.target); } });
    }, { threshold: 0.3 });
    cObs.observe(chat);
  }

  async function ask(text) {
    var typing = typingMsg();
    if (ROUTER_ENDPOINT) {
      try {
        var res = await fetch(ROUTER_ENDPOINT, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text })
        });
        if (res.ok) {
          var data = await res.json();
          if (data && data.reply) {
            typing.remove();
            addMsg("bot", esc(data.reply).replace(/\n/g, "<br>"), provenance("live", data.provenance));
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
})();
