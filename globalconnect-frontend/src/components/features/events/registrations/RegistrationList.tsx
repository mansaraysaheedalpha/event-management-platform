//src / components / features / events / registrations / RegistrationList.tsx;
"use client";

import { useQuery } from "@apollo/client";
import { GET_REGISTRATIONS_BY_EVENT_QUERY } from "@/graphql/events.graphql";
import { DataTable } from "@/components/features/events/event-list/data-table";
import { columns } from "./registration-columns";
import { Loader } from "@/components/ui/loader";
import { AlertTriangle } from "lucide-react";

interface RegistrationListProps {
  eventId: string;
}

export function RegistrationList({ eventId }: RegistrationListProps) {
  const { data, loading, error } = useQuery(GET_REGISTRATIONS_BY_EVENT_QUERY, {
    variables: { eventId },
  });

  if (loading) {
    return (
      <div className="flex justify-center items-center h-48">
        <Loader />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center text-red-500 bg-red-50 p-6 rounded-md">
        <AlertTriangle className="mx-auto h-8 w-8 mb-2" />
        <p className="font-semibold">Error loading registrations</p>
        <p className="text-sm">{error.message}</p>
      </div>
    );
  }

  return (
    <DataTable columns={columns} data={data?.registrationsByEvent || []} />
  );
}
