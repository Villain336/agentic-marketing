"use client";

import Link from "next/link";
import { PRICING_TIERS, DEPARTMENTS, AGENTS } from "@/lib/constants";

// ── Landing Page ────────────────────────────────────────────────────────

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white">
      <Nav />
      <Hero />
      <Departments />
      <HowItWorks />
      <Pricing />
      <CTA />
      <Footer />
    </div>
  );
}

function Nav() {
  return (
    <nav className="fixed top-0 w-full bg-white/80 backdrop-blur-lg border-b border-surface-100 z-50">
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center">
            <span className="text-white font-bold text-sm">S</span>
          </div>
          <span className="font-display font-bold text-lg text-surface-900">Supervisor</span>
        </div>
        <div className="hidden md:flex items-center gap-8 text-sm text-surface-600">
          <a href="#departments" className="hover:text-surface-900 transition-colors">Agents</a>
          <a href="#how-it-works" className="hover:text-surface-900 transition-colors">How It Works</a>
          <a href="#pricing" className="hover:text-surface-900 transition-colors">Pricing</a>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/auth" className="btn-ghost">Log In</Link>
          <Link href="/auth?mode=signup" className="btn-primary">Get Started</Link>
        </div>
      </div>
    </nav>
  );
}

function Hero() {
  return (
    <section className="pt-32 pb-20 px-6">
      <div className="max-w-4xl mx-auto text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-brand-50 text-brand-700 text-xs font-medium mb-6 animate-fade-in">
          <span className="w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse" />
          Now in Early Access
        </div>
        <h1 className="font-display font-extrabold text-5xl md:text-6xl lg:text-7xl text-surface-900 leading-[1.1] tracking-tight mb-6 animate-slide-up">
          Your Entire Business,{" "}
          <span className="text-brand-600">Run by AI</span>
        </h1>
        <p className="text-lg md:text-xl text-surface-500 max-w-2xl mx-auto mb-10 leading-relaxed animate-slide-up">
          44 specialized agents handle marketing, sales, finance, legal, and engineering.
          You set the vision. Supervisor executes.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 animate-slide-up">
          <Link href="/auth?mode=signup" className="btn-primary text-base px-8 py-3">
            Start Free Trial
          </Link>
          <a href="#how-it-works" className="btn-secondary text-base px-8 py-3">
            See How It Works
          </a>
        </div>
        <div className="mt-12 flex items-center justify-center gap-8 text-sm text-surface-400">
          <span><strong className="text-surface-600">44</strong> agents</span>
          <span className="w-1 h-1 rounded-full bg-surface-300" />
          <span><strong className="text-surface-600">65+</strong> real integrations</span>
          <span className="w-1 h-1 rounded-full bg-surface-300" />
          <span><strong className="text-surface-600">5</strong> LLM providers</span>
        </div>
      </div>
    </section>
  );
}

