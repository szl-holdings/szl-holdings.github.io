from pathlib import Path

p = Path('index.html')
s = p.read_text(encoding='utf-8')

nav_old = '      <a href="#ecosystem">Portfolio</a>'
nav_new = '      <a href="/products/">Products</a>\n      <a href="#ecosystem">Portfolio</a>'
if '/products/' not in s:
    if nav_old not in s:
        raise SystemExit('nav anchor not found')
    s = s.replace(nav_old, nav_new, 1)

anchor = '    <!-- THESIS -->'
section = '''    <!-- CANONICAL PRODUCT PORTFOLIO -->
    <section class="section" id="products" aria-labelledby="products-title">
      <div class="section-head reveal">
        <p class="kicker">One front door</p>
        <h2 id="products-title">Every SZL product. One portfolio.</h2>
        <p class="lede">holdings.a-11-oy.com is the company and portfolio catalog. The live A11oy product remains at a-11-oy.com; Hugging Face entries remain separately labeled publication surfaces.</p>
      </div>
      <div class="surface-grid" aria-label="Product portfolio entry points">
        <a class="surface-card reveal" href="/products/"><span class="surface-label">Canonical catalog</span><strong>Explore all products</strong><span>Verticals, platform products, source ownership, migration state, and the machine-readable catalog.</span><b aria-hidden="true">Open portfolio &rarr;</b></a>
        <a class="surface-card reveal" href="https://huggingface.co/SZLHOLDINGS" target="_blank" rel="noopener"><span class="surface-label">Published registry</span><strong>Hugging Face</strong><span>Models, datasets, collections, and Spaces retain their own evidence and runtime labels.</span><b aria-hidden="true">Open registry &rarr;</b></a>
      </div>
    </section>

'''
if 'id="products"' not in s:
    if anchor not in s:
        raise SystemExit('thesis anchor not found')
    s = s.replace(anchor, section + anchor, 1)

p.write_text(s, encoding='utf-8')
