"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { TouristView } from "@/components/TouristView";
import { ConsumerSkeleton } from "@/components/states/Skeleton";

function TouristRouteContent() {
  const searchParams = useSearchParams();
  const scenarioId = searchParams.get("scenario") ?? undefined;
  return <TouristView scenarioId={scenarioId} />;
}

export default function TouristPage() {
  return (
    <Suspense fallback={<ConsumerSkeleton />}>
      <TouristRouteContent />
    </Suspense>
  );
}
