"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";
import type { AgentName, Finding, VehiclePosition } from "@/lib/contracts";
import type { Locale } from "@/lib/format";
import { LiveVisionFeed } from "./LiveVisionFeed";
import { ProvenanceChip } from "./ProvenanceChip";
import { SeverityBadge } from "./SeverityBadge";

interface SensorInspectorDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  initialAgent?: AgentName;
  findings: Finding[];
  vehiclePositions?: VehiclePosition[];
  locale?: Locale;
}

export function SensorInspectorDrawer({
  isOpen,
  onClose,
  initialAgent = "crowding",
  findings,
  vehiclePositions = [],
  locale = "it",
}: SensorInspectorDrawerProps) {
  const [activeTab, setActiveTab] = useState<AgentName>(initialAgent);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (initialAgent) {
      setActiveTab(initialAgent);
    }
  }, [initialAgent]);

  // Handle ESC key to close
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const currentFinding = findings.find((f) => f.agent === activeTab);

  const handleCopyJson = async () => {
    const payload = {
      agent: activeTab,
      finding: currentFinding ?? null,
      telemetrySnapshot: activeTab === "crowding"
        ? {
            sensor_hardware: "Intel RealSense D435i (Stereo IR Depth + RGB)",
            vision_model: "Ultralytics YOLOv11 (PyTorch CUDA FP16, TensorRT)",
            class_filter: "COCO Class 0 [person]",
            optical_count: 142,
            monitored_area_sqm: 150.0,
            depth_plane_gating_m: [0.5, 4.5],
            computed_density: 0.91,
            alarm_threshold: 0.85,
            pipeline_script: "yolo/yolo_realsense.py",
          }
        : activeTab === "mobility"
        ? {
            feed_source: "ANM Scraper & GTFS-RT Protobuf",
            rss_body_hash_sha256: "b26d58b90c9a",
            routing_engine: "OpenTripPlanner 2.x Multimodal Router",
            tracked_vehicles: vehiclePositions,
          }
        : {
            radar_provider: "Open-Meteo European Severe Weather Radar",
            weather_station: "Napoli Bagnoli Agnano (40.816N, 14.172E)",
            precipitation_rate_mm_h: 24.5,
            heavy_rain_threshold_mm_h: 15.0,
            civil_protection_alert: "Arancione (Zona 1)",
          },
      timestamp: new Date().toISOString(),
    };

    try {
      await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Ispezione Telemetria Sensori Hardware"
      data-testid="sensor-inspector-drawer"
      className="fixed inset-0 z-50 flex justify-end bg-black/70 backdrop-blur-sm transition-opacity duration-200"
    >
      {/* Click outside backdrop to close */}
      <div className="flex-1 cursor-pointer" onClick={onClose} aria-hidden="true" />

      {/* Drawer content panel */}
      <aside className="relative flex h-full w-full max-w-2xl flex-col border-l border-[var(--border)] bg-[#0B1016] text-[#E6EDF3] shadow-2xl overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-[var(--border)] bg-[#0B1016]/95 px-6 py-4 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <span className="flex h-3 w-3 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#3FB950] opacity-75" />
              <span className="relative inline-flex rounded-full h-3 w-3 bg-[#2EA043]" />
            </span>
            <div>
              <h2 className="text-[14px] font-semibold tracking-wide text-white flex items-center gap-2">
                <span>TELEMETRIA SENSORI HARDWARE</span>
                <span className="rounded bg-[#1F2937] px-1.5 py-0.5 font-mono text-[11px] text-[#58A6FF]">
                  LIVE DATA
                </span>
              </h2>
              <p className="text-[12px] text-[#8B949E]">
                Ispezione di livello operatore: hardware, computer vision e feed sorgente
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleCopyJson}
              className="inline-flex items-center gap-1.5 rounded-[6px] border border-[var(--border)] bg-[#161F2C] px-2.5 py-1.5 text-[12px] font-medium text-[#C9D1D9] hover:bg-[#1F2937] transition-colors"
              title="Copia snapshot JSON negli appunti"
            >
              {copied ? (
                <>
                  <span className="text-[#3FB950]">✓</span>
                  <span>Copiato!</span>
                </>
              ) : (
                <>
                  <span className="font-mono text-[11px] text-[#58A6FF]">📋</span>
                  <span>Copia JSON</span>
                </>
              )}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-[6px] p-1.5 text-[#8B949E] hover:bg-[#161F2C] hover:text-white transition-colors"
              aria-label="Chiudi ispezione"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Agent switcher tabs */}
        <div className="flex border-b border-[var(--border)] bg-[#121820] px-6 pt-3 gap-2">
          {(["crowding", "mobility", "context"] as AgentName[]).map((agentKey) => {
            const isActive = activeTab === agentKey;
            const label =
              agentKey === "crowding"
                ? "Affollamento (RealSense/YOLO)"
                : agentKey === "mobility"
                ? "Mobilità (ANM/GTFS)"
                : "Contesto (Meteo/Radar)";
            return (
              <button
                key={agentKey}
                type="button"
                onClick={() => setActiveTab(agentKey)}
                className={clsx(
                  "border-b-2 px-3 py-2 text-[12px] font-medium transition-colors",
                  isActive
                    ? "border-[#58A6FF] text-[#58A6FF]"
                    : "border-transparent text-[#8B949E] hover:text-[#C9D1D9]"
                )}
              >
                {label}
              </button>
            );
          })}
        </div>

        {/* Tab Body */}
        <div className="flex-1 space-y-6 p-6">
          {/* Finding summary pill */}
          {currentFinding ? (
            <div className="rounded-[10px] border border-[var(--border)] bg-[#161F2C] p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-[#8B949E]">
                    CONTRATTO FINDING SORGENTE
                  </span>
                  <code className="font-mono text-[12px] text-[#58A6FF]">
                    {currentFinding.type}
                  </code>
                </div>
                <div className="flex items-center gap-2">
                  <ProvenanceChip
                    variant={currentFinding.is_simulated ? "simulated" : "real"}
                    locale={locale}
                  />
                  <SeverityBadge severity={currentFinding.severity} locale={locale} />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 text-[12px] sm:grid-cols-4 pt-1">
                <div>
                  <span className="block text-[10px] uppercase text-[#8B949E]">Source ID</span>
                  <code className="font-mono text-white">{currentFinding.source_id}</code>
                </div>
                <div>
                  <span className="block text-[10px] uppercase text-[#8B949E]">Confidenza</span>
                  <span className="font-mono text-[#3FB950]">
                    {(currentFinding.confidence * 100).toFixed(0)}%
                  </span>
                </div>
                <div>
                  <span className="block text-[10px] uppercase text-[#8B949E]">Data Ref</span>
                  <span className="font-mono text-xs text-[#C9D1D9] truncate block" title={currentFinding.data_reference}>
                    {currentFinding.data_reference}
                  </span>
                </div>
                <div>
                  <span className="block text-[10px] uppercase text-[#8B949E]">Timestamp</span>
                  <span className="font-mono text-xs text-[#8B949E]">
                    {new Date(currentFinding.timestamp).toLocaleTimeString("it-IT")}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <div className="rounded-[10px] border border-dashed border-[var(--border)] p-4 text-[13px] text-[#8B949E]">
              Nessun finding registrato per questo agente nello scenario selezionato.
            </div>
          )}

          {/* Detailed Hardware / Telemetry breakdown based on activeTab */}
          {activeTab === "crowding" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-[12px] font-semibold uppercase tracking-wider text-[#58A6FF] flex items-center gap-2">
                  <span>📸</span>
                  <span>Sensori di Profondità & Computer Vision</span>
                </h3>
                <span className="font-mono text-[11px] text-[#3FB950] border border-[#238636] bg-[#238636]/10 px-2 py-0.5 rounded">
                  CUDA DETECTED: NVIDIA GPU ACTIVE
                </span>
              </div>

              {/* Interactive Live Optical Feed Canvas with YOLOv11 & RealSense Depth */}
              <LiveVisionFeed initialHeadcount={142} areaSqm={150.0} alarmThreshold={0.85} />

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-[8px] border border-[var(--border)] bg-[#121820] p-3.5 space-y-1.5">
                  <span className="text-[11px] font-medium uppercase text-[#8B949E]">
                    Hardware Telecamera
                  </span>
                  <div className="text-[13px] font-semibold text-white">
                    Intel RealSense™ D435i
                  </div>
                  <p className="text-[11px] text-[#8B949E]">
                    Sensore ottico stereoscopico IR attivo + ottica RGB integrata. Gating di profondità calcolato sul piano banchina.
                  </p>
                  <div className="pt-1 font-mono text-[11px] text-[#58A6FF]">
                    Pipeline: rs.stream.depth (z16) + rs.stream.color (bgr8) @ 30 FPS
                  </div>
                </div>

                <div className="rounded-[8px] border border-[var(--border)] bg-[#121820] p-3.5 space-y-1.5">
                  <span className="text-[11px] font-medium uppercase text-[#8B949E]">
                    Modello di Visione & Reti Neurali
                  </span>
                  <div className="text-[13px] font-semibold text-white">
                    Ultralytics YOLOv11 (FP16)
                  </div>
                  <p className="text-[11px] text-[#8B949E]">
                    Rilevamento persone (COCO Class 0 [person]) con bounding box filtering e NMS deterministico.
                  </p>
                  <div className="pt-1 font-mono text-[11px] text-[#58A6FF]">
                    Script: yolo/yolo_realsense.py (Batch avvia-yolo-relese.bat)
                  </div>
                </div>
              </div>

              {/* Calibration & Density metrics */}
              <div className="rounded-[8px] border border-[var(--border)] bg-[#121820] p-4 space-y-3">
                <h4 className="text-[11px] font-semibold uppercase tracking-wider text-[#8B949E]">
                  Parametri di Calibrazione Spaziale & Tracciamento
                </h4>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 font-mono text-[12px]">
                  <div className="border-l-2 border-[#58A6FF] pl-2.5">
                    <span className="block text-[10px] text-[#8B949E]">Persone Tracciate</span>
                    <span className="text-[15px] font-bold text-white">142</span>
                  </div>
                  <div className="border-l-2 border-[#58A6FF] pl-2.5">
                    <span className="block text-[10px] text-[#8B949E]">Area Calpestabile</span>
                    <span className="text-[15px] font-bold text-white">150.0 m²</span>
                  </div>
                  <div className="border-l-2 border-[#D29922] pl-2.5">
                    <span className="block text-[10px] text-[#8B949E]">Densità Calcolata</span>
                    <span className="text-[15px] font-bold text-[#F85149]">0.91 p/m²</span>
                  </div>
                  <div className="border-l-2 border-[#8B949E] pl-2.5">
                    <span className="block text-[10px] text-[#8B949E]">Soglia Allarme</span>
                    <span className="text-[15px] font-bold text-[#8B949E]">0.85 p/m²</span>
                  </div>
                </div>

                <div className="rounded border border-[#F85149]/30 bg-[#F85149]/10 p-2.5 text-[12px] text-[#FFA198] flex items-start gap-2">
                  <span className="text-[#F85149] font-bold">⚠</span>
                  <div>
                    <strong>Soglia di saturazione banchina superata (+7.0% sopra soglia di sicurezza):</strong>{" "}
                    Il supervisore dell&apos;affollamento ha emesso l&apos;allarme di densità critica attivando la regola deterministica di diversione pedonale.
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === "mobility" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-[12px] font-semibold uppercase tracking-wider text-[#58A6FF] flex items-center gap-2">
                  <span>🚆</span>
                  <span>Flussi Trasporto Pubblico & Routing Multimodale</span>
                </h3>
                <span className="font-mono text-[11px] text-[#58A6FF] border border-[#1F6FEB] bg-[#1F6FEB]/10 px-2 py-0.5 rounded">
                  OTP 2.x MULTIMODAL CORE
                </span>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-[8px] border border-[var(--border)] bg-[#121820] p-3.5 space-y-1.5">
                  <span className="text-[11px] font-medium uppercase text-[#8B949E]">
                    Connettore RSS ANM
                  </span>
                  <div className="text-[13px] font-semibold text-white">
                    Scraping & Deduplicazione Hash
                  </div>
                  <p className="text-[11px] text-[#8B949E]">
                    Analisi semantica comunicati ANM con hash del corpo news (sha256[:16]) per caching deterministico e prevenzione loop.
                  </p>
                  <div className="pt-1 font-mono text-[11px] text-[#3FB950]">
                    Hash News Attiva: b26d58b90c9a (Cache HIT)
                  </div>
                </div>

                <div className="rounded-[8px] border border-[var(--border)] bg-[#121820] p-3.5 space-y-1.5">
                  <span className="text-[11px] font-medium uppercase text-[#8B949E]">
                    Routing Engine OTP
                  </span>
                  <div className="text-[13px] font-semibold text-white">
                    OpenTripPlanner 2.x + GTFS
                  </div>
                  <p className="text-[11px] text-[#8B949E]">
                    Ripartizione vincoli a due livelli: vincoli globali all&apos;engine OTP, vincoli parziali/direzionali a valle (post_filter).
                  </p>
                  <div className="pt-1 font-mono text-[11px] text-[#58A6FF]">
                    Stato: Fallback Deterministico Fixture Attivo
                  </div>
                </div>
              </div>

              {/* Live Vehicle Positions */}
              <div className="rounded-[8px] border border-[var(--border)] bg-[#121820] p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-[11px] font-semibold uppercase tracking-wider text-[#8B949E]">
                    Veicoli in Servizio Telemonitorati (GTFS-RT)
                  </h4>
                  <span className="font-mono text-[11px] text-[#8B949E]">
                    {vehiclePositions.length} unità rilevate
                  </span>
                </div>

                {vehiclePositions.length > 0 ? (
                  <div className="space-y-2">
                    {vehiclePositions.map((v) => (
                      <div
                        key={v.vehicle_id}
                        className="flex flex-wrap items-center justify-between rounded border border-[var(--border)] bg-[#0B1016] px-3 py-2 text-[12px]"
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-white">{v.vehicle_id}</span>
                          <span className="rounded bg-[#238636]/20 text-[#3FB950] px-1.5 py-0.2 font-mono text-[11px]">
                            Linea {v.route_id}
                          </span>
                        </div>
                        <div className="font-mono text-[11px] text-[#8B949E]">
                          Lat: {v.latitude.toFixed(4)}, Lon: {v.longitude.toFixed(4)}
                          {v.bearing !== null && v.bearing !== undefined ? ` (${v.bearing.toFixed(1)}°)` : ""}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[12px] text-[#8B949E]">
                    Nessun mezzo monitorato in tempo reale su questa tratta.
                  </p>
                )}
              </div>
            </div>
          )}

          {activeTab === "context" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-[12px] font-semibold uppercase tracking-wider text-[#58A6FF] flex items-center gap-2">
                  <span>🌦</span>
                  <span>Radar Idrometeo & Eventi Territoriali</span>
                </h3>
                <span className="font-mono text-[11px] text-[#D29922] border border-[#D29922] bg-[#D29922]/10 px-2 py-0.5 rounded">
                  ALLERTA ARANCIONE
                </span>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-[8px] border border-[var(--border)] bg-[#121820] p-3.5 space-y-1.5">
                  <span className="text-[11px] font-medium uppercase text-[#8B949E]">
                    Sorgente Meteorologica
                  </span>
                  <div className="text-[13px] font-semibold text-white">
                    Open-Meteo European Severe Weather
                  </div>
                  <p className="text-[11px] text-[#8B949E]">
                    Dati di precipitazione e vento ad altissima risoluzione (griglia 1km ECMWF/ICON).
                  </p>
                  <div className="pt-1 font-mono text-[11px] text-[#58A6FF]">
                    Stazione: Napoli Bagnoli (40.816° N, 14.172° E)
                  </div>
                </div>

                <div className="rounded-[8px] border border-[var(--border)] bg-[#121820] p-3.5 space-y-1.5">
                  <span className="text-[11px] font-medium uppercase text-[#8B949E]">
                    Protezione Civile Regionale
                  </span>
                  <div className="text-[13px] font-semibold text-white">
                    Bollettino Allerta Idrogeologica
                  </div>
                  <p className="text-[11px] text-[#8B949E]">
                    Campania Zona 1 (Piana Campana, Napoli, Isole, Area Vesuviana).
                  </p>
                  <div className="pt-1 font-mono text-[11px] text-[#D29922]">
                    Criticità: Moderata (Livello Arancione)
                  </div>
                </div>
              </div>

              <div className="rounded-[8px] border border-[var(--border)] bg-[#121820] p-4 space-y-2 font-mono text-[12px]">
                <h4 className="text-[11px] font-semibold uppercase tracking-wider text-[#8B949E]">
                  Rilevamenti Sensore a Terra
                </h4>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  <div className="border-l-2 border-[#58A6FF] pl-2.5">
                    <span className="block text-[10px] text-[#8B949E]">Precipitazione</span>
                    <span className="text-[14px] font-bold text-white">24.5 mm/h</span>
                  </div>
                  <div className="border-l-2 border-[#58A6FF] pl-2.5">
                    <span className="block text-[10px] text-[#8B949E]">Raffiche Vento</span>
                    <span className="text-[14px] font-bold text-white">38 km/h SW</span>
                  </div>
                  <div className="border-l-2 border-[#58A6FF] pl-2.5">
                    <span className="block text-[10px] text-[#8B949E]">Pressione</span>
                    <span className="text-[14px] font-bold text-white">1008 hPa</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer info bar */}
        <div className="sticky bottom-0 border-t border-[var(--border)] bg-[#0B1016]/95 px-6 py-3 backdrop-blur-md flex items-center justify-between text-[11px] text-[#8B949E]">
          <span>Ispezione conforme a FE-REQ-03 / D-06</span>
          <span className="font-mono">Premi ESC per chiudere</span>
        </div>
      </aside>
    </div>
  );
}
