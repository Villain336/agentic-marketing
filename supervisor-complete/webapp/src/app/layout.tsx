import type { Metadata } from "next";
import "./globals.css";
import { ThemeToggle } from "@/components/theme-toggle";

export const metadata: Metadata = {
  title: {
    default: "Omni OS — AI Operating System for Founders",
    template: "%s | Omni OS",
  },
  description:
    "44 autonomous AI agents run your marketing, sales, finance, legal, and engineering. Real APIs. Real execution. Not wrappers.",
  keywords: [
    "AI agents",
    "business automation",
    "AI operating system",
    "marketing automation",
    "sales automation",
    "AI SaaS",
    "autonomous agents",
    "Claude AI",
    "founder tools",
  ],
  openGraph: {
    title: "Omni OS — AI Operating System for Founders",
    description:
      "44 autonomous AI agents run your entire business. Real APIs. Real execution.",
    type: "website",
    siteName: "Omni OS",
  },
  twitter: {
    card: "summary_large_image",
    title: "Omni OS — AI Operating System for Founders",
    description: "44 AI agents. One platform. Your entire business, automated.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="scroll-smooth" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var theme = localStorage.getItem('omni_theme');
                  if (theme === 'dark' || (!theme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
                    document.documentElement.classList.add('dark');
                  } else {
                    document.documentElement.classList.remove('dark');
                  }
                } catch(e) {}
              })();
            `,
          }}
        />
      </head>
      <body className="min-h-screen bg-surface-0 text-surface-900 antialiased transition-colors duration-200">
        <ThemeToggle />
        {children}
      </body>
    </html>
  );
}
