// src/app/(platform)/events/page.tsx
"use client";

import { useQuery } from "@apollo/client";
import { GET_EVENTS_QUERY } from "@/graphql/events.graphql";
import { Button } from "@/components/ui/button";
import { Loader } from "@/components/ui/loader";
import { AlertTriangle, PlusCircle } from "lucide-react";
import { columns } from "@/components/features/events/event-list/column";
import { DataTable } from "@/components/features/events/event-list/data-table";
import Link from "next/link";

export default function EventsPage() {
  const { data, loading, error } = useQuery(GET_EVENTS_QUERY);

  const renderContent = () => {
    if (loading) {
      return (
        <div className="flex justify-center items-center h-64">
          <Loader className="h-8 w-8" />
        </div>
      );
    }

    if (error) {
      return (
        <div className="text-center text-red-500 bg-red-50 p-6 rounded-md">
          <AlertTriangle className="mx-auto h-8 w-8 mb-2" />
          <p className="font-semibold">Error loading events</p>
          <p className="text-sm">{error.message}</p>
        </div>
      );
    }

    // Pass the columns and data to our new DataTable component
    return (
      <DataTable columns={columns} data={data?.eventsByOrganization || []} />
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">Events</h1>
        <Button asChild>
          <Link href="/events/new">
            <PlusCircle className="mr-2 h-4 w-4" />
            Create Event
          </Link>
        </Button>
      </div>
      {renderContent()}
    </div>
  );
}
