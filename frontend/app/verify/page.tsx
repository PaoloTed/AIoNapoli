"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { VerifyView } from "@/components/VerifyView";
import { OperatorSkeleton } from "@/components/states/Skeleton";

function VerifyRouteContent() {
  const searchParams = useSearchParams();
  const scenarioId = searchParams.get("scenario") ?? undefined;
  return <VerifyView scenarioId={scenarioId} />;
}

export default function VerifyPage() {
  return (
    <Suspense fallback={<OperatorSkeleton />}>
      <VerifyRouteContent />
    </Suspense>
  );
}
