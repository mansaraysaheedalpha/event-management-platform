// src/components/features/events/EventTabs.tsx
"use client";

import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { GetEventByIdQuery } from "@/gql/graphql";
import { EventOverview } from "./EventOverview";
import { SessionList } from "./sessions/sessionList";
import { Button } from "@/components/ui/button";
import { PlusCircle, UserPlus } from "lucide-react";
import { CreateSessionModal } from "./sessions/CreateSessionModal";
import { RegistrationList } from "./registrations/RegistrationList";
import { CreateRegistrationModal } from "./registrations/CreateRegistrationModal"; // ✅ Import the new modal

interface EventTabsProps {
  event: NonNullable<GetEventByIdQuery["event"]>;
}

export function EventTabs({ event }: EventTabsProps) {
  const [isSessionModalOpen, setIsSessionModalOpen] = useState(false);
  // ✅ State for the new registration modal
  const [isRegModalOpen, setIsRegModalOpen] = useState(false);

  return (
    <>
      {/* Session Creation Modal */}
      <CreateSessionModal
        isOpen={isSessionModalOpen}
        onOpenChange={setIsSessionModalOpen}
        eventId={event.id}
        eventStartDate={new Date(event.startDate)}
        eventEndDate={new Date(event.endDate)}
      />

      {/* ✅ Registration Creation Modal */}
      <CreateRegistrationModal
        isOpen={isRegModalOpen}
        onOpenChange={setIsRegModalOpen}
        eventId={event.id}
      />

      <Tabs defaultValue="overview" className="w-full">
        <TabsList className="grid w-full grid-cols-4 mb-4">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="sessions">Sessions</TabsTrigger>
          <TabsTrigger value="registrations">Registrations</TabsTrigger>
          <TabsTrigger value="settings" disabled>
            Settings (Soon)
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <EventOverview event={event} />
        </TabsContent>

        <TabsContent value="sessions" className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-2xl font-bold">Schedule</h2>
            <Button onClick={() => setIsSessionModalOpen(true)}>
              <PlusCircle className="mr-2 h-4 w-4" />
              Add Session
            </Button>
          </div>
          <SessionList eventId={event.id} />
        </TabsContent>

        <TabsContent value="registrations" className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-2xl font-bold">Attendees</h2>
            {/* ✅ Enable the button and wire it up to the state */}
            <Button onClick={() => setIsRegModalOpen(true)}>
              <UserPlus className="mr-2 h-4 w-4" />
              Register Attendee
            </Button>
          </div>
          <RegistrationList eventId={event.id} />
        </TabsContent>
      </Tabs>
    </>
  );
}
