import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Careers",
  description: "Join the Omni OS team. Build the AI operating system for founders.",
};

export default function CareersPage() {
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
          <div className="mono-label mb-3">Careers</div>
          <h1 className="font-display font-bold text-3xl text-surface-900 mb-4">
            Build the future of work
          </h1>
          <p className="text-surface-500 mb-10">
            We&apos;re building an AI operating system that replaces entire departments.
            If that excites you, we want to talk.
          </p>

          <div className="p-8 rounded-xl border border-surface-200 text-center">
            <p className="text-surface-500 mb-4">
              No open positions right now. We&apos;re a lean team shipping fast.
            </p>
            <p className="text-sm text-surface-400">
              Interested anyway? Email <span className="text-surface-900 font-medium">careers@omnios.ai</span>
            </p>
          </div>
        </div>
      </section>

      <footer className="border-t border-surface-100 py-10 px-6">
        <div className="max-w-6xl mx-auto flex items-center justify-between text-xs text-surface-400">
          <span>&copy; {new Date().getFullYear()} Omni OS Inc.</span>
          <div className="flex gap-6">
            <Link href="/" className="hover:text-surface-600">Home</Link>
            <Link href="/about" className="hover:text-surface-600">About</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
