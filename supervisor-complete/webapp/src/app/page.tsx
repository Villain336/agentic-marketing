"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { PRICING_TIERS, DEPARTMENTS, AGENTS, FEATURES, INTEGRATIONS } from "@/lib/constants";
import { OmniLogo } from "@/components/ui/omni-logo";

// ── Landing Page ────────────────────────────────────────────────────────

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white">
      <Nav />
      <Hero />
      <LogoBar />
      <Agents />
      <Features />
      <Terminal />
      <HowItWorks />
      <Pricing />
      <CTA />
      <Footer />
    </div>
  );
}

// ── Nav ─────────────────────────────────────────────────────────────────

function Nav() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <nav
      className={`fixed top-0 w-full z-50 transition-all duration-200 ${
        scrolled ? "bg-white border-b border-surface-100" : "bg-transparent"
      }`}
    >
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2.5">
          <OmniLogo size={32} className="text-surface-900" />
          <span className="font-display font-bold text-lg text-surface-900 tracking-tight">
            Omni OS
          </span>
        </Link>
        <div className="hidden md:flex items-center gap-8 text-sm text-surface-500">
          <a href="#agents" className="hover:text-surface-900 transition-colors">
            Agents
          </a>
          <a href="#features" className="hover:text-surface-900 transition-colors">
            Features
          </a>
          <a href="#how-it-works" className="hover:text-surface-900 transition-colors">
            How It Works
          </a>
          <a href="#pricing" className="hover:text-surface-900 transition-colors">
            Pricing
          </a>
          <Link href="/features" className="hover:text-surface-900 transition-colors">
            All Features
          </Link>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/auth" className="btn-ghost hidden sm:inline-flex">
            Log In
          </Link>
          <Link href="/auth?mode=signup" className="btn-primary">
            Get Started
          </Link>
        </div>
      </div>
    </nav>
  );
}

// ── Hero ─────────────────────────────────────────────────────────────────

function Hero() {
  return (
    <section className="pt-36 pb-24 px-6">
      <div className="max-w-4xl mx-auto text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-surface-200 text-xs text-surface-500 font-medium mb-8 animate-fade-in">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse-slow" />
          Now in Early Access
        </div>

        <h1 className="font-display font-extrabold text-5xl md:text-6xl lg:text-[4.5rem] text-surface-900 leading-[1.08] tracking-tight mb-6 animate-slide-up">
          Your entire business.
          <br />
          <span className="text-surface-400">Run by AI agents.</span>
        </h1>

        <p className="text-lg md:text-xl text-surface-500 max-w-2xl mx-auto mb-10 leading-relaxed animate-slide-up">
          44 autonomous agents handle marketing, sales, finance, legal, and engineering.
          Real APIs. Real execution. Not wrappers.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 animate-slide-up">
          <Link href="/auth?mode=signup" className="btn-primary text-base px-8 py-3.5">
            Start Free Trial
            <span className="text-surface-400 ml-1">&rarr;</span>
          </Link>
          <a href="#how-it-works" className="btn-secondary text-base px-8 py-3.5">
            See How It Works
          </a>
        </div>

        <div className="mt-16 flex items-center justify-center gap-8 text-sm text-surface-400 animate-fade-in">
          <Stat value="44" label="agents" />
          <span className="w-px h-4 bg-surface-200" />
          <Stat value="65+" label="integrations" />
          <span className="w-px h-4 bg-surface-200" />
          <Stat value="5" label="LLM providers" />
          <span className="w-px h-4 bg-surface-200" />
          <Stat value="9" label="tool categories" />
        </div>
      </div>
    </section>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <span>
      <strong className="text-surface-900 font-mono">{value}</strong>{" "}
      <span className="text-surface-400">{label}</span>
    </span>
  );
}

// ── Logo / Integration Bar ──────────────────────────────────────────────

