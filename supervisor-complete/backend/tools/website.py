"""
Full multi-page website builder and individual page generation.
"""

from __future__ import annotations

import json
import re


from config import settings

from tools.deployment import _deploy_to_vercel
async def _build_full_website(business_name: str, service: str, pages: str = "home,about,services,contact",
                                brand_colors: str = "", brand_fonts: str = "",
                                cta_text: str = "Book a Call", cta_url: str = "#contact") -> str:
    """Generate a complete multi-page business website with responsive design and deploy to Vercel."""
    page_list = [p.strip().lower() for p in pages.split(",")]
    primary = "#6366f1"
    secondary = "#1e1b4b"
    accent = "#f59e0b"
    if brand_colors:
        try:
            colors = json.loads(brand_colors) if brand_colors.startswith("{") else {}
            primary = colors.get("primary", primary)
            secondary = colors.get("secondary", secondary)
            accent = colors.get("accent", accent)
        except json.JSONDecodeError:
            if brand_colors.startswith("#"):
                primary = brand_colors

    display_font = "Inter"
    body_font = "Inter"
    if brand_fonts:
        try:
            fonts = json.loads(brand_fonts) if brand_fonts.startswith("{") else {}
            display_font = fonts.get("display", display_font)
            body_font = fonts.get("body", body_font)
        except json.JSONDecodeError:
            pass

    css = f"""/* {business_name} — Generated Styles */
*{{margin:0;padding:0;box-sizing:border-box}}
:root{{
  --primary:{primary};--secondary:{secondary};--accent:{accent};
  --bg:#ffffff;--bg-alt:#f8fafc;--text:#1e293b;--text-light:#64748b;
  --radius:12px;--shadow:0 1px 3px rgba(0,0,0,0.1);
  --font-display:'{display_font}',system-ui,sans-serif;
  --font-body:'{body_font}',system-ui,sans-serif;
}}
@import url('https://fonts.googleapis.com/css2?family={display_font.replace(' ','+')}:wght@400;500;600;700;800&display=swap');
body{{font-family:var(--font-body);color:var(--text);line-height:1.6;font-size:16px}}
a{{color:var(--primary);text-decoration:none}}
img{{max-width:100%;height:auto}}
.container{{max-width:1200px;margin:0 auto;padding:0 24px}}

/* Navigation */
nav{{background:var(--bg);border-bottom:1px solid #e2e8f0;position:sticky;top:0;z-index:100;backdrop-filter:blur(12px)}}
nav .container{{display:flex;justify-content:space-between;align-items:center;height:72px}}
nav .logo{{font-family:var(--font-display);font-weight:800;font-size:1.5rem;color:var(--secondary)}}
nav ul{{display:flex;gap:32px;list-style:none}}
nav a{{color:var(--text);font-weight:500;transition:color 0.2s}}
nav a:hover{{color:var(--primary)}}
nav .cta-nav{{background:var(--primary);color:#fff!important;padding:10px 24px;border-radius:var(--radius);font-weight:600}}
nav .cta-nav:hover{{opacity:0.9}}

/* Hero */
.hero{{min-height:85vh;display:flex;align-items:center;background:linear-gradient(135deg,{secondary} 0%,{primary} 100%);color:#fff;text-align:center}}
.hero h1{{font-family:var(--font-display);font-size:clamp(2.5rem,5vw,4rem);font-weight:800;max-width:800px;margin:0 auto 1.5rem;line-height:1.1}}
.hero p{{font-size:1.25rem;max-width:600px;margin:0 auto 2rem;opacity:0.9}}
.btn{{display:inline-block;padding:14px 32px;border-radius:var(--radius);font-weight:700;font-size:1rem;transition:all 0.2s;cursor:pointer;border:none}}
.btn-primary{{background:var(--accent);color:var(--secondary)}}
.btn-primary:hover{{transform:translateY(-2px);box-shadow:0 4px 12px rgba(0,0,0,0.2)}}
.btn-secondary{{background:rgba(255,255,255,0.15);color:#fff;border:2px solid rgba(255,255,255,0.3)}}
.btn-secondary:hover{{background:rgba(255,255,255,0.25)}}

/* Sections */
section{{padding:96px 0}}
section:nth-child(even){{background:var(--bg-alt)}}
.section-header{{text-align:center;margin-bottom:64px}}
.section-header h2{{font-family:var(--font-display);font-size:2.5rem;font-weight:800;color:var(--secondary);margin-bottom:16px}}
.section-header p{{font-size:1.125rem;color:var(--text-light);max-width:600px;margin:0 auto}}

/* Grid */
.grid{{display:grid;gap:32px}}
.grid-2{{grid-template-columns:repeat(auto-fit,minmax(400px,1fr))}}
.grid-3{{grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}}
.grid-4{{grid-template-columns:repeat(auto-fit,minmax(250px,1fr))}}

/* Cards */
.card{{background:var(--bg);border:1px solid #e2e8f0;border-radius:var(--radius);padding:32px;transition:all 0.2s}}
.card:hover{{box-shadow:0 8px 24px rgba(0,0,0,0.08);transform:translateY(-4px)}}
.card h3{{font-size:1.25rem;font-weight:700;margin-bottom:12px;color:var(--secondary)}}
.card p{{color:var(--text-light)}}
.card .icon{{font-size:2rem;margin-bottom:16px}}

/* Contact */
.contact-form{{max-width:600px;margin:0 auto}}
.contact-form input,.contact-form textarea,.contact-form select{{width:100%;padding:14px 16px;border:1px solid #e2e8f0;border-radius:8px;font-size:1rem;margin-bottom:16px;font-family:inherit}}
.contact-form textarea{{min-height:150px;resize:vertical}}
.contact-form button{{width:100%}}

/* Footer */
footer{{background:var(--secondary);color:rgba(255,255,255,0.7);padding:48px 0 24px}}
footer .container{{display:flex;justify-content:space-between;flex-wrap:wrap;gap:24px}}
footer h4{{color:#fff;margin-bottom:12px}}
footer a{{color:rgba(255,255,255,0.7)}}footer a:hover{{color:#fff}}
footer .bottom{{border-top:1px solid rgba(255,255,255,0.1);margin-top:32px;padding-top:24px;text-align:center;font-size:0.875rem}}

/* Mobile */
@media(max-width:768px){{
  nav ul{{display:none}}
  .hero h1{{font-size:2rem}}
  .grid-2,.grid-3,.grid-4{{grid-template-columns:1fr}}
  section{{padding:64px 0}}
}}"""

    nav_links = []
    for p in page_list:
        label = p.replace("-", " ").replace("_", " ").title()
        href = f"{p}.html" if p != "home" else "index.html"
        nav_links.append(f'<li><a href="{href}">{label}</a></li>')
    nav_html = f"""<nav><div class="container">
<a href="index.html" class="logo">{business_name}</a>
<ul>{" ".join(nav_links)}</ul>
<a href="{cta_url}" class="cta-nav">{cta_text}</a>
</div></nav>"""

    footer_html = f"""<footer><div class="container">
<div><h4>{business_name}</h4><p>Professional {service.lower()} that delivers results.</p></div>
<div><h4>Quick Links</h4>{''.join(f'<p><a href="{p}.html" >{p.title()}</a></p>' for p in page_list if p != "home")}</div>
<div><h4>Contact</h4><p>Email: hello@{business_name.lower().replace(' ','')}.com</p></div>
<div class="bottom"><p>&copy; 2026 {business_name}. All rights reserved.</p></div>
</div></footer>"""

    def _make_page(title: str, body: str) -> str:
        return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — {business_name}</title>
