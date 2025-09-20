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

import { Events_By_OrganizationQuery } from "@/gql/graphql";

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
    // ✅ THE FIX: Use camelCase to match the GraphQL schema
    accessorKey: "startDate",
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
      // ✅ THE FIX: Get the value using the correct camelCase key
      const date = new Date(row.getValue("startDate"));
      return <div>{format(date, "PPP")}</div>;
    },
  },
  {
    // ✅ THE FIX: Use camelCase here as well for consistency
    accessorKey: "isPublic",
    header: "Visibility",
    cell: ({ row }) => (row.getValue("isPublic") ? "Public" : "Private"),
  },
  {
    id: "actions",
    cell: ({ row }) => {
      const event = row.original;
      return (
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
