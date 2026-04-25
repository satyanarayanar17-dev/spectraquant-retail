import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";

import "./globals.css";
import copy from "@/lib/copy.json";
import { AppProviders } from "@/components/AppProviders";
import { DisclaimerBanner } from "@/components/DisclaimerBanner";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter"
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono"
});

export const metadata: Metadata = {
  title: copy.brand.name,
  description: copy.brand.tagline
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-theme="dark">
      <body className={`${inter.variable} ${jetbrainsMono.variable}`}>
        <AppProviders>
          <div className="mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-6 sm:px-6 lg:px-8">
            <header className="mb-8 flex items-center justify-between rounded-2xl border border-border-subtle bg-surface/80 px-5 py-4 backdrop-blur">
              <div>
                <p className="text-xs uppercase tracking-[0.24em] text-tertiary">SpectraQuant</p>
                <h1 className="mt-1 text-lg font-semibold text-primary">{copy.brand.name}</h1>
              </div>
              <p className="hidden text-sm text-secondary sm:block">{copy.brand.tagline}</p>
            </header>
            <main className="flex-1">{children}</main>
            <footer className="mt-8 space-y-3">
              <DisclaimerBanner />
              <p className="text-xs text-tertiary">{copy.footer.disclaimer}</p>
            </footer>
          </div>
        </AppProviders>
      </body>
    </html>
  );
}
