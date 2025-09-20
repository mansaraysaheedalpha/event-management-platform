//src/app/(platform)/onboarding/create-organization/page.tsx
"use client";

import { useState } from "react";
import { useMutation, gql } from "@apollo/client";
import { toast } from "sonner";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth.store";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Loader } from "@/components/ui/loader";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import Image from "next/image";
import { ONBOARDING_CREATE_ORGANIZATION_MUTATION } from "@/graphql/organization.graphql";

export default function CreateOrganizationPage() {
  const [name, setName] = useState("");
  const router = useRouter();
  const setAuth = useAuthStore((state) => state.setAuth);

  const [createOrganization, { loading }] = useMutation(
    ONBOARDING_CREATE_ORGANIZATION_MUTATION,
    {
      onCompleted: (data) => {
        toast.success("Organization created successfully!");
        const { token, user } = data.onboardingCreateOrganization;

        // This is the final step: save the NEW full-access token
        setAuth(token, user);

        // Now redirect to the dashboard as a fully authenticated user
        router.push("/dashboard");
      },
      onError: (error) => {
        toast.error(error.message);
      },
    }
  );

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    createOrganization({ variables: { input: { name } } });
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-6">
      <div className="flex justify-center mb-8">
        <Image
          src="/logo.png"
          alt="GlobalConnect Logo"
          width={80}
          height={80}
        />
      </div>
      <Card className="w-full max-w-md">
        <form onSubmit={handleSubmit}>
          <CardHeader>
            <CardTitle>Welcome to GlobalConnect!</CardTitle>
            <CardDescription>
              Let's get started by creating your first organization.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <Label htmlFor="org-name">Organization Name</Label>
              <Input
                id="org-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Acme Inc."
                required
              />
            </div>
          </CardContent>
          <CardFooter>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading && <Loader className="mr-2" />}
              Create Organization & Continue
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
