"use client";

import { useQuery, useMutation, gql } from "@apollo/client";
import { useState, useEffect } from "react";
import { toast } from "sonner";
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
import { Loader } from "@/components/ui/loader";
import { GET_MY_PROFILE_QUERY, UPDATE_MY_PROFILE_MUTATION } from "@/graphql/user.graphql";
import { useAuthStore } from "@/store/auth.store";


export function ProfileForm() {
  const [formData, setFormData] = useState({ first_name: "", last_name: "" });
  const [initialData, setInitialData] = useState({
    first_name: "",
    last_name: "",
  });
   const updateUserInStore = useAuthStore((state) => state.updateUser);

  const { data, loading: queryLoading } = useQuery(GET_MY_PROFILE_QUERY, {
    onCompleted: (data) => {
      if (data?.getMyProfile) {
        const { first_name, last_name } = data.getMyProfile;
        setFormData({ first_name, last_name });
        setInitialData({ first_name, last_name });
      }
    },
  });

  const [updateProfile, { loading: mutationLoading }] = useMutation(
    UPDATE_MY_PROFILE_MUTATION,
    {
      onCompleted: (data) => {
        toast.success("Profile updated successfully!");
        const { first_name, last_name } = data.updateMyProfile;
        updateUserInStore({ first_name, last_name });
        setInitialData({ first_name, last_name });
      },
      onError: (error) => toast.error(error.message),
      refetchQueries: [{ query: GET_MY_PROFILE_QUERY }],
    }
  );

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    updateProfile({ variables: { input: formData } });
  };

  const isDirty =
    formData.first_name !== initialData.first_name ||
    formData.last_name !== initialData.last_name;
  const isLoading = queryLoading || mutationLoading;

  return (
    <Card>
      <form onSubmit={handleSubmit}>
        <CardHeader>
          <CardTitle>My Profile</CardTitle>
          <CardDescription>
            This is how others will see you on the site.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="first_name">First Name</Label>
              <Input
                id="first_name"
                name="first_name"
                value={formData.first_name}
                onChange={handleChange}
                disabled={isLoading}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="last_name">Last Name</Label>
              <Input
                id="last_name"
                name="last_name"
                value={formData.last_name}
                onChange={handleChange}
                disabled={isLoading}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Email</Label>
            <Input value={data?.getMyProfile.email || "Loading..."} disabled />
            <p className="text-xs text-muted-foreground">
              Your email address cannot be changed here.
            </p>
          </div>
        </CardContent>
        <CardFooter className="border-t px-6 py-4">
          <div className="flex w-full justify-end">
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
