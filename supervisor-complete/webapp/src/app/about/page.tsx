import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "About",
  description: "Omni OS is the AI operating system for founders who ship. 44 autonomous agents run your entire business.",
};

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-white">
      <nav className="fixed top-0 w-full z-50 bg-white border-b border-surface-100">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-surface-900 flex items-center justify-center">
              <span className="text-white font-bold text-sm font-mono">O</span>
            </div>
            <span className="font-display font-bold text-lg text-surface-900 tracking-tight">Omni OS</span>
          </Link>
          <div className="hidden md:flex items-center gap-8 text-sm text-surface-500">
            <Link href="/features" className="hover:text-surface-900 transition-colors">Features</Link>
            <Link href="/#pricing" className="hover:text-surface-900 transition-colors">Pricing</Link>
            <Link href="/about" className="text-surface-900 font-medium">About</Link>
          </div>
          <Link href="/auth?mode=signup" className="btn-primary">Get Started</Link>
        </div>
      </nav>

      <section className="pt-32 pb-20 px-6">
        <div className="max-w-3xl mx-auto">
          <div className="mono-label mb-3">About</div>
          <h1 className="font-display font-extrabold text-4xl md:text-5xl text-surface-900 leading-tight mb-6">
            We believe every founder
            <br />
            <span className="text-surface-400">deserves a full team.</span>
          </h1>

          <div className="space-y-6 text-surface-600 leading-relaxed">
            <p>
              Most founders start alone. They wear every hat — marketing, sales, finance, legal, engineering.
              They spend 80% of their time on operations and 20% on building what matters.
            </p>
            <p>
              Omni OS flips that ratio. 44 AI agents handle the operational work — finding leads, sending emails,
              managing finances, writing code, deploying sites — so founders can focus on vision and strategy.
            </p>
            <p>
              These aren&apos;t chatbots that generate text and hope you copy-paste it somewhere. Every agent has real
              API integrations. The Prospector agent calls Apollo to find actual contacts. The Outreach agent sends
              real emails through SendGrid. The Billing agent creates real Stripe invoices.
            </p>
            <p>
              We built Omni OS because we were tired of &ldquo;AI tools&rdquo; that create more work, not less.
              If an agent can&apos;t execute the task end-to-end, it&apos;s not an agent — it&apos;s a suggestion engine.
            </p>

            <div className="border-t border-surface-200 pt-8 mt-8">
              <h2 className="font-display font-bold text-xl text-surface-900 mb-4">What makes us different</h2>
              <ul className="space-y-3">
                {[
                  "Real execution — agents use APIs to take action, not just generate text",
                  "Claude AI Code Engine — every agent can write, review, and ship production code",
                  "Cloudflare web crawlers — real-time competitive intelligence",
                  "5 LLM providers with automatic failover — 99.9% uptime",
                  "Revenue loop — Prospector to Outreach to Billing runs autonomously",
                ].map((item) => (
                  <li key={item} className="flex items-start gap-2.5 text-sm">
                    <span className="text-surface-900 mt-0.5">&check;</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="mt-12 flex gap-3">
            <Link href="/auth?mode=signup" className="btn-primary">Start Free Trial</Link>
            <Link href="/features" className="btn-secondary">Explore Features</Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-surface-100 py-10 px-6">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <span className="text-xs text-surface-400">&copy; {new Date().getFullYear()} Omni OS Inc.</span>
          <div className="flex items-center gap-6 text-xs text-surface-400">
            <Link href="/" className="hover:text-surface-600">Home</Link>
            <Link href="/features" className="hover:text-surface-600">Features</Link>
            <Link href="/privacy" className="hover:text-surface-600">Privacy</Link>
            <Link href="/terms" className="hover:text-surface-600">Terms</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
