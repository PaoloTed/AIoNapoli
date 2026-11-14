"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { CitizenView } from "@/components/CitizenView";
import { ConsumerSkeleton } from "@/components/states/Skeleton";

function CitizenRouteContent() {
  const searchParams = useSearchParams();
  const scenarioId = searchParams.get("scenario") ?? undefined;
  return <CitizenView scenarioId={scenarioId} />;
}

export default function CitizenPage() {
  return (
    <Suspense fallback={<ConsumerSkeleton />}>
      <CitizenRouteContent />
    </Suspense>
  );
}
