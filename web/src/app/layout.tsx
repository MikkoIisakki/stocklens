import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { loadDomainConfig } from "@/lib/domain";

export function generateMetadata(): Metadata {
  const cfg = loadDomainConfig();
  return {
    title: cfg.display_name,
    description: cfg.description,
  };
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const cfg = loadDomainConfig();
  return (
    <html lang="en">
      <body>
        <header className="bg-brand text-brand-fg">
          <nav className="mx-auto flex max-w-5xl items-center gap-6 px-4 py-3">
            <Link href="/" className="text-lg font-semibold">
              {cfg.display_name}
            </Link>
            <ul className="flex gap-4 text-sm">
              <li>
                <Link href="/" className="hover:underline">
                  Prices
                </Link>
              </li>
              <li>
                <Link href="/cheap-intervals" className="hover:underline">
                  Cheap intervals
                </Link>
              </li>
              <li>
                <Link href="/alerts" className="hover:underline">
                  Alerts
                </Link>
              </li>
            </ul>
            <span className="ml-auto text-xs opacity-80">{cfg.default_region}</span>
          </nav>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
