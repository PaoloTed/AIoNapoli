"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { RecipientView } from "@/components/RecipientView";
import { RECIPIENT_PROFILES } from "@/lib/recipients";
import { ConsumerSkeleton } from "@/components/states/Skeleton";

function CitizenRouteContent() {
  const searchParams = useSearchParams();
  const scenarioId = searchParams.get("scenario") ?? undefined;
  return <RecipientView profile={RECIPIENT_PROFILES.citizen} scenarioId={scenarioId} />;
}

export default function CitizenPage() {
  return (
    <Suspense fallback={<ConsumerSkeleton />}>
      <CitizenRouteContent />
    </Suspense>
  );
}
