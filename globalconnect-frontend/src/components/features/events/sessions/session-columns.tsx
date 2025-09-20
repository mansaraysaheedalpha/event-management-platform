"use client";

import { ColumnDef } from "@tanstack/react-table";
import { format } from "date-fns";
import { GetSessionsByEventQuery } from "@/gql/graphql";
import { Badge } from "@/components/ui/badge";

// Extract the type for a single session from our auto-generated query types
export type Session = GetSessionsByEventQuery["sessionsByEvent"][number];

export const columns: ColumnDef<Session>[] = [
  {
    accessorKey: "title",
    header: "Title",
    cell: ({ row }) => (
      <div className="font-medium">{row.getValue("title")}</div>
    ),
  },
  {
    accessorKey: "startTime",
    header: "Start Time",
    cell: ({ row }) => (
      <div>{format(new Date(row.getValue("startTime")), "p")}</div> // "3:00 PM"
    ),
  },
  {
    accessorKey: "endTime",
    header: "End Time",
    cell: ({ row }) => (
      <div>{format(new Date(row.getValue("endTime")), "p")}</div>
    ),
  },
  {
    accessorKey: "speakers",
    header: "Speakers",
    cell: ({ row }) => {
      const speakers = row.getValue("speakers") as { name: string }[];
      if (!speakers || speakers.length === 0) {
        return <span className="text-muted-foreground">None</span>;
      }
      return (
        <div className="flex flex-wrap gap-1">
          {speakers.map((speaker) => (
            <Badge key={speaker.name} variant="secondary">
              {speaker.name}
            </Badge>
          ))}
        </div>
      );
    },
  },
];
