"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { OperatorView } from "@/components/OperatorView";
import { OperatorSkeleton } from "@/components/states/Skeleton";

function OperatorRouteContent() {
  const searchParams = useSearchParams();
  const scenarioId = searchParams.get("scenario") ?? undefined;
  return <OperatorView scenarioId={scenarioId} />;
}

export default function OperatorPage() {
  return (
    <Suspense fallback={<OperatorSkeleton />}>
      <OperatorRouteContent />
    </Suspense>
  );
}
