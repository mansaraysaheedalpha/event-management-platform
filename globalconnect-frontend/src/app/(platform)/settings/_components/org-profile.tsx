"use client";

import { useAuthStore } from "@/store/auth.store";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useQuery, useMutation } from "@apollo/client";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader } from "@/components/ui/loader";
import {
  GET_ORGANIZATION_QUERY,
  UPDATE_ORGANIZATION_MUTATION,
} from "./settings.graphql";
import { GET_MY_ORGS_QUERY } from "@/graphql/queries";

export function OrgProfile() {
  const orgId = useAuthStore((state) => state.orgId);
  const [name, setName] = useState("");
  const [initialName, setInitialName] = useState("");

  const {
    data,
    loading: queryLoading,
    error,
  } = useQuery(GET_ORGANIZATION_QUERY, {
    variables: { organizationId: orgId },
    skip: !orgId,
    onCompleted: (data) => {
      if (data?.organization) {
        setName(data.organization.name);
        setInitialName(data.organization.name);
      }
    },
  });

  const [updateOrganization, { loading: mutationLoading }] = useMutation(
    UPDATE_ORGANIZATION_MUTATION,
    {
      onCompleted: (data) => {
        toast.success("Organization name updated successfully!");
        setInitialName(data.updateOrganization.name);
      },
      onError: (error) => {
        toast.error(error.message);
      },
      // Also refetch the list of orgs, as the name change affects the switcher
      refetchQueries: [
        { query: GET_ORGANIZATION_QUERY, variables: { organizationId: orgId } },
        { query: GET_MY_ORGS_QUERY },
      ],
    }
  );

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (name === initialName) return;
    updateOrganization({
      variables: {
        input: {
          organizationId: orgId,
          name: name,
        },
      },
    });
  };

  const isDirty = name !== initialName;
  const isLoading = queryLoading || mutationLoading;

  if (queryLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Organization Profile</CardTitle>
          <CardDescription>Update your organization's name.</CardDescription>
        </CardHeader>
        <CardContent className="h-24 flex items-center justify-center">
          <Loader className="h-6 w-6" />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Error</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-destructive">Failed to load organization data.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <form onSubmit={handleSubmit}>
        <CardHeader>
          <CardTitle>Organization Profile</CardTitle>
          <CardDescription>Update your organization's name.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Label htmlFor="name">Organization Name</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Your organization's name"
              disabled={isLoading}
            />
          </div>
        </CardContent>
        <CardFooter className="border-t px-6 py-4">
          <div className="flex w-full justify-between items-center">
            <p className="text-sm text-muted-foreground">
              Update the name of your organization.
            </p>
            <Button type="submit" disabled={!isDirty || isLoading}>
              {mutationLoading && <Loader className="mr-2" />}
              Save Changes
            </Button>
          </div>
        </CardFooter>
      </form>
    </Card>
  );
}
