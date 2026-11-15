import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "mapbox-gl/dist/mapbox-gl.css";
import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-inter",
  display: "swap",
});

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#0B1016" },
    { media: "(prefers-color-scheme: light)", color: "#FAFAF8" },
  ],
};

export const metadata: Metadata = {
  title: "Napoli Agentic City — Mission Control & Decision Intelligence",
  description:
    "Piattaforma multi-agente deterministica per la mobilità e la gestione eventi a Napoli. Integrazione con sensori ottici Intel RealSense, YOLOv11, GTFS-RT e audit trail crittografico SHA-256.",
  applicationName: "Napoli Agentic City",
  authors: [{ name: "Comune di Napoli / CdS Hackathon 2026 Team" }],
  keywords: [
    "Napoli",
    "Mobilità Intelligente",
    "Smart City",
    "Agentic AI",
    "Deterministico",
    "Intel RealSense",
    "YOLOv11",
    "OpenTripPlanner",
    "GTFS-RT",
    "Audit Trail",
  ],
  openGraph: {
    title: "Napoli Agentic City — Mission Control & Decision Intelligence",
    description:
      "Decisioni di mobilità ed emergenza deterministiche al 100% con tracciabilità crittografica e zero allucinazioni.",
    type: "website",
    locale: "it_IT",
    siteName: "Napoli Agentic City",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="it" className={inter.variable}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
