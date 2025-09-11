//src / components / features / events / registrations / registration - columns.tsx;
("use client");

import { ColumnDef } from "@tanstack/react-table";
import { format } from "date-fns";
import { GetRegistrationsByEventQuery } from "@/gql/graphql";
import { Badge } from "@/components/ui/badge";
import { UserAvatar } from "@/components/ui/user-avatar";

export type Registration =
  GetRegistrationsByEventQuery["registrationsByEvent"][number];

export const columns: ColumnDef<Registration>[] = [
  {
    accessorKey: "attendee",
    header: "Attendee",
    cell: ({ row }) => {
      const registration = row.original;
      const name =
        registration.user?.firstName && registration.user?.lastName
          ? `${registration.user.firstName} ${registration.user.lastName}`
          : registration.guestName || "Guest User";
      const email = registration.user?.email || registration.guestEmail;

      return (
        <div className="flex items-center gap-3">
          <UserAvatar
            firstName={
              registration.user?.firstName || registration.guestName || ""
            }
            lastName={registration.user?.lastName || ""}
          />
          <div className="flex flex-col">
            <span className="font-medium">{name}</span>
            <span className="text-xs text-muted-foreground">{email}</span>
          </div>
        </div>
      );
    },
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => {
      const status = row.getValue("status") as string;
      const variant =
        status === "checked_in"
          ? "default"
          : status === "confirmed"
          ? "secondary"
          : "destructive";
      return (
        <Badge variant={variant} className="capitalize">
          {status.replace("_", " ")}
        </Badge>
      );
    },
  },
  {
    accessorKey: "ticketCode",
    header: "Ticket Code",
  },
  {
    accessorKey: "checkedInAt",
    header: "Checked In Time",
    cell: ({ row }) => {
      const checkedInAt = row.getValue("checkedInAt");
      if (!checkedInAt) {
        return <span className="text-muted-foreground">N/A</span>;
      }
      const date = new Date(checkedInAt as string);
      return <div>{format(date, "PPP p")}</div>;
    },
  },
];
