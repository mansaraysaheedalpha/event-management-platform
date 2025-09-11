"use client";

import { useQuery } from "@apollo/client";
import { GET_SESSIONS_BY_EVENT_QUERY } from "@/graphql/events.graphql";
import { DataTable } from "@/components/features/events/event-list/data-table"; // Re-using our excellent data table
import { columns } from "./session-columns";
import { Loader } from "@/components/ui/loader";
import { AlertTriangle } from "lucide-react";

interface SessionListProps {
  eventId: string;
}

export function SessionList({ eventId }: SessionListProps) {
  const { data, loading, error } = useQuery(GET_SESSIONS_BY_EVENT_QUERY, {
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
        <p className="font-semibold">Error loading sessions</p>
        <p className="text-sm">{error.message}</p>
      </div>
    );
  }

  return <DataTable columns={columns} data={data?.sessionsByEvent || []} />;
}