function Departments() {
  return (
    <section id="departments" className="py-20 px-6 bg-surface-50">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-14">
          <h2 className="font-display font-bold text-3xl md:text-4xl text-surface-900 mb-4">
            7 Departments. 44 Agents. One Platform.
          </h2>
          <p className="text-surface-500 text-lg max-w-2xl mx-auto">
            Each department operates autonomously with specialized agents that learn from every campaign.
          </p>
        </div>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
          {DEPARTMENTS.map((dept) => {
            const agents = AGENTS.filter((a) => a.department === dept.id);
            return (
              <div key={dept.id} className="card-hover p-6 group">
                <div className={`badge ${dept.color} mb-3`}>{dept.label}</div>
                <p className="text-sm text-surface-500 mb-4">{dept.description}</p>
                <div className="space-y-2">
                  {agents.slice(0, 4).map((agent) => (
                    <div key={agent.id} className="flex items-center gap-3 text-sm">
                      <div className="w-6 h-6 rounded-md bg-surface-100 flex items-center justify-center text-surface-500 text-xs">
                        {agent.label[0]}
                      </div>
                      <span className="text-surface-700 font-medium">{agent.label}</span>
                      <span className="text-surface-400 text-xs ml-auto">{agent.role}</span>
                    </div>
                  ))}
                  {agents.length > 4 && (
                    <p className="text-xs text-surface-400 pl-9">+{agents.length - 4} more agents</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function HowItWorks() {
  const steps = [
    { num: "01", title: "Onboard in 5 minutes", desc: "Tell us about your business, goals, and target market. Our AI interviews you to build your company profile." },
    { num: "02", title: "Agents build your playbook", desc: "44 agents execute in parallel — prospecting, content, ads, legal, finance. Each output feeds the next." },
    { num: "03", title: "Learn and improve", desc: "The genome system tracks what works. Every campaign makes the next one smarter. Cross-campaign intelligence compounds." },
    { num: "04", title: "Scale without headcount", desc: "Run multiple campaigns simultaneously. Agents re-run automatically when metrics drop. You review, approve, collect." },
  ];
  return (
    <section id="how-it-works" className="py-20 px-6">
      <div className="max-w-5xl mx-auto">
        <h2 className="font-display font-bold text-3xl md:text-4xl text-surface-900 text-center mb-14">
          How Supervisor Works
        </h2>
        <div className="grid md:grid-cols-2 gap-8">
          {steps.map((step) => (
            <div key={step.num} className="flex gap-5">
              <div className="flex-shrink-0 w-12 h-12 rounded-xl bg-brand-50 text-brand-600 font-display font-bold text-lg flex items-center justify-center">
                {step.num}
              </div>
              <div>
                <h3 className="font-semibold text-surface-900 mb-1">{step.title}</h3>
                <p className="text-sm text-surface-500 leading-relaxed">{step.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Pricing() {
  return (
    <section id="pricing" className="py-20 px-6 bg-surface-50">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-14">
          <div className="badge bg-amber-100 text-amber-700 border border-amber-200 mb-4">Early Access Pricing — 50% Off</div>
          <h2 className="font-display font-bold text-3xl md:text-4xl text-surface-900 mb-4">
            Simple, Transparent Pricing
          </h2>
          <p className="text-surface-500 text-lg">No per-seat charges. No hidden fees. One platform, one price.</p>
        </div>
        <div className="grid md:grid-cols-3 gap-6">
          {PRICING_TIERS.map((tier) => (
            <div
              key={tier.id}
              className={`card p-7 flex flex-col ${
                tier.highlight
                  ? "border-brand-500 ring-1 ring-brand-500/20 shadow-lg relative"
                  : ""
              }`}
            >
              {tier.highlight && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 badge bg-brand-600 text-white px-3">
                  Most Popular
                </div>
              )}
              <div className="mb-6">
                <h3 className="font-display font-bold text-xl text-surface-900">{tier.name}</h3>
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
                  <li key={f} className="flex items-start gap-2 text-sm text-surface-600">
                    <span className="text-brand-500 mt-0.5">&#10003;</span>
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

function CTA() {
  return (
    <section className="py-20 px-6">
      <div className="max-w-3xl mx-auto text-center">
        <h2 className="font-display font-bold text-3xl md:text-4xl text-surface-900 mb-4">
          Ready to run your business on autopilot?
        </h2>
        <p className="text-surface-500 text-lg mb-8">
          Join founders who replaced 10+ tools with one AI operating system.
        </p>
        <Link href="/auth?mode=signup" className="btn-primary text-base px-10 py-3.5">
          Start Your Free Trial
        </Link>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-surface-100 py-10 px-6">
      <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-brand-600 flex items-center justify-center">
            <span className="text-white text-xs font-bold">S</span>
          </div>
          <span className="text-sm font-medium text-surface-700">Supervisor</span>
        </div>
        <div className="text-xs text-surface-400">
          &copy; {new Date().getFullYear()} Supervisor AI. All rights reserved.
        </div>
      </div>
    </footer>
  );
}
