// src/components/features/events/EventCard.tsx
"use client";

import Link from "next/link";
import Image from "next/image";
import { format } from "date-fns";
import { CalendarDays, Users, ArrowRight } from "lucide-react";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { AspectRatio } from "@/components/ui/aspect-ratio";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { Event } from "./event-list/column"; // We can reuse the type

interface EventCardProps {
  event: Event;
}

export function EventCard({ event }: EventCardProps) {
  const getStatusVariant = (status: string) =>
    status === "published"
      ? "default"
      : status === "draft"
      ? "secondary"
      : "destructive";

  const placeholderImage = "/placeholder-event.png";
  const imageUrl = event.imageUrl || placeholderImage;

  return (
    <TooltipProvider>
      <Card className="flex flex-col h-full overflow-hidden transition-all hover:shadow-xl border-border/60 hover:border-border">
        <CardHeader className="p-0">
          <Link href={`/events/${event.id}`}>
            <AspectRatio ratio={16 / 9}>
              <Image
                src={imageUrl}
                alt={event.name}
                className="object-cover w-full h-full"
                fill
              />
            </AspectRatio>
          </Link>
        </CardHeader>
        <CardContent className="p-5 flex-grow">
          <div className="flex justify-between items-start mb-3">
            <Badge
              variant={getStatusVariant(event.status)}
              className="capitalize"
            >
              {event.status}
            </Badge>
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
          <CardTitle className="text-xl font-bold leading-tight mb-2">
            <Link href={`/events/${event.id}`} className="hover:underline">
              {event.name}
            </Link>
          </CardTitle>
          <div className="text-sm text-muted-foreground flex items-center gap-2">
            <CalendarDays className="h-4 w-4" />
            <span>{format(new Date(event.startDate), "PPP")}</span>
          </div>
        </CardContent>
        <CardFooter className="p-5 bg-muted/40 border-t">
          <div className="flex justify-between items-center w-full">
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="flex items-center text-sm cursor-pointer">
                  <Users className="h-4 w-4 mr-2 text-muted-foreground" />
                  <span className="font-bold text-base">
                    {event.registrationsCount || 0}
                  </span>
                  <span className="text-muted-foreground ml-1.5">
                    Registrations
                  </span>
                </div>
              </TooltipTrigger>
              <TooltipContent>
                <p>{event.registrationsCount || 0} people have registered.</p>
              </TooltipContent>
            </Tooltip>
            <Button asChild variant="ghost" size="sm">
              <Link href={`/events/${event.id}`}>
                Manage
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </div>
        </CardFooter>
      </Card>
    </TooltipProvider>
  );
}
