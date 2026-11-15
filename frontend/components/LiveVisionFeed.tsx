"use client";

import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { playSound } from "@/lib/sound";

interface LiveVisionFeedProps {
  initialHeadcount?: number;
  areaSqm?: number;
  alarmThreshold?: number;
}

export function LiveVisionFeed({
  initialHeadcount = 142,
  areaSqm = 150.0,
  alarmThreshold = 0.85,
}: LiveVisionFeedProps) {
  const [headcount, setHeadcount] = useState(initialHeadcount);
  const [viewMode, setViewMode] = useState<"dual" | "rgb" | "depth">("dual");
  const [isPlaying, setIsPlaying] = useState(true);
  const [fps, setFps] = useState(29.8);
  const [snapshotNotice, setSnapshotNotice] = useState<string | null>(null);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animFrameId = useRef<number | null>(null);

  // Computed metrics
  const density = headcount / areaSqm;
  const isOverThreshold = density >= alarmThreshold;
  const deltaPercent = ((density - alarmThreshold) / alarmThreshold) * 100;

  // Render animated canvas stream
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let ctx: CanvasRenderingContext2D | null = null;
    try {
      ctx = canvas.getContext ? canvas.getContext("2d") : null;
    } catch {
      return;
    }
    if (!ctx) return;

    let tick = 0;

    const render = () => {
      if (isPlaying) {
        tick++;
        // Minor realistic FPS oscillation around 30 FPS
        if (tick % 20 === 0) {
          setFps(+(29.4 + Math.sin(tick * 0.05) * 0.6).toFixed(1));
        }
      }

      const w = canvas.width;
      const h = canvas.height;

      ctx.clearRect(0, 0, w, h);

      // Determine view layout
      if (viewMode === "dual") {
        const halfW = w / 2;

        // --- LEFT HALF: RGB + YOLOv11 ---
        ctx.save();
        ctx.beginPath();
        ctx.rect(0, 0, halfW, h);
        ctx.clip();

        // Background platform floor
        ctx.fillStyle = "#111822";
        ctx.fillRect(0, 0, halfW, h);

        // Platform yellow caution stripe
        ctx.fillStyle = "#F59E0B";
        ctx.fillRect(0, h - 22, halfW, 6);
        ctx.fillStyle = "#1E293B";
        for (let i = 0; i < halfW; i += 20) {
          ctx.beginPath();
          ctx.moveTo(i, h - 22);
          ctx.lineTo(i + 10, h - 16);
          ctx.lineTo(i + 5, h - 16);
          ctx.lineTo(i - 5, h - 22);
          ctx.fill();
        }

        // Draw track area below caution line
        ctx.fillStyle = "#090D12";
        ctx.fillRect(0, h - 16, halfW, 16);

        // Platform area text
        ctx.fillStyle = "#475569";
        ctx.font = "9px monospace";
        ctx.fillText("BANCHINA L2 GARIBALDI - AREA 150m²", 10, 20);

        // Render simulated people bounding boxes
        const displayBoxesCount = Math.min(Math.round(headcount / 7), 26);
        for (let i = 0; i < displayBoxesCount; i++) {
          const seed = i * 47.3 + (isPlaying ? Math.sin(tick * 0.02 + i) * 3 : 0);
          const px = 15 + ((seed * 37) % (halfW - 55));
          const py = 35 + ((seed * 19) % (h - 75));
          const pw = 18 + ((seed * 7) % 10);
          const ph = 32 + ((seed * 11) % 16);

          // Person bounding box
          const boxColor = isOverThreshold ? "#EF4444" : "#10B981";
          ctx.strokeStyle = boxColor;
          ctx.lineWidth = 1.5;
          ctx.strokeRect(px, py, pw, ph);

          // Head circle
          ctx.fillStyle = isOverThreshold ? "rgba(239, 68, 68, 0.4)" : "rgba(16, 185, 129, 0.4)";
          ctx.beginPath();
          ctx.arc(px + pw / 2, py + 6, 4, 0, Math.PI * 2);
          ctx.fill();

          // YOLO confidence pill
          ctx.fillStyle = boxColor;
          ctx.fillRect(px, py - 11, 48, 10);
          ctx.fillStyle = "#000000";
          ctx.font = "bold 8px monospace";
          const conf = (0.78 + (i % 20) * 0.01).toFixed(2);
          ctx.fillText(`person ${conf}`, px + 2, py - 3);
        }

        // Overlay camera label
        ctx.fillStyle = "#38BDF8";
        ctx.font = "bold 10px monospace";
        ctx.fillText("CAM_02 [RGB + YOLOv11 FP16]", 10, h - 28);

        ctx.restore();

        // Divider
        ctx.strokeStyle = "#334155";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(halfW, 0);
        ctx.lineTo(halfW, h);
        ctx.stroke();

        // --- RIGHT HALF: DEPTH COLORMAP (Z16) ---
        ctx.save();
        ctx.beginPath();
        ctx.rect(halfW, 0, halfW, h);
        ctx.clip();

        // Depth background gradient (deep indigo -> teal -> yellow -> red)
        const depthGrad = ctx.createLinearGradient(halfW, 0, halfW, h);
        depthGrad.addColorStop(0, "#081028"); // far (4.5m)
        depthGrad.addColorStop(0.5, "#0D3850"); // mid (3.0m)
        depthGrad.addColorStop(0.8, "#854D0E"); // closer (2.0m)
        depthGrad.addColorStop(1, "#7F1D1D"); // critical platform edge (1.0m)
        ctx.fillStyle = depthGrad;
        ctx.fillRect(halfW, 0, halfW, h);

        // Render depth clusters for people
        for (let i = 0; i < displayBoxesCount; i++) {
          const seed = i * 47.3 + (isPlaying ? Math.sin(tick * 0.02 + i) * 3 : 0);
          const px = halfW + 15 + ((seed * 37) % (halfW - 55));
          const py = 35 + ((seed * 19) % (h - 75));
          const pw = 18 + ((seed * 7) % 10);
          const ph = 32 + ((seed * 11) % 16);

          // Thermal hotspot
          const radGrad = ctx.createRadialGradient(
            px + pw / 2,
            py + ph / 2,
            2,
            px + pw / 2,
            py + ph / 2,
            pw
          );
          radGrad.addColorStop(0, "#FDE047");
          radGrad.addColorStop(0.5, "#F97316");
          radGrad.addColorStop(1, "transparent");
          ctx.fillStyle = radGrad;
          ctx.beginPath();
          ctx.arc(px + pw / 2, py + ph / 2, pw * 1.2, 0, Math.PI * 2);
          ctx.fill();

          // Distance tag
          ctx.fillStyle = "#E2E8F0";
          ctx.font = "8px monospace";
          const dist = (1.2 + (seed % 3.0)).toFixed(1);
          ctx.fillText(`${dist}m`, px, py + ph + 8);
        }

        ctx.fillStyle = "#F59E0B";
        ctx.font = "bold 10px monospace";
        ctx.fillText("RealSense D435i [DEPTH z16 JET]", halfW + 10, h - 28);

        ctx.restore();
      } else if (viewMode === "rgb") {
        // Full RGB mode
        ctx.fillStyle = "#111822";
        ctx.fillRect(0, 0, w, h);

        ctx.fillStyle = "#F59E0B";
        ctx.fillRect(0, h - 25, w, 6);

        const displayBoxesCount = Math.min(Math.round(headcount / 5), 36);
        for (let i = 0; i < displayBoxesCount; i++) {
          const seed = i * 47.3 + (isPlaying ? Math.sin(tick * 0.02 + i) * 3 : 0);
          const px = 20 + ((seed * 43) % (w - 70));
          const py = 35 + ((seed * 23) % (h - 80));
          const pw = 22 + ((seed * 7) % 12);
          const ph = 40 + ((seed * 11) % 18);

          const boxColor = isOverThreshold ? "#EF4444" : "#10B981";
          ctx.strokeStyle = boxColor;
          ctx.lineWidth = 1.5;
          ctx.strokeRect(px, py, pw, ph);

          ctx.fillStyle = boxColor;
          ctx.fillRect(px, py - 12, 54, 11);
          ctx.fillStyle = "#000000";
          ctx.font = "bold 8px monospace";
          const conf = (0.75 + (i % 24) * 0.01).toFixed(2);
          ctx.fillText(`person ${conf}`, px + 2, py - 3);
        }

        ctx.fillStyle = "#38BDF8";
        ctx.font = "bold 11px monospace";
        ctx.fillText("CAM_02 [RGB + Ultralytics YOLOv11 NMS]", 12, h - 32);
      } else {
        // Full Depth mode
        const depthGrad = ctx.createLinearGradient(0, 0, 0, h);
        depthGrad.addColorStop(0, "#081028");
        depthGrad.addColorStop(0.5, "#0D3850");
        depthGrad.addColorStop(0.8, "#854D0E");
        depthGrad.addColorStop(1, "#7F1D1D");
        ctx.fillStyle = depthGrad;
        ctx.fillRect(0, 0, w, h);

        const displayBoxesCount = Math.min(Math.round(headcount / 5), 36);
        for (let i = 0; i < displayBoxesCount; i++) {
          const seed = i * 47.3 + (isPlaying ? Math.sin(tick * 0.02 + i) * 3 : 0);
          const px = 20 + ((seed * 43) % (w - 70));
          const py = 35 + ((seed * 23) % (h - 80));
          const pw = 22 + ((seed * 7) % 12);

          const radGrad = ctx.createRadialGradient(
            px + pw / 2,
            py + pw / 2,
            2,
            px + pw / 2,
            py + pw / 2,
            pw * 1.5
          );
          radGrad.addColorStop(0, "#FDE047");
          radGrad.addColorStop(0.5, "#F97316");
          radGrad.addColorStop(1, "transparent");
          ctx.fillStyle = radGrad;
          ctx.beginPath();
          ctx.arc(px + pw / 2, py + pw / 2, pw * 1.5, 0, Math.PI * 2);
          ctx.fill();

          ctx.fillStyle = "#E2E8F0";
          ctx.font = "9px monospace";
          const dist = (0.8 + (seed % 3.5)).toFixed(1);
          ctx.fillText(`${dist}m`, px, py + pw * 2);
        }

        ctx.fillStyle = "#F59E0B";
        ctx.font = "bold 11px monospace";
        ctx.fillText("Intel RealSense D435i [Depth z16 Colormap]", 12, h - 32);
      }

      // Draw top telemetric heads-up strip
      ctx.fillStyle = "rgba(11, 16, 22, 0.85)";
      ctx.fillRect(0, 0, w, 22);
      ctx.fillStyle = "#94A3B8";
      ctx.font = "9px monospace";
      ctx.fillText(
        `FPS: ${fps} | HARDWARE: CUDA:0 (NVIDIA) | RESOLUTION: 640x480 | GATING: [0.5m - 4.5m]`,
        10,
        14
      );

      // Status indicator dot
      ctx.beginPath();
      ctx.arc(w - 14, 11, 4, 0, Math.PI * 2);
      ctx.fillStyle = isPlaying ? "#22C55E" : "#EAB308";
      ctx.fill();

      animFrameId.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      if (animFrameId.current) {
        cancelAnimationFrame(animFrameId.current);
      }
    };
  }, [headcount, viewMode, isPlaying, isOverThreshold, fps]);

  const handleSaveSnapshot = () => {
    playSound("click");
    const canvas = canvasRef.current;
    if (!canvas) return;
    const filename = `capture_${Math.floor(Date.now() / 1000)}.png`;
    const link = document.createElement("a");
    link.download = filename;
    link.href = canvas.toDataURL("image/png");
    link.click();
    setSnapshotNotice(`Salvato: ${filename}`);
    setTimeout(() => setSnapshotNotice(null), 3000);
  };

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = Number(e.target.value);
    setHeadcount(val);
    const newDensity = val / areaSqm;
    if (newDensity >= alarmThreshold && density < alarmThreshold) {
      playSound("alert");
    }
  };

  return (
    <div
      className="space-y-4 rounded-[10px] border border-[var(--border)] bg-[#0B1016] p-4 text-[#E6EDF3]"
      data-testid="live-vision-feed"
    >
      {/* Title & View Selector Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#22303D] pb-3">
        <div className="flex items-center gap-2">
          <span className="flex h-2.5 w-2.5 relative">
            <span
              className={clsx(
                "animate-ping absolute inline-flex h-full w-full rounded-full opacity-75",
                isPlaying ? "bg-[#3FB950]" : "bg-[#D29922]"
              )}
            />
            <span
              className={clsx(
                "relative inline-flex rounded-full h-2.5 w-2.5",
                isPlaying ? "bg-[#2EA043]" : "bg-[#D29922]"
              )}
            />
          </span>
          <h4 className="text-[12px] font-semibold tracking-wide text-white">
            FEED OTTICO REALSENSE & INFERENZA YOLOv11
          </h4>
        </div>

        {/* View mode toggle */}
        <div className="flex items-center rounded-[6px] border border-[#30363D] bg-[#161F2C] p-0.5 text-[11px]">
          <button
            type="button"
            onClick={() => setViewMode("dual")}
            className={clsx(
              "rounded-[4px] px-2 py-0.5 font-medium transition-colors",
              viewMode === "dual" ? "bg-[#58A6FF] text-black font-semibold" : "text-[#8B949E] hover:text-white"
            )}
          >
            Dual (RGB+Depth)
          </button>
          <button
            type="button"
            onClick={() => setViewMode("rgb")}
            className={clsx(
              "rounded-[4px] px-2 py-0.5 font-medium transition-colors",
              viewMode === "rgb" ? "bg-[#58A6FF] text-black font-semibold" : "text-[#8B949E] hover:text-white"
            )}
          >
            RGB + YOLO
          </button>
          <button
            type="button"
            onClick={() => setViewMode("depth")}
            className={clsx(
              "rounded-[4px] px-2 py-0.5 font-medium transition-colors",
              viewMode === "depth" ? "bg-[#58A6FF] text-black font-semibold" : "text-[#8B949E] hover:text-white"
            )}
          >
            Depth (z16)
          </button>
        </div>
      </div>

      {/* Visual Canvas */}
      <div className="relative overflow-hidden rounded-[8px] border border-[#30363D] bg-[#05080C] shadow-inner">
        <canvas
          ref={canvasRef}
          width={580}
          height={240}
          className="w-full h-auto block aspect-[580/240]"
        />

        {/* Controls Overlay bar */}
        <div className="absolute bottom-2 right-2 flex items-center gap-1.5 bg-[#0B1016]/80 backdrop-blur-sm p-1 rounded-[6px] border border-[#30363D] text-[11px]">
          <button
            type="button"
            onClick={() => setIsPlaying(!isPlaying)}
            className="rounded px-2 py-0.5 font-mono text-[#58A6FF] hover:bg-[#161F2C]"
            title={isPlaying ? "Metti in pausa simulazione" : "Avvia simulazione"}
          >
            {isPlaying ? "⏸ Pausa" : "▶ Play"}
          </button>
          <button
            type="button"
            onClick={handleSaveSnapshot}
            className="rounded px-2 py-0.5 font-mono text-[#C9D1D9] hover:bg-[#161F2C]"
            title="Salva snapshot frame (come tasto 'S' in yolo_realsense.py)"
          >
            📷 Snapshot
          </button>
        </div>

        {snapshotNotice && (
          <div className="absolute top-8 left-3 rounded bg-[#238636] px-2 py-1 text-[11px] font-mono text-white shadow-lg animate-fade-in">
            {snapshotNotice}
          </div>
        )}
      </div>

      {/* Interactive Calibration & Headcount Slider */}
      <div className="space-y-3 rounded-[8px] border border-[#22303D] bg-[#121820] p-3.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[#8B949E]">
              SIMULATORE DI AFFLUSSO BANCHINA (IN REAL-TIME)
            </span>
            <p className="text-[11px] text-[#8B949E]">
              Modifica il conteggio persone per testare la risposta della soglia di sicurezza:
            </p>
          </div>
          <div className="font-mono text-[14px] font-bold text-white flex items-center gap-1">
            <span className="text-[#58A6FF]">{headcount}</span>
            <span className="text-[11px] text-[#8B949E]">persone rilevate</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="font-mono text-[11px] text-[#8B949E]">30</span>
          <input
            type="range"
            min={30}
            max={220}
            step={1}
            value={headcount}
            onChange={handleSliderChange}
            className="flex-1 accent-[#58A6FF] h-1.5 cursor-pointer rounded-lg bg-[#30363D]"
            aria-label="Regola conteggio persone simulate"
          />
          <span className="font-mono text-[11px] text-[#8B949E]">220</span>
        </div>

        {/* Dynamic Metric Readout */}
        <div className="grid grid-cols-3 gap-2 pt-1 font-mono text-[12px]">
          <div className="rounded border border-[#30363D] bg-[#0B1016] p-2">
            <span className="block text-[10px] text-[#8B949E] uppercase">Densità Calcolata</span>
            <span
              className={clsx(
                "text-[14px] font-bold",
                isOverThreshold ? "text-[#F85149]" : density >= 0.7 ? "text-[#D29922]" : "text-[#3FB950]"
              )}
            >
              {density.toFixed(2)} p/m²
            </span>
          </div>

          <div className="rounded border border-[#30363D] bg-[#0B1016] p-2">
            <span className="block text-[10px] text-[#8B949E] uppercase">Soglia di Sicurezza</span>
            <span className="text-[14px] font-bold text-[#8B949E]">{alarmThreshold.toFixed(2)} p/m²</span>
          </div>

          <div className="rounded border border-[#30363D] bg-[#0B1016] p-2">
            <span className="block text-[10px] text-[#8B949E] uppercase">Stato Regola R1</span>
            <span
              className={clsx(
                "text-[12px] font-bold",
                isOverThreshold ? "text-[#F85149]" : density >= 0.7 ? "text-[#D29922]" : "text-[#3FB950]"
              )}
            >
              {isOverThreshold ? `ALLARME (+${deltaPercent.toFixed(0)}%)` : density >= 0.7 ? "PRE-ALLERTA" : "NOMINALE"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
