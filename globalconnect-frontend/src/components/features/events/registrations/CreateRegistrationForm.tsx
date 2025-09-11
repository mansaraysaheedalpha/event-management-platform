// src/components/features/events/registrations/CreateRegistrationForm.tsx
"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@apollo/client";
import { toast } from "sonner";
import { CREATE_REGISTRATION_MUTATION } from "@/graphql/events.graphql";
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
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";

// Schema validation for the form
const registrationFormSchema = z.object({
  email: z.string().email("Please enter a valid email address."),
  firstName: z.string().optional(),
  lastName: z.string().optional(),
});

type RegistrationFormValues = z.infer<typeof registrationFormSchema>;

interface CreateRegistrationFormProps {
  eventId: string;
  onFinished: () => void;
}

export function CreateRegistrationForm({
  eventId,
  onFinished,
}: CreateRegistrationFormProps) {
  const [isGuest, setIsGuest] = useState(false);
  const form = useForm<RegistrationFormValues>({
    resolver: zodResolver(registrationFormSchema),
  });

  const [createRegistration, { loading }] = useMutation(
    CREATE_REGISTRATION_MUTATION,
    {
      onCompleted: (data) => {
        const email =
          data.createRegistration.user?.email ||
          data.createRegistration.guestEmail;
        toast.success(`Successfully registered ${email}!`);
        onFinished();
      },
      onError: (error) => toast.error(error.message),
      refetchQueries: ["GetRegistrationsByEvent"],
    }
  );

  const onSubmit = (values: RegistrationFormValues) => {
    const payload: {
      email: string;
      firstName?: string;
      lastName?: string;
      userId?: string; // We'll add this feature later
    } = { email: values.email };

    if (isGuest) {
      payload.firstName = values.firstName;
      payload.lastName = values.lastName;
    }

    createRegistration({
      variables: {
        input: payload,
        eventId: eventId, // Pass eventId separately if needed by your resolver
      },
    });
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <div className="flex items-center space-x-2">
          <Switch
            id="guest-mode"
            checked={isGuest}
            onCheckedChange={setIsGuest}
          />
          <Label htmlFor="guest-mode">Register as Guest</Label>
        </div>

        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Attendee Email</FormLabel>
              <FormControl>
                <Input
                  placeholder={
                    isGuest ? "guest.attendee@email.com" : "user@platform.com"
                  }
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {isGuest && (
          <div className="grid grid-cols-2 gap-4">
            <FormField
              control={form.control}
              name="firstName"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>First Name</FormLabel>
                  <FormControl>
                    <Input placeholder="John" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="lastName"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Last Name</FormLabel>
                  <FormControl>
                    <Input placeholder="Doe" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
        )}

        <Button type="submit" disabled={loading} className="w-full">
          {loading && <Loader className="mr-2" />}
          {loading ? "Registering..." : "Register Attendee"}
        </Button>
      </form>
    </Form>
  );
}
