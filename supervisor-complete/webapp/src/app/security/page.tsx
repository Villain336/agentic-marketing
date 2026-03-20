import type { Metadata } from "next";
import Link from "next/link";
import { OmniLogo } from "@/components/ui/omni-logo";

export const metadata: Metadata = {
  title: "Security",
  description: "How Omni OS keeps your data and credentials secure.",
};

export default function SecurityPage() {
  return (
    <div className="min-h-screen bg-white">
      <nav className="fixed top-0 w-full z-50 bg-white border-b border-surface-100">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <OmniLogo size={32} className="text-surface-900" />
            <span className="font-display font-bold text-lg text-surface-900 tracking-tight">Omni OS</span>
          </Link>
          <Link href="/auth?mode=signup" className="btn-primary">Get Started</Link>
        </div>
      </nav>

      <section className="pt-32 pb-20 px-6">
        <div className="max-w-3xl mx-auto">
          <div className="mono-label mb-3">Security</div>
          <h1 className="font-display font-bold text-3xl text-surface-900 mb-6">
            Security at Omni OS
          </h1>

          <div className="space-y-6 text-sm text-surface-600 leading-relaxed">
            <p>Security is foundational to Omni OS. When AI agents operate autonomously with real API credentials, security is not optional — it is the product.</p>

            <div className="grid sm:grid-cols-2 gap-4 my-8">
              {[
                { title: "Encryption at Rest", desc: "All data encrypted with AES-256. API keys use envelope encryption with per-tenant keys." },
                { title: "Encryption in Transit", desc: "TLS 1.3 for all connections. HSTS enforced. Certificate transparency monitoring." },
                { title: "API Key Isolation", desc: "Credentials are never logged, never sent to LLM providers, and never exposed in agent outputs." },
                { title: "Rate Limiting", desc: "Per-user, per-agent rate limits prevent abuse. Circuit breakers protect third-party APIs." },
                { title: "Audit Logging", desc: "Every agent action, tool call, and API request is logged with timestamps and user attribution." },
                { title: "Content Security", desc: "CSP headers, X-Frame-Options, CORS restrictions, and input sanitization on all endpoints." },
                { title: "Autonomy Controls", desc: "Configurable approval gates for spending, outreach, and infrastructure actions." },
                { title: "Multi-Tenant Isolation", desc: "Campaign data is isolated per tenant. No cross-tenant data leakage." },
              ].map((item) => (
                <div key={item.title} className="p-5 rounded-xl border border-surface-200">
                  <h3 className="font-semibold text-sm text-surface-900 mb-1">{item.title}</h3>
                  <p className="text-xs text-surface-500">{item.desc}</p>
                </div>
              ))}
            </div>

            <div>
              <h2 className="font-semibold text-surface-900 text-base mb-2">Responsible AI</h2>
              <p>Agent outputs are validated through quality gates. Outbound communications (emails, social posts) can be configured to require human approval before sending. Spending actions have configurable thresholds.</p>
            </div>

            <div>
              <h2 className="font-semibold text-surface-900 text-base mb-2">Reporting Vulnerabilities</h2>
              <p>If you discover a security vulnerability, please report it to security@omnios.ai. We respond to all reports within 24 hours.</p>
            </div>
          </div>
        </div>
      </section>

      <footer className="border-t border-surface-100 py-10 px-6">
        <div className="max-w-6xl mx-auto flex items-center justify-between text-xs text-surface-400">
          <span>&copy; {new Date().getFullYear()} Omni OS Inc.</span>
          <div className="flex gap-6">
            <Link href="/" className="hover:text-surface-600">Home</Link>
            <Link href="/privacy" className="hover:text-surface-600">Privacy</Link>
            <Link href="/terms" className="hover:text-surface-600">Terms</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
