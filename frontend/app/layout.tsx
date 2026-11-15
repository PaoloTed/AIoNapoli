import type { Metadata } from "next";
import "mapbox-gl/dist/mapbox-gl.css";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "AIoNapoli — Napoli Agentic City",
  description:
    "Decisioni deterministiche con provenienza dichiarata per operatore, turista e cittadino.",
  icons: { icon: "/brand/icon-aionapoli.svg" },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="it">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
