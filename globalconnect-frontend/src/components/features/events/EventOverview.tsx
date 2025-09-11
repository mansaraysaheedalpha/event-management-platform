// src/components/features/events/EventOverview.tsx
"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DescriptionList } from "@/components/ui/description-list";
import { GetEventByIdQuery } from "@/gql/graphql";
import { format } from "date-fns";

type EventDetails = NonNullable<GetEventByIdQuery["event"]>;

interface EventOverviewProps {
  event: EventDetails;
}

export function EventOverview({ event }: EventOverviewProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Event Details</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {event.description && (
          <DescriptionList
            title="Description"
            description={event.description}
          />
        )}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <DescriptionList
            title="Start Date"
            description={format(new Date(event.startDate), "PPP p")}
          />
          <DescriptionList
            title="End Date"
            description={format(new Date(event.endDate), "PPP p")}
          />
          <DescriptionList
            title="Visibility"
            description={event.isPublic ? "Public" : "Private"}
          />
        </div>
      </CardContent>
    </Card>
  );
}
