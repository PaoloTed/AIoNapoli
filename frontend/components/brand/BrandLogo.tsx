/**
 * @purpose Componente ufficiale del marchio AIoNapoli (icona, logo completo, wordmark)
 * @contracts nessuno
 * @tokens shared
 * @verified 2026-11-15
 */

import Image from "next/image";

type Variant = "icon" | "full" | "full-light" | "wordmark";

const ASSETS: Record<Variant, { src: string; ratio: number }> = {
  icon: { src: "/brand/icon-aionapoli.svg", ratio: 1 },
  full: { src: "/brand/logo-aionapoli.svg", ratio: 924 / 250 },
  "full-light": { src: "/brand/logo-aionapoli-light.svg", ratio: 924 / 250 },
  wordmark: { src: "/brand/wordmark-aionapoli.svg", ratio: 654.5 / 174.2 },
};

export function BrandLogo({
  variant = "icon",
  height = 32,
  priority = false,
}: {
  variant?: Variant;
  height?: number;
  priority?: boolean;
}) {
  const asset = ASSETS[variant];
  const width = Math.round(height * asset.ratio);

  return (
    <Image
      src={asset.src}
      alt="AIoNapoli"
      width={width}
      height={height}
      priority={priority}
      unoptimized
      draggable={false}
      style={{ display: "block", height: `${height}px`, width: `${width}px` }}
    />
  );
}
