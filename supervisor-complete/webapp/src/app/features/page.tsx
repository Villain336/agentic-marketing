"use client";

import Link from "next/link";
import { AGENTS, DEPARTMENTS, INTEGRATIONS, FEATURES } from "@/lib/constants";

export default function FeaturesPage() {
  return (
    <div className="min-h-screen bg-white">
      <SiteNav />

      {/* Hero */}
      <section className="pt-32 pb-16 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <div className="mono-label mb-3">Features</div>
          <h1 className="font-display font-extrabold text-4xl md:text-5xl text-surface-900 leading-tight mb-4">
            Everything your business needs.
            <br />
            <span className="text-surface-400">In one OS.</span>
          </h1>
          <p className="text-lg text-surface-500 max-w-xl mx-auto">
            44 autonomous agents, 65+ real integrations, 5 LLM providers with automatic failover.
          </p>
        </div>
      </section>

      {/* Core capabilities */}
      <section className="py-20 px-6 bg-surface-50">
        <div className="max-w-6xl mx-auto">
          <div className="mono-label mb-6">Core Capabilities</div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
            {FEATURES.map((f) => (
              <div key={f.id} className="bg-white rounded-xl border border-surface-200 p-6">
                <h3 className="font-semibold text-surface-900 mb-2">{f.title}</h3>
                <p className="text-sm text-surface-500 leading-relaxed">{f.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Agent Directory */}
      <section className="py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="mono-label mb-6">Agent Directory</div>
          <h2 className="font-display font-bold text-2xl text-surface-900 mb-8">
            All 44 agents, organized by department
          </h2>
          {DEPARTMENTS.map((dept) => {
            const agents = AGENTS.filter((a) => a.department === dept.id);
            return (
              <div key={dept.id} className="mb-10">
                <h3 className="font-semibold text-lg text-surface-900 mb-1">{dept.label}</h3>
                <p className="text-sm text-surface-500 mb-4">{dept.description}</p>
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                  {agents.map((agent) => (
                    <div key={agent.id} className="card-hover p-4">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-surface-100 flex items-center justify-center text-surface-500 font-mono text-xs">
                          {agent.label[0]}
                        </div>
                        <div>
                          <div className="font-medium text-sm text-surface-900">{agent.label}</div>
                          <div className="text-xs text-surface-500">{agent.role}</div>
                        </div>
                      </div>
                      <div className="mt-3 text-xs text-surface-400 font-mono">
                        {agent.realTools} real tools &middot; {agent.toolCount} total
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Integrations */}
      <section id="integrations" className="py-20 px-6 bg-surface-950">
        <div className="max-w-6xl mx-auto">
          <div className="mono-label text-surface-500 mb-6">Integrations</div>
          <h2 className="font-display font-bold text-2xl text-white mb-8">
            65+ real API integrations
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
            {INTEGRATIONS.map((name) => (
              <div
                key={name}
                className="flex items-center gap-2 px-4 py-3 rounded-lg border border-surface-800 text-sm text-surface-300"
              >
                <span className="w-2 h-2 rounded-full bg-surface-600" />
                {name}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Claude SDK */}
      <section className="py-20 px-6">
        <div className="max-w-4xl mx-auto">
          <div className="mono-label mb-6">AI Code Engine</div>
          <h2 className="font-display font-bold text-2xl text-surface-900 mb-4">
            Every agent writes production code
          </h2>
          <p className="text-surface-500 mb-8 max-w-xl">
            Powered by the Claude Agent SDK, every agent can generate, review, refactor, and deploy code.
            The Full-Stack Dev agent ships entire applications.
          </p>
          <div className="grid sm:grid-cols-2 gap-4">
            {[
              { title: "Code Generation", desc: "Write Python, TypeScript, Go, Rust — production-quality with error handling" },
              { title: "Code Review", desc: "Security, performance, and readability analysis with fix suggestions" },
              { title: "Test Generation", desc: "Comprehensive test suites with pytest, Jest, or Vitest" },
              { title: "Refactoring", desc: "Improve code quality while preserving all functionality" },
            ].map((item) => (
              <div key={item.title} className="p-5 rounded-xl border border-surface-200">
                <h3 className="font-semibold text-sm text-surface-900 mb-1">{item.title}</h3>
                <p className="text-xs text-surface-500">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Crawlers */}
      <section className="py-20 px-6 bg-surface-50">
        <div className="max-w-4xl mx-auto">
          <div className="mono-label mb-6">Web Intelligence</div>
          <h2 className="font-display font-bold text-2xl text-surface-900 mb-4">
            Cloudflare-powered web crawlers
          </h2>
          <p className="text-surface-500 mb-8 max-w-xl">
            Crawl competitor sites, extract pricing tables, monitor feature changes — all in real time
            with Cloudflare Browser Rendering.
          </p>
          <div className="grid sm:grid-cols-2 gap-4">
            {[
              { title: "Website Crawling", desc: "Crawl up to 50 pages per site with full JavaScript rendering" },
              { title: "Structured Extraction", desc: "Extract pricing, features, team info as structured JSON" },
              { title: "Competitor Monitoring", desc: "Track pricing changes, new features, blog posts automatically" },
              { title: "Content Intelligence", desc: "Analyze competitor content strategy and identify gaps" },
            ].map((item) => (
              <div key={item.title} className="p-5 rounded-xl bg-white border border-surface-200">
                <h3 className="font-semibold text-sm text-surface-900 mb-1">{item.title}</h3>
                <p className="text-xs text-surface-500">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 px-6 bg-surface-950">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="font-display font-bold text-3xl text-white mb-4">
            Ready to deploy your AI workforce?
          </h2>
          <p className="text-surface-400 mb-8">
            Start with 10 agents. Scale to 44. No per-seat pricing.
          </p>
          <Link href="/auth?mode=signup" className="inline-flex items-center gap-2 px-8 py-3.5 rounded-lg bg-white text-surface-900 font-medium hover:bg-surface-100 transition-all">
            Start Free Trial <span>&rarr;</span>
          </Link>
        </div>
      </section>

      <SiteFooter />
    </div>
  );
}

function SiteNav() {
  return (
    <nav className="fixed top-0 w-full z-50 bg-white border-b border-surface-100">
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-surface-900 flex items-center justify-center">
            <span className="text-white font-bold text-sm font-mono">O</span>
          </div>
          <span className="font-display font-bold text-lg text-surface-900 tracking-tight">Omni OS</span>
        </Link>
        <div className="hidden md:flex items-center gap-8 text-sm text-surface-500">
          <Link href="/#agents" className="hover:text-surface-900 transition-colors">Agents</Link>
          <Link href="/features" className="text-surface-900 font-medium">Features</Link>
          <Link href="/#pricing" className="hover:text-surface-900 transition-colors">Pricing</Link>
          <Link href="/about" className="hover:text-surface-900 transition-colors">About</Link>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/auth" className="btn-ghost hidden sm:inline-flex">Log In</Link>
          <Link href="/auth?mode=signup" className="btn-primary">Get Started</Link>
        </div>
      </div>
    </nav>
  );
}

function SiteFooter() {
  return (
    <footer className="border-t border-surface-100 py-10 px-6">
      <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-surface-900 flex items-center justify-center">
            <span className="text-white text-xs font-bold font-mono">O</span>
          </div>
          <span className="text-sm font-medium text-surface-700">Omni OS</span>
        </div>
        <div className="flex items-center gap-6 text-xs text-surface-400">
          <Link href="/features" className="hover:text-surface-600">Features</Link>
          <Link href="/about" className="hover:text-surface-600">About</Link>
          <Link href="/privacy" className="hover:text-surface-600">Privacy</Link>
          <Link href="/terms" className="hover:text-surface-600">Terms</Link>
          <Link href="/security" className="hover:text-surface-600">Security</Link>
        </div>
        <div className="text-xs text-surface-400">
          &copy; {new Date().getFullYear()} Omni OS Inc.
        </div>
      </div>
    </footer>
  );
}
