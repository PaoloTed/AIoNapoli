"use client";

import clsx from "clsx";

function SkeletonBar({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={clsx(
        "rounded-[6px] bg-[var(--border)]/60 animate-pulse motion-reduce:animate-none",
        className,
      )}
    />
  );
}

export function FindingCardSkeleton() {
  return (
    <div
      className="rounded-[10px] border border-[var(--border)] bg-[var(--surface)] p-4 space-y-3"
      data-skeleton="finding"
    >
      <div className="flex items-center justify-between gap-2">
        <SkeletonBar className="h-4 w-28" />
        <SkeletonBar className="h-5 w-20" />
      </div>
      <div className="space-y-2">
        <SkeletonBar className="h-3.5 w-3/4" />
        <SkeletonBar className="h-3.5 w-1/2" />
      </div>
      <div className="flex items-center justify-between pt-1">
        <SkeletonBar className="h-3 w-24" />
        <SkeletonBar className="h-3 w-32" />
      </div>
    </div>
  );
}

export function MapSkeleton({ compact = false }: { compact?: boolean }) {
  return (
    <div
      className="rounded-[10px] border border-[var(--border)] bg-[var(--surface)] p-4 space-y-3"
      data-skeleton="map"
    >
      <SkeletonBar className="h-4 w-36" />
      <SkeletonBar className={compact ? "h-[200px] w-full" : "h-[240px] md:h-[360px] w-full"} />
      <div className="space-y-2">
        <SkeletonBar className="h-3.5 w-2/3" />
        <SkeletonBar className="h-3.5 w-1/2" />
      </div>
    </div>
  );
}

export function DecisionSkeleton() {
  return (
    <div
      className="rounded-[10px] border border-[var(--border)] bg-[var(--surface)] p-4 space-y-4"
      data-skeleton="decision"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SkeletonBar className="h-5 w-48" />
        <SkeletonBar className="h-8 w-36" />
      </div>
      <SkeletonBar className="h-4 w-5/6" />
      <div className="grid gap-4 md:grid-cols-3">
        <SkeletonBar className="h-36 w-full" />
        <SkeletonBar className="h-36 w-full" />
        <SkeletonBar className="h-36 w-full" />
      </div>
    </div>
  );
}

export function OperatorSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" data-testid="operator-skeleton">
      <div className="grid gap-6 lg:grid-cols-12">
        <div className="lg:col-span-6">
          <MapSkeleton />
        </div>
        <div className="lg:col-span-6 space-y-4">
          <FindingCardSkeleton />
          <FindingCardSkeleton />
          <FindingCardSkeleton />
        </div>
      </div>
      <DecisionSkeleton />
    </div>
  );
}

export function ConsumerSkeleton() {
  return (
    <div className="mx-auto max-w-2xl space-y-4" aria-busy="true" data-testid="consumer-skeleton">
      <div className="rounded-[10px] border border-[var(--border)] bg-[var(--surface)] p-4 space-y-3">
        <SkeletonBar className="h-4 w-40" />
        <SkeletonBar className="h-6 w-full" />
        <SkeletonBar className="h-4 w-3/4" />
        <SkeletonBar className="h-16 w-full" />
      </div>
      <MapSkeleton compact />
    </div>
  );
}
