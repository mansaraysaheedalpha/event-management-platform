// src/components/features/events/sessions/CreateSessionForm.tsx
"use client";

import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@apollo/client";
import { toast } from "sonner";
import { CREATE_SESSION_MUTATION } from "@/graphql/events.graphql";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Loader } from "@/components/ui/loader";
import { SpeakerCombobox } from "./SpeakerCombobox"; // ✅ Import the new component

const sessionFormSchema = z.object({
  title: z.string().min(3, "Session title is required."),
  startTime: z.string().min(1, "Start time is required."),
  endTime: z.string().min(1, "End time is required."),
  // ✅ Add speakerIds to our validation schema
  speakerIds: z.array(z.string()).optional(),
});

type SessionFormValues = z.infer<typeof sessionFormSchema>;

interface CreateSessionFormProps {
  eventId: string;
  eventStartDate: Date;
  onFinished: () => void;
}

export function CreateSessionForm({
  eventId,
  eventStartDate,
  onFinished,
}: CreateSessionFormProps) {
  const form = useForm<SessionFormValues>({
    resolver: zodResolver(sessionFormSchema),
    defaultValues: {
      speakerIds: [], // Default to an empty array
    },
  });

  const [createSession, { loading }] = useMutation(CREATE_SESSION_MUTATION, {
    onCompleted: () => {
      toast.success("Session created successfully!");
      onFinished();
    },
    onError: (error) => toast.error(error.message),
    refetchQueries: ["GetSessionsByEvent"],
  });

  const onSubmit = (values: SessionFormValues) => {
    const startDateTime = new Date(eventStartDate);
    const [startHours, startMinutes] = values.startTime.split(":").map(Number);
    startDateTime.setHours(startHours, startMinutes, 0, 0);

    const endDateTime = new Date(eventStartDate);
    const [endHours, endMinutes] = values.endTime.split(":").map(Number);
    endDateTime.setHours(endHours, endMinutes, 0, 0);

    createSession({
      variables: {
        input: {
          eventId: eventId,
          title: values.title,
          startTime: startDateTime.toISOString(),
          endTime: endDateTime.toISOString(),
          // ✅ Pass the speakerIds from the form
          speakerIds: values.speakerIds || [],
        },
      },
    });
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="title"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Session Title</FormLabel>
              <FormControl>
                <Input placeholder="e.g., Opening Keynote" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <div className="grid grid-cols-2 gap-4">
          <FormField
            control={form.control}
            name="startTime"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Start Time</FormLabel>
                <FormControl>
                  <Input type="time" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="endTime"
            render={({ field }) => (
              <FormItem>
                <FormLabel>End Time</FormLabel>
                <FormControl>
                  <Input type="time" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        {/* ✅ Integrate the SpeakerCombobox into our form */}
        <FormField
          control={form.control}
          name="speakerIds"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Speakers (Optional)</FormLabel>
              <FormControl>
                <SpeakerCombobox
                  value={field.value || []}
                  onChange={field.onChange}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <Button type="submit" disabled={loading} className="w-full">
          {loading && <Loader className="mr-2" />}
          Create Session
        </Button>
      </form>
    </Form>
  );
}