<meta name="description" content="{business_name} — Professional {service}">
<link rel="stylesheet" href="styles.css">
</head><body>{nav_html}{body}{footer_html}</body></html>"""

    files = [{"file": "styles.css", "data": css}]

    if "home" in page_list or "index" in page_list:
        home_body = f"""
<section class="hero"><div class="container">
<h1>We Help Businesses Grow With Expert {service}</h1>
<p>Results-driven {service.lower()} for companies that demand excellence. No fluff, no excuses — just outcomes.</p>
<a href="{cta_url}" class="btn btn-primary">{cta_text}</a>
<a href="services.html" class="btn btn-secondary" style="margin-left:12px">Our Services</a>
</div></section>
<section><div class="container">
<div class="section-header"><h2>Why Choose {business_name}</h2><p>We combine deep expertise with proven systems to deliver measurable results.</p></div>
<div class="grid grid-3">
<div class="card"><div class="icon">&#9733;</div><h3>Proven Results</h3><p>Track record of delivering measurable outcomes for every client.</p></div>
<div class="card"><div class="icon">&#9881;</div><h3>Systematic Approach</h3><p>Battle-tested frameworks that remove guesswork and accelerate growth.</p></div>
<div class="card"><div class="icon">&#9829;</div><h3>Dedicated Partnership</h3><p>We become an extension of your team, not just another vendor.</p></div>
</div></div></section>
<section><div class="container" style="text-align:center">
<h2>Ready to Get Started?</h2><p style="margin:16px auto 32px;max-width:500px;color:var(--text-light)">Book a free strategy call and let's discuss how we can help grow your business.</p>
<a href="{cta_url}" class="btn btn-primary">{cta_text}</a>
</div></section>"""
        files.append({"file": "index.html", "data": _make_page("Home", home_body)})

    if "about" in page_list:
        about_body = f"""
