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
import { useAuthStore } from "@/store/auth.store"; // Assuming auth store is available

// Schema with conditional validation for guest fields
const registrationFormSchema = z
  .object({
    email: z.string().email("Please enter a valid email address."),
    first_name: z.string().optional(),
    last_name: z.string().optional(),
    isGuest: z.boolean(),
  })
  .refine(
    (data) => {
      if (data.isGuest) {
        return data.first_name && data.first_name.length > 0;
      }
      return true;
    },
    {
      message: "First name is required for guest registration.",
      path: ["first_name"],
    }
  )
  .refine(
    (data) => {
      if (data.isGuest) {
        return data.last_name && data.last_name.length > 0;
      }
      return true;
    },
    {
      message: "Last name is required for guest registration.",
      path: ["last_name"],
    }
  );

type RegistrationFormValues = z.infer<typeof registrationFormSchema>;

interface CreateRegistrationFormProps {
  eventId: string;
  onFinished: () => void;
}

export function CreateRegistrationForm({
  eventId,
  onFinished,
}: CreateRegistrationFormProps) {
  const { user } = useAuthStore();
  const [isGuest, setIsGuest] = useState(!user); // Default to guest if not logged in

  const form = useForm<RegistrationFormValues>({
    resolver: zodResolver(registrationFormSchema),
    defaultValues: {
      email: user?.email || "",
      isGuest: !user,
    },
  });

  // Watch the value of isGuest to dynamically update the form
  const isGuestValue = form.watch("isGuest");

  const onSubmit = (values: RegistrationFormValues) => {
    const registrationIn: {
      email: string;
      first_name?: string;
      last_name?: string;
      user_id?: string;
    } = { email: values.email };

    if (values.isGuest) {
      registrationIn.first_name = values.first_name;
      registrationIn.last_name = values.last_name;
    } else if (user) {
      registrationIn.user_id = user.id;
    }

    createRegistration({
      variables: {
        eventId,
        registrationIn,
      },
    });
  };

  const [createRegistration, { loading }] = useMutation(
    CREATE_REGISTRATION_MUTATION,
    {
      onCompleted: (data) => {
        const name =
          data.createRegistration.guestName || data.createRegistration.user?.id;
        toast.success(
          `Successfully registered ${name}! Your ticket is ${data.createRegistration.ticketCode}.`
        );
        onFinished();
      },
      onError: (error) => {
        if (error.graphQLErrors && error.graphQLErrors.length > 0) {
          const graphQLError = error.graphQLErrors[0];
          // eslint-disable-next-line @typescript-eslint/ban-ts-comment
          // @ts-ignore
          const code = graphQLError.extensions?.code;

          if (code === "CONFLICT") {
            toast.error(
              "A registration already exists for this user or email."
            );
          } else if (code === "FORBIDDEN") {
            toast.error(
              "You do not have permission to register for this event."
            );
          } else {
            toast.error(graphQLError.message);
          }
        } else {
          toast.error("An unexpected error occurred. Please try again.");
        }
      },
      refetchQueries: ["GetRegistrationsByEvent"],
    }
  );

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(onSubmit)}
        className="space-y-4"
        noValidate
      >
        {!user && (
          <div className="flex items-center space-x-2">
            <FormField
              control={form.control}
              name="isGuest"
              render={({ field }) => (
                <Switch
                  id="guest-mode"
                  checked={field.value}
                  onCheckedChange={field.onChange}
                />
              )}
            />
            <Label htmlFor="guest-mode">Register as Guest</Label>
          </div>
        )}

        {user ? (
          <div className="space-y-2">
            <Label>Email</Label>
            <p className="text-sm text-gray-500">{user.email}</p>
          </div>
        ) : (
          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Email</FormLabel>
                <FormControl>
                  <Input placeholder="attendee@email.com" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        )}

        {isGuestValue && (
          <div className="grid grid-cols-2 gap-4">
            <FormField
              control={form.control}
              name="first_name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>First Name</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="John"
                      {...field}
                      value={field.value ?? ""}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="last_name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Last Name</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="Doe"
                      {...field}
                      value={field.value ?? ""}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
        )}

        <Button type="submit" disabled={loading} className="w-full">
          {loading && <Loader className="mr-2" />}
          {loading ? "Registering..." : "Register"}
        </Button>
      </form>
    </Form>
  );
}

