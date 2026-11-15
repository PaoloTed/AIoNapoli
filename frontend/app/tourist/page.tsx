"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { RecipientView } from "@/components/RecipientView";
import { RECIPIENT_PROFILES } from "@/lib/recipients";
import { ConsumerSkeleton } from "@/components/states/Skeleton";

function TouristRouteContent() {
  const searchParams = useSearchParams();
  const scenarioId = searchParams.get("scenario") ?? undefined;
  return <RecipientView profile={RECIPIENT_PROFILES.tourist} scenarioId={scenarioId} />;
}

export default function TouristPage() {
  return (
    <Suspense fallback={<ConsumerSkeleton />}>
      <TouristRouteContent />
    </Suspense>
  );
}
