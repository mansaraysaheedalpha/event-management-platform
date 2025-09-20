// src/components/features/events/EventRow.tsx
"use client";

import Link from "next/link";
import Image from "next/image";
import { format } from "date-fns";
import { CalendarDays, Users, MoreVertical, ArrowRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { Event } from "./event-list/column";

interface EventRowProps {
  event: Event;
}

export function EventRow({ event }: EventRowProps) {
  const getStatusVariant = (status: string) =>
    status === "published"
      ? "default"
      : status === "draft"
      ? "secondary"
      : "destructive";

  const placeholderImage = "/placeholder-event.png";
  const imageUrl = event.imageUrl || placeholderImage;

  return (
    <div className="flex items-center p-4 border-b transition-colors hover:bg-muted/50">
      <div className="flex items-center gap-4 flex-1">
        <Image
          src={imageUrl}
          alt={event.name}
          width={64}
          height={36}
          className="rounded-md object-cover w-16 h-9"
        />
        <div className="flex-1">
          <Link
            href={`/events/${event.id}`}
            className="font-semibold hover:underline"
          >
            {event.name}
          </Link>
          <div className="text-sm text-muted-foreground flex items-center gap-2 mt-1">
            <CalendarDays className="h-4 w-4" />
            <span>{format(new Date(event.startDate), "PPP")}</span>
          </div>
        </div>
      </div>
      <div className="w-40 text-center">
        <Badge variant={getStatusVariant(event.status)} className="capitalize">
          {event.status}
        </Badge>
      </div>
      <div className="w-40 text-center">
        <span
          className={`text-xs font-semibold px-2 py-1 rounded-full ${
            event.isPublic
              ? "bg-green-100 text-green-800"
              : "bg-amber-100 text-amber-800"
          }`}
        >
          {event.isPublic ? "Public" : "Private"}
        </span>
      </div>
      <div className="w-40 flex items-center justify-center">
        <Users className="h-4 w-4 mr-2 text-muted-foreground" />
        <span className="font-semibold">{event.registrationsCount || 0}</span>
      </div>
      <div className="w-20 text-right">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="h-8 w-8 p-0">
              <span className="sr-only">Open menu</span>
              <MoreVertical className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem asChild>
              <Link href={`/events/${event.id}`}>
                <ArrowRight className="mr-2 h-4 w-4" />
                Manage
              </Link>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}