function LogoBar() {
  return (
    <section className="py-10 border-y border-surface-100 overflow-hidden">
      <div className="mono-label text-center mb-6">Integrations</div>
      <div className="relative">
        <div className="flex marquee-track whitespace-nowrap">
          {[...INTEGRATIONS, ...INTEGRATIONS].map((name, i) => (
            <div
              key={`${name}-${i}`}
              className="inline-flex items-center gap-2 mx-4 px-4 py-2 rounded-lg border border-surface-100 text-sm text-surface-600 font-medium shrink-0"
            >
              <span className="w-2 h-2 rounded-full bg-surface-300" />
              {name}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Agents Section ──────────────────────────────────────────────────────

function Agents() {
  const [activeDept, setActiveDept] = useState("marketing");

  const agents = AGENTS.filter((a) => a.department === activeDept);
  const dept = DEPARTMENTS.find((d) => d.id === activeDept);

  return (
    <section id="agents" className="py-24 px-6">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-12">
          <div className="mono-label mb-3">Agents</div>
          <h2 className="font-display font-bold text-3xl md:text-4xl text-surface-900 mb-4">
            7 departments. 44 agents. One OS.
          </h2>
          <p className="text-surface-500 text-lg max-w-xl mx-auto">
            Each agent operates autonomously with real tool access and learns from every run.
          </p>
        </div>

        {/* Department tabs */}
        <div className="flex flex-wrap justify-center gap-2 mb-10">
          {DEPARTMENTS.map((d) => (
            <button
              key={d.id}
              onClick={() => setActiveDept(d.id)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
                activeDept === d.id
                  ? "bg-surface-900 text-white"
                  : "bg-surface-100 text-surface-600 hover:bg-surface-200"
              }`}
            >
              {d.label}
            </button>
          ))}
        </div>

        {/* Agent grid */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {agents.map((agent) => (
            <div
              key={agent.id}
              className="card-hover p-4 group"
            >
              <div className="flex items-start gap-3">
                <div className="w-9 h-9 rounded-lg bg-surface-100 flex items-center justify-center text-surface-500 font-mono text-xs shrink-0 group-hover:bg-surface-900 group-hover:text-white transition-colors">
                  {agent.label[0]}
                </div>
                <div className="min-w-0">
                  <div className="font-semibold text-sm text-surface-900">
                    {agent.label}
                  </div>
                  <div className="text-xs text-surface-500 mt-0.5">{agent.role}</div>
                  <div className="flex items-center gap-3 mt-2">
                    <span className="text-xs text-surface-400 font-mono">
                      {agent.realTools} tools
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {dept && (
          <p className="text-center text-sm text-surface-400 mt-6">
            {dept.description}
          </p>
        )}
      </div>
    </section>
  );
}

// ── Features Section ────────────────────────────────────────────────────

function Features() {
  const icons: Record<string, string> = {
    cpu: "\u2B22", code: "\u2039\u203A", globe: "\u25C9",
    layers: "\u2261", zap: "\u26A1", rocket: "\u2191",
  };

  return (
    <section id="features" className="py-24 px-6 bg-surface-950 text-white">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-16">
          <div className="mono-label text-surface-500 mb-3">Capabilities</div>
          <h2 className="font-display font-bold text-3xl md:text-4xl text-white mb-4">
            Not another AI wrapper.
          </h2>
          <p className="text-surface-400 text-lg max-w-xl mx-auto">
            Real APIs. Real execution. Every agent can write code, crawl the web, and take action.
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-px bg-surface-800 rounded-xl overflow-hidden">
          {FEATURES.map((f) => (
            <div key={f.id} className="bg-surface-950 p-8 hover:bg-surface-900 transition-colors">
              <div className="w-10 h-10 rounded-lg bg-surface-800 flex items-center justify-center text-lg mb-4 font-mono">
                {icons[f.icon] || "\u2022"}
              </div>
              <h3 className="font-semibold text-white mb-2">{f.title}</h3>
              <p className="text-sm text-surface-400 leading-relaxed">{f.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Terminal Demo ───────────────────────────────────────────────────────

function Terminal() {
  const [lineIndex, setLineIndex] = useState(0);

  const lines = [
    { prefix: "$", text: "omnios run prospector --icp \"B2B SaaS founders\"", color: "text-white" },
    { prefix: "\u2713", text: "Found 8 qualified prospects via Apollo API", color: "text-emerald-400" },
    { prefix: "\u2713", text: "Verified 8/8 emails via Hunter", color: "text-emerald-400" },
    { prefix: "$", text: "omnios run outreach --sequence 3-email", color: "text-white" },
    { prefix: "\u2713", text: "Sent 24 personalized emails via SendGrid", color: "text-emerald-400" },
    { prefix: "$", text: "omnios run billing --auto-invoice", color: "text-white" },
    { prefix: "\u2713", text: "Created 3 Stripe invoices totaling $14,250", color: "text-emerald-400" },
    { prefix: "\u2713", text: "Revenue loop complete. 3 deals closed.", color: "text-brand-400" },
  ];

  useEffect(() => {
    if (lineIndex >= lines.length) return;
    const timer = setTimeout(
      () => setLineIndex((prev) => prev + 1),
      lineIndex === 0 ? 1000 : 600
    );
    return () => clearTimeout(timer);
  }, [lineIndex, lines.length]);

  return (
    <section className="py-24 px-6">
      <div className="max-w-3xl mx-auto">
        <div className="text-center mb-10">
          <div className="mono-label mb-3">Live Demo</div>
          <h2 className="font-display font-bold text-3xl text-surface-900">
            The revenue loop in action
          </h2>
        </div>

        <div className="rounded-xl border border-surface-200 overflow-hidden bg-surface-950">
          {/* Title bar */}
          <div className="flex items-center gap-2 px-4 py-3 border-b border-surface-800">
            <div className="w-3 h-3 rounded-full bg-surface-700" />
            <div className="w-3 h-3 rounded-full bg-surface-700" />
            <div className="w-3 h-3 rounded-full bg-surface-700" />
            <span className="text-xs text-surface-500 font-mono ml-3">omnios</span>
          </div>

          {/* Terminal content */}
          <div className="p-6 font-mono text-sm space-y-2 min-h-[280px]">
            {lines.slice(0, lineIndex).map((line, i) => (
              <div key={i} className="flex gap-2 animate-fade-in">
                <span className={line.prefix === "$" ? "text-brand-400" : line.color}>
                  {line.prefix}
                </span>
                <span className={line.color}>{line.text}</span>
              </div>
            ))}
            {lineIndex < lines.length && (
              <div className="flex gap-2">
                <span className="text-brand-400">$</span>
                <span className="cursor-blink text-surface-500" />
              </div>
            )}
            {lineIndex >= lines.length && (
              <div className="flex gap-2 mt-4 pt-4 border-t border-surface-800">
                <span className="text-surface-500">
                  Ready for next campaign. Type `omnios run` to continue.
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

// ── How It Works ────────────────────────────────────────────────────────

function HowItWorks() {
  const steps = [
    {
      num: "01",
      title: "Onboard in 5 minutes",
      desc: "Tell us your business, goals, and target market. Our AI interviews you to build your company profile.",
    },
    {
      num: "02",
      title: "Agents build your playbook",
      desc: "44 agents execute in parallel — prospecting, content, ads, legal, finance. Each output feeds the next.",
    },
    {
      num: "03",
      title: "Real execution, not drafts",
      desc: "Agents use real APIs: SendGrid sends emails, Apollo finds leads, Stripe collects payments. No copy-paste.",
    },
    {
      num: "04",
      title: "Scale without headcount",
      desc: "Run multiple campaigns simultaneously. Agents learn from results and improve automatically.",
    },
  ];

  return (
    <section id="how-it-works" className="py-24 px-6 bg-surface-50">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-16">
          <div className="mono-label mb-3">Process</div>
          <h2 className="font-display font-bold text-3xl md:text-4xl text-surface-900">
            How Omni OS works
          </h2>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          {steps.map((step) => (
            <div key={step.num} className="flex gap-5 p-6 rounded-xl bg-white border border-surface-200">
              <div className="shrink-0 w-12 h-12 rounded-lg bg-surface-900 text-white font-display font-bold text-sm flex items-center justify-center">
                {step.num}
              </div>
              <div>
                <h3 className="font-semibold text-surface-900 mb-1.5">{step.title}</h3>
                <p className="text-sm text-surface-500 leading-relaxed">{step.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Pricing ─────────────────────────────────────────────────────────────

function Pricing() {
  return (
    <section id="pricing" className="py-24 px-6">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-14">
          <div className="badge bg-amber-50 text-amber-700 border border-amber-200 mb-4">
            Early Access — 50% Off
          </div>
          <h2 className="font-display font-bold text-3xl md:text-4xl text-surface-900 mb-4">
            Simple pricing. No per-seat fees.
          </h2>
          <p className="text-surface-500 text-lg">
            One platform. One price. Cancel anytime.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-5">
          {PRICING_TIERS.map((tier) => (
            <div
              key={tier.id}
              className={`card p-7 flex flex-col ${
                tier.highlight
                  ? "border-surface-900 ring-1 ring-surface-900 relative"
                  : ""
              }`}
            >
              {tier.highlight && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 badge bg-surface-900 text-white px-3">
                  Most Popular
                </div>
              )}
              <div className="mb-6">
                <h3 className="font-display font-bold text-xl text-surface-900">
                  {tier.name}
                </h3>
                <p className="text-sm text-surface-500 mt-1">{tier.description}</p>
              </div>
              <div className="mb-6">
                <div className="flex items-baseline gap-1">
                  <span className="font-display font-bold text-4xl text-surface-900">
                    ${tier.price.toLocaleString()}
                  </span>
                  <span className="text-surface-400 text-sm">/{tier.period}</span>
                </div>
                <div className="text-xs text-surface-400 line-through mt-1">
                  ${tier.originalPrice.toLocaleString()}/month
                </div>
              </div>
              <ul className="space-y-3 mb-8 flex-1">
                {tier.features.map((f) => (
                  <li key={f} className="flex items-start gap-2.5 text-sm text-surface-600">
                    <span className="text-surface-900 mt-0.5 text-xs">&check;</span>
                    {f}
                  </li>
                ))}
              </ul>
              <Link
                href="/auth?mode=signup"
                className={tier.highlight ? "btn-primary w-full" : "btn-secondary w-full"}
              >
                {tier.cta}
              </Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── CTA ─────────────────────────────────────────────────────────────────

function CTA() {
  return (
    <section className="py-24 px-6 bg-surface-950">
      <div className="max-w-3xl mx-auto text-center">
        <h2 className="font-display font-bold text-3xl md:text-4xl text-white mb-4">
          Stop hiring. Start deploying.
        </h2>
        <p className="text-surface-400 text-lg mb-8 max-w-lg mx-auto">
          44 AI agents replace entire departments. Ship your business on autopilot.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link
            href="/auth?mode=signup"
            className="inline-flex items-center justify-center gap-2 px-8 py-3.5 rounded-lg bg-white text-surface-900 font-medium text-base hover:bg-surface-100 transition-all"
          >
            Start Your Free Trial
            <span className="ml-1">&rarr;</span>
          </Link>
          <Link
            href="/features"
            className="inline-flex items-center justify-center gap-2 px-8 py-3.5 rounded-lg border border-surface-700 text-surface-300 font-medium text-base hover:bg-surface-800 transition-all"
          >
            Explore All Features
          </Link>
        </div>
      </div>
    </section>
  );
}

// ── Footer ──────────────────────────────────────────────────────────────

function Footer() {
  return (
    <footer className="border-t border-surface-100 py-12 px-6">
      <div className="max-w-6xl mx-auto">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-10">
          <div>
            <div className="flex items-center gap-2 mb-4">
              <OmniLogo size={28} className="text-surface-900" />
              <span className="text-sm font-bold text-surface-900">Omni OS</span>
            </div>
            <p className="text-xs text-surface-400 leading-relaxed">
              The AI operating system for founders who ship.
            </p>
          </div>

          <div>
            <div className="text-xs font-semibold text-surface-900 uppercase tracking-wider mb-3">
              Product
            </div>
            <ul className="space-y-2 text-sm text-surface-500">
              <li><Link href="/features" className="hover:text-surface-900 transition-colors">Features</Link></li>
              <li><a href="#pricing" className="hover:text-surface-900 transition-colors">Pricing</a></li>
              <li><a href="#agents" className="hover:text-surface-900 transition-colors">Agents</a></li>
              <li><Link href="/features#integrations" className="hover:text-surface-900 transition-colors">Integrations</Link></li>
            </ul>
          </div>

          <div>
            <div className="text-xs font-semibold text-surface-900 uppercase tracking-wider mb-3">
              Company
            </div>
            <ul className="space-y-2 text-sm text-surface-500">
              <li><Link href="/about" className="hover:text-surface-900 transition-colors">About</Link></li>
              <li><Link href="/blog" className="hover:text-surface-900 transition-colors">Blog</Link></li>
              <li><Link href="/careers" className="hover:text-surface-900 transition-colors">Careers</Link></li>
            </ul>
          </div>

          <div>
            <div className="text-xs font-semibold text-surface-900 uppercase tracking-wider mb-3">
              Legal
            </div>
            <ul className="space-y-2 text-sm text-surface-500">
              <li><Link href="/privacy" className="hover:text-surface-900 transition-colors">Privacy</Link></li>
              <li><Link href="/terms" className="hover:text-surface-900 transition-colors">Terms</Link></li>
              <li><Link href="/security" className="hover:text-surface-900 transition-colors">Security</Link></li>
            </ul>
          </div>
        </div>

        <div className="border-t border-surface-100 pt-6 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="text-xs text-surface-400">
            &copy; {new Date().getFullYear()} Omni OS Inc. All rights reserved.
          </div>
          <div className="flex items-center gap-4 text-xs text-surface-400">
            <Link href="/privacy" className="hover:text-surface-600">Privacy</Link>
            <Link href="/terms" className="hover:text-surface-600">Terms</Link>
            <Link href="/security" className="hover:text-surface-600">Security</Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
