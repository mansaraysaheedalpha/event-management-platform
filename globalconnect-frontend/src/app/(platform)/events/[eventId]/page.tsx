// src/app/(platform)/events/[eventId]/page.tsx
"use client";

import { useQuery } from "@apollo/client";
import { GET_EVENT_DETAILS_QUERY } from "@/graphql/events.graphql";
import { Loader } from "@/components/ui/loader";
import { AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { EventTabs } from "@/components/features/events/EventTabs";

interface EventDetailPageProps {
  params: { eventId: string };
}

export default function EventDetailPage({ params }: EventDetailPageProps) {
  const { eventId } = params;
  const { data, loading, error } = useQuery(GET_EVENT_DETAILS_QUERY, {
    variables: { id: eventId },
  });

  if (loading) {
    return (
      <div className="flex justify-center items-center h-full">
        <Loader className="h-8 w-8" />
      </div>
    );
  }

  if (error || !data?.event) {
    return (
      <div className="text-center text-red-500 bg-red-50 p-6 rounded-md">
        <AlertTriangle className="mx-auto h-8 w-8 mb-2" />
        <p className="font-semibold">Error loading event</p>
        <p className="text-sm">{error?.message || "Event not found."}</p>
      </div>
    );
  }

  const { event } = data;

  const getStatusVariant = (status: string) =>
    status === "published"
      ? "default"
      : status === "draft"
      ? "secondary"
      : "destructive";

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <h1 className="text-3xl font-bold">{event.name}</h1>
        <Badge
          variant={getStatusVariant(event.status)}
          className="capitalize text-base"
        >
          {event.status}
        </Badge>
      </div>
      <EventTabs event={event} />
    </div>
  );
}
