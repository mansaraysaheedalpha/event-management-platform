//src / components / features / events / registrations / registration - columns.tsx;
"use client";

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

      // More robust name and email checking
      const user = registration.user;
      const guestName = registration.guestName;

      const hasFirstName = user?.first_name && user.first_name !== "None";
      const hasLastName = user?.last_name && user.last_name !== "None";
      const hasFullName = hasFirstName && hasLastName;

      const getDisplayName = (user) => {
        if (!user) return null;
        const firstName =
          user.first_name && user.first_name !== "None" ? user.first_name : "";
        const lastName =
          user.last_name && user.last_name !== "None" ? user.last_name : "";
        const fullName = `${firstName} ${lastName}`.trim();
        return fullName || user.email; // Fallback to email if name is empty
      };

      const name =
        registration.guestName ||
        getDisplayName(registration.user) ||
        "Registered User";

      const email = user?.email || registration.guestEmail;

      return (
        <div className="flex items-center gap-3">
          <UserAvatar
            firstName={
              (hasFirstName ? user.first_name : "") || guestName || ""
            }
            lastName={hasLastName ? user.last_name : ""}
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
