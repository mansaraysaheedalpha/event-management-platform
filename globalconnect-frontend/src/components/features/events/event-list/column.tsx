// src/components/features/events/event-list/columns.tsx
"use client";

import { ColumnDef } from "@tanstack/react-table";
import { format } from "date-fns";
import Link from "next/link";
import { ArrowUpDown, MoreHorizontal } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

// ✅ IMPORT the auto-generated type from GraphQL Code Generator.
// Note: The actual name might be Events_By_OrganizationQuery depending on your setup.
import { Events_By_OrganizationQuery } from "@/gql/graphql";

// ✅ This is our single, authoritative type for an event in the list.
// We use `[number]` to extract the type of a single item from the array.
export type Event = Events_By_OrganizationQuery["eventsByOrganization"][number];

export const columns: ColumnDef<Event>[] = [
  {
    accessorKey: "name",
    header: ({ column }) => (
      <Button
        variant="ghost"
        onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
      >
        Event Name
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    cell: ({ row }) => {
      const event = row.original;
      return (
        // ✅ Make the event name a clickable link to its detail page.
        <Link
          href={`/events/${event.id}`}
          className="font-medium text-primary hover:underline"
        >
          {event.name}
        </Link>
      );
    },
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => {
      const status = row.getValue("status") as string;
      const variant =
        status === "published"
          ? "default"
          : status === "draft"
          ? "secondary"
          : "destructive";

      return (
        <Badge variant={variant} className="capitalize">
          {status}
        </Badge>
      );
    },
  },
  {
    accessorKey: "start_date",
    header: ({ column }) => (
      <Button
        variant="ghost"
        onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
      >
        Start Date
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    cell: ({ row }) => {
      // ✅ Use date-fns for consistent and professional date formatting.
      const date = new Date(row.getValue("start_date"));
      return <div>{format(date, "PPP")}</div>; // e.g., "Sep 3, 2025"
    },
  },
  {
    accessorKey: "is_public",
    header: "Visibility",
    cell: ({ row }) => (row.getValue("is_public") ? "Public" : "Private"),
  },
  {
    id: "actions",
    cell: ({ row }) => {
      const event = row.original;
      return (
        // ✅ Add a standard actions menu for future functionality.
        <div className="text-right">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="h-8 w-8 p-0">
                <span className="sr-only">Open menu</span>
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Actions</DropdownMenuLabel>
              <DropdownMenuItem asChild>
                <Link href={`/events/${event.id}`}>View Details</Link>
              </DropdownMenuItem>
              <DropdownMenuItem disabled>Edit Event (Soon)</DropdownMenuItem>
              <DropdownMenuItem disabled className="text-red-500">
                Delete Event (Soon)
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      );
    },
  },
];
