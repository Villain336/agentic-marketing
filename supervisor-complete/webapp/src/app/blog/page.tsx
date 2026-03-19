import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Blog",
  description: "Omni OS blog. AI agents, automation, and founder tools.",
};

export default function BlogPage() {
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
          <Link href="/auth?mode=signup" className="btn-primary">Get Started</Link>
        </div>
      </nav>

      <section className="pt-32 pb-20 px-6">
        <div className="max-w-3xl mx-auto">
          <div className="mono-label mb-3">Blog</div>
          <h1 className="font-display font-bold text-3xl text-surface-900 mb-10">
            Latest from Omni OS
          </h1>

          <div className="space-y-8">
            {[
              {
                title: "Why AI Wrappers Are Dead",
                excerpt: "The market is flooded with products that slap a ChatGPT interface on top of an API and call it automation. Real AI agents execute — they don't suggest.",
                date: "March 2026",
                tag: "Product",
              },
              {
                title: "The Revenue Loop: How 3 Agents Replace Your Sales Team",
                excerpt: "Prospector finds leads via Apollo, Outreach sends sequences via SendGrid, Billing collects via Stripe. The complete autonomous revenue cycle.",
                date: "March 2026",
                tag: "Guide",
              },
              {
                title: "Introducing Claude AI Code Engine",
                excerpt: "Every Omni OS agent can now generate, review, and deploy production code using the Claude Agent SDK. Here's how we built it.",
                date: "March 2026",
                tag: "Engineering",
              },
            ].map((post) => (
              <article key={post.title} className="p-6 rounded-xl border border-surface-200 hover:border-surface-300 transition-colors">
                <div className="flex items-center gap-3 mb-3">
                  <span className="badge bg-surface-100 text-surface-600">{post.tag}</span>
                  <span className="text-xs text-surface-400">{post.date}</span>
                </div>
                <h2 className="font-semibold text-lg text-surface-900 mb-2">{post.title}</h2>
                <p className="text-sm text-surface-500 leading-relaxed">{post.excerpt}</p>
              </article>
            ))}
          </div>

          <p className="text-center text-sm text-surface-400 mt-12">
            More posts coming soon. Follow us for updates.
          </p>
        </div>
      </section>

      <footer className="border-t border-surface-100 py-10 px-6">
        <div className="max-w-6xl mx-auto flex items-center justify-between text-xs text-surface-400">
          <span>&copy; {new Date().getFullYear()} Omni OS Inc.</span>
          <div className="flex gap-6">
            <Link href="/" className="hover:text-surface-600">Home</Link>
            <Link href="/features" className="hover:text-surface-600">Features</Link>
            <Link href="/about" className="hover:text-surface-600">About</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
