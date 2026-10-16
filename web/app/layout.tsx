import type { Metadata } from "next";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import "./globals.css";

// Read the legacy app address at request time, including on error/404 pages.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: { default: "Echo Madrid", template: "%s | Echo Madrid" },
  description:
    "Real Madrid in focus. Explore standings, fixtures, and results grounded in stored football data.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main-content">
          Skip to content
        </a>
        <Header />
        <main id="main-content">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
