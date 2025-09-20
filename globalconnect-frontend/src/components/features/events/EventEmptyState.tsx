// src/components/features/events/EventEmptyState.tsx
"use client";

import { Button } from "@/components/ui/button";
import { CalendarPlus } from "lucide-react";
import Link from "next/link";

export function EventEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center text-center p-8 border-2 border-dashed rounded-lg h-[450px]">
      <CalendarPlus className="h-16 w-16 text-muted-foreground mb-4" />
      <h2 className="text-2xl font-semibold">
        You haven't created any events yet
      </h2>
      <p className="text-muted-foreground mt-2 mb-6 max-w-sm">
        Get started by creating your first event. It only takes a minute to set
        up.
      </p>
      <Button asChild size="lg">
        <Link href="/events/new">Create Your First Event</Link>
      </Button>
    </div>
  );
}
