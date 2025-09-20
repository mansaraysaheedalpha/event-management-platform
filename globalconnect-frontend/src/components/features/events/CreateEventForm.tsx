// src/components/features/events/CreateEventForm.tsx

"use client";

import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@apollo/client";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { CREATE_EVENT_MUTATION } from "@/graphql/events.graphql";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { DatePicker } from "@/components/ui/date-picker";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Loader } from "@/components/ui/loader";

const eventFormSchema = z
  .object({
    name: z.string().min(3, "Event name must be at least 3 characters."),
    description: z.string().optional(),
    startDate: z.date({
      required_error: "A start date is required.",
    }),
    endDate: z.date({
      required_error: "An end date is required.",
    }),
  })
  .refine((data) => data.endDate > data.startDate, {
    message: "End date must be after the start date.",
    path: ["endDate"],
  });

type EventFormValues = z.infer<typeof eventFormSchema>;

export function CreateEventForm() {
  const router = useRouter();
  const form = useForm<EventFormValues>({
    resolver: zodResolver(eventFormSchema),
  });

  const [createEvent, { loading }] = useMutation(CREATE_EVENT_MUTATION, {
    onCompleted: (data) => {
      toast.success("Event created successfully!");
      router.push(`/events/${data.createEvent.id}`);
    },
    onError: (error) => {
      toast.error(error.message);
    },
    refetchQueries: ["GetEventsByOrganization"],
  });

  const onSubmit = (values: EventFormValues) => {
    createEvent({
      variables: {
        // ✅ THE DEFINITIVE FIX:
        // The GraphQL schema expects camelCase variables.
        // We are now sending the correct format.
        input: {
          name: values.name,
          description: values.description,
          startDate: values.startDate.toISOString(),
          endDate: values.endDate.toISOString(),
          venueId: null, // Still optional, but now correctly named
        },
      },
    });
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Event Name</FormLabel>
              <FormControl>
                <Input placeholder="e.g., Annual Tech Summit" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Description (Optional)</FormLabel>
              <FormControl>
                <Textarea placeholder="Describe your event..." {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FormField
            control={form.control}
            name="startDate"
            render={({ field }) => (
              <FormItem className="flex flex-col">
                <FormLabel>Start Date</FormLabel>
                <FormControl>
                  <DatePicker value={field.value} onChange={field.onChange} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="endDate"
            render={({ field }) => (
              <FormItem className="flex flex-col">
                <FormLabel>End Date</FormLabel>
                <FormControl>
                  <DatePicker value={field.value} onChange={field.onChange} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>
        <Button type="submit" disabled={loading} className="w-full">
          {loading && <Loader className="mr-2" />}
          {loading ? "Creating..." : "Create Event"}
        </Button>
      </form>
    </Form>
  );
}
