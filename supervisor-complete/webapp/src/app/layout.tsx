import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Supervisor — AI Operating System for Founders",
  description: "44 AI agents. One platform. Your entire business, automated.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="scroll-smooth">
      <body className="min-h-screen bg-white antialiased">{children}</body>
    </html>
  );
}