<section style="padding-top:120px"><div class="container">
<div class="section-header"><h2>About {business_name}</h2><p>The story behind our mission to transform how businesses grow.</p></div>
<div class="grid grid-2" style="align-items:center">
<div><h3 style="font-size:1.5rem;margin-bottom:16px">Built on Expertise, Driven by Results</h3>
<p style="margin-bottom:16px">We started {business_name} because we saw too many businesses wasting money on {service.lower()} that didn't deliver. Our approach is different — we combine deep industry expertise with data-driven strategies that actually move the needle.</p>
<p>Every engagement starts with understanding your business, your market, and your goals. Then we build a custom strategy designed to deliver measurable results.</p></div>
<div class="card" style="background:var(--bg-alt)"><h3>Our Values</h3>
<p style="margin-bottom:12px"><strong>Transparency</strong> — No hidden fees, no vanity metrics. You see exactly what we do and why.</p>
<p style="margin-bottom:12px"><strong>Accountability</strong> — We tie our success to your outcomes, not our hours.</p>
<p><strong>Excellence</strong> — Good enough isn't in our vocabulary. We push for exceptional.</p></div>
</div></div></section>"""
        files.append({"file": "about.html", "data": _make_page("About", about_body)})

    if "services" in page_list:
        services_body = f"""
<section style="padding-top:120px"><div class="container">
<div class="section-header"><h2>Our Services</h2><p>Comprehensive {service.lower()} solutions tailored to your business goals.</p></div>
<div class="grid grid-2">
<div class="card"><h3>Strategy & Planning</h3><p>Deep-dive market research, competitive analysis, and custom roadmaps that align with your business objectives.</p></div>
<div class="card"><h3>Execution & Implementation</h3><p>We don't just plan — we execute. Full implementation of strategies with measurable milestones.</p></div>
<div class="card"><h3>Optimization & Growth</h3><p>Continuous improvement through data analysis, A/B testing, and performance optimization.</p></div>
<div class="card"><h3>Reporting & Analytics</h3><p>Transparent reporting with actionable insights. Know exactly what's working and what's next.</p></div>
</div></div></section>
<section><div class="container" style="text-align:center">
<h2>Let's Talk About Your Goals</h2><p style="margin:16px auto 32px;max-width:500px;color:var(--text-light)">Every business is different. Let's find the right approach for yours.</p>
<a href="{cta_url}" class="btn btn-primary">{cta_text}</a>
</div></section>"""
        files.append({"file": "services.html", "data": _make_page("Services", services_body)})

    if "contact" in page_list:
        contact_body = f"""
<section style="padding-top:120px"><div class="container">
<div class="section-header"><h2>Get in Touch</h2><p>Ready to grow? Let's start a conversation.</p></div>
<div class="contact-form" id="contact">
<form action="https://formspree.io/f/YOUR_FORM_ID" method="POST">
<input type="text" name="name" placeholder="Your Name" required>
<input type="email" name="email" placeholder="Your Email" required>
<input type="text" name="company" placeholder="Company Name">
<select name="budget"><option value="">Budget Range</option><option>$1,000-$3,000/mo</option><option>$3,000-$5,000/mo</option><option>$5,000-$10,000/mo</option><option>$10,000+/mo</option></select>
<textarea name="message" placeholder="Tell us about your project and goals..." required></textarea>
<button type="submit" class="btn btn-primary">{cta_text}</button>
</form></div></div></section>"""
        files.append({"file": "contact.html", "data": _make_page("Contact", contact_body)})

    for p in page_list:
        if p not in ("home", "index", "about", "services", "contact"):
            generic_body = f"""
