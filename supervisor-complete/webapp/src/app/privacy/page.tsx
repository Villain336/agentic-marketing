import type { Metadata } from "next";
import Link from "next/link";
import { OmniLogo } from "@/components/ui/omni-logo";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "Omni OS privacy policy. How we handle your data.",
};

export default function PrivacyPage() {
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
          <div className="mono-label mb-3">Legal</div>
          <h1 className="font-display font-bold text-3xl text-surface-900 mb-2">Privacy Policy</h1>
          <p className="text-sm text-surface-400 mb-10">Last updated: March 2026</p>

          <div className="space-y-8 text-sm text-surface-600 leading-relaxed">
            <div>
              <h2 className="font-semibold text-surface-900 text-base mb-2">1. Information We Collect</h2>
              <p>We collect information you provide directly: account details (name, email), business profile data entered during onboarding, and usage data from agent interactions. We also collect technical data: IP address, browser type, and device information.</p>
            </div>
            <div>
              <h2 className="font-semibold text-surface-900 text-base mb-2">2. How We Use Your Information</h2>
              <p>Your data powers your AI agents. Business profiles inform agent behavior. We use usage data to improve agent performance and platform reliability. We never sell your data to third parties.</p>
            </div>
            <div>
              <h2 className="font-semibold text-surface-900 text-base mb-2">3. Third-Party Integrations</h2>
              <p>When you connect third-party services (Apollo, SendGrid, Stripe, etc.), your API keys are encrypted at rest. Agents interact with these services on your behalf using your credentials. We do not store data returned from third-party APIs beyond your campaign memory.</p>
            </div>
            <div>
              <h2 className="font-semibold text-surface-900 text-base mb-2">4. AI Model Usage</h2>
              <p>Your prompts and agent interactions are processed by LLM providers (Anthropic, OpenAI, Google). We do not use your data to train AI models. Each provider&apos;s data handling is governed by their respective privacy policies.</p>
            </div>
            <div>
              <h2 className="font-semibold text-surface-900 text-base mb-2">5. Data Retention</h2>
              <p>Campaign data is retained for the duration of your subscription plus 30 days. You can request data deletion at any time by contacting support.</p>
            </div>
            <div>
              <h2 className="font-semibold text-surface-900 text-base mb-2">6. Security</h2>
              <p>All data is encrypted in transit (TLS 1.3) and at rest (AES-256). API keys are stored using envelope encryption. We undergo regular security audits.</p>
            </div>
            <div>
              <h2 className="font-semibold text-surface-900 text-base mb-2">7. Contact</h2>
              <p>For privacy inquiries, contact privacy@omnios.ai.</p>
            </div>
          </div>
        </div>
      </section>

      <footer className="border-t border-surface-100 py-10 px-6">
        <div className="max-w-6xl mx-auto flex items-center justify-between text-xs text-surface-400">
          <span>&copy; {new Date().getFullYear()} Omni OS Inc.</span>
          <div className="flex gap-6">
            <Link href="/" className="hover:text-surface-600">Home</Link>
            <Link href="/terms" className="hover:text-surface-600">Terms</Link>
            <Link href="/security" className="hover:text-surface-600">Security</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