<section style="padding-top:120px"><div class="container">
<div class="section-header"><h2>{p.replace('-',' ').replace('_',' ').title()}</h2><p>Content for this page.</p></div>
</div></section>"""
            files.append({"file": f"{p}.html", "data": _make_page(p.title(), generic_body)})

    result: dict[str, Any] = {
        "pages_generated": len(files) - 1,
        "files": [f["file"] for f in files],
        "features": ["Responsive design", "Mobile-first", "SEO meta tags", "Contact form",
                      "Sticky navigation", "Custom brand colors", "Google Fonts", "CSS Grid layout"],
    }

    token = getattr(settings, 'vercel_token', '') or ""
    if token:
        deploy_result = await _deploy_to_vercel(
            project_name=re.sub(r'[^a-z0-9-]', '', business_name.lower().replace(' ', '-'))[:40],
            files=json.dumps(files))
        deploy_data = json.loads(deploy_result)
        result["deployed_url"] = deploy_data.get("url", "")
        result["deployment_id"] = deploy_data.get("deployment_id", "")
        result["status"] = "deployed"
    else:
        result["status"] = "generated"
        result["note"] = "Set VERCEL_TOKEN to auto-deploy. Files ready for manual deployment."
    return json.dumps(result)



async def _generate_page(page_type: str, business_name: str, content: str,
                           brand_colors: str = "", style: str = "modern") -> str:
    """Generate a single page with specific content — pricing, case studies, FAQ, blog, etc."""
    primary = "#6366f1"
    if brand_colors:
        try:
            colors = json.loads(brand_colors) if brand_colors.startswith("{") else {}
            primary = colors.get("primary", primary)
        except json.JSONDecodeError:
            if brand_colors.startswith("#"):
                primary = brand_colors
    templates: dict[str, str] = {
        "pricing": f"""<section style="padding:120px 0 96px"><div style="max-width:1200px;margin:0 auto;padding:0 24px;text-align:center">
<h2 style="font-size:2.5rem;font-weight:800;margin-bottom:16px">Simple, Transparent Pricing</h2>
<p style="color:#64748b;margin-bottom:48px">No hidden fees. No long-term contracts. Cancel anytime.</p>
{content}
</div></section>""",
        "case_study": f"""<section style="padding:120px 0 96px"><div style="max-width:800px;margin:0 auto;padding:0 24px">
<h2 style="font-size:2.5rem;font-weight:800;margin-bottom:32px">Case Study</h2>
{content}
</div></section>""",
        "faq": f"""<section style="padding:120px 0 96px"><div style="max-width:800px;margin:0 auto;padding:0 24px">
<h2 style="font-size:2.5rem;font-weight:800;text-align:center;margin-bottom:48px">Frequently Asked Questions</h2>
{content}
</div></section>""",
        "blog": f"""<section style="padding:120px 0 96px"><div style="max-width:800px;margin:0 auto;padding:0 24px">
{content}
</div></section>""",
    }
    body = templates.get(page_type, f"<section style='padding:120px 0 96px'><div style='max-width:1200px;margin:0 auto;padding:0 24px'>{content}</div></section>")
    html = f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{page_type.title()} — {business_name}</title>
<link rel="stylesheet" href="styles.css">
</head><body>{body}</body></html>"""
    return json.dumps({"page_type": page_type, "html_length": len(html),
                       "html": html[:5000], "generated": True})



def register_website_tools(registry):
    """Register all website tools with the given registry."""
    from models import ToolParameter

    registry.register("build_full_website", "Generate a complete multi-page business website with responsive design and deploy.",
        [ToolParameter(name="business_name", description="Business name"),
         ToolParameter(name="service", description="Service/product description"),
         ToolParameter(name="pages", description="Comma-separated pages: home,about,services,contact,pricing,faq,blog", required=False),
         ToolParameter(name="brand_colors", description="JSON: {primary, secondary, accent} hex colors", required=False),
         ToolParameter(name="brand_fonts", description="JSON: {display, body} Google Font names", required=False),
         ToolParameter(name="cta_text", description="Call-to-action button text", required=False),
         ToolParameter(name="cta_url", description="CTA link URL", required=False)],
        _build_full_website, "website")

    registry.register("generate_page", "Generate a single page — pricing, case study, FAQ, blog post, etc.",
        [ToolParameter(name="page_type", description="Page type: pricing, case_study, faq, blog, landing"),
         ToolParameter(name="business_name", description="Business name"),
         ToolParameter(name="content", description="HTML content for the page body"),
         ToolParameter(name="brand_colors", description="JSON or hex color", required=False),
         ToolParameter(name="style", description="Visual style: modern, bold, minimal", required=False)],
        _generate_page, "website")

    # ── Finance Tools ──

