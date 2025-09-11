// src/components/layout/CreateOrgModal.tsx
"use client";

import { useState } from "react";
import { useMutation, gql, useApolloClient } from "@apollo/client";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader } from "../ui/loader";
import { useAuthStore } from "@/store/auth.store";
import { GET_MY_ORGS_QUERY } from "./OrganizationSwitcher";

// This mutation now expects an AuthPayload in return
const CREATE_ADDITIONAL_ORGANIZATION = gql`
  mutation CreateAdditionalOrganization(
    $input: OnboardingCreateOrganizationInput!
  ) {
    createAdditionalOrganization(input: $input) {
      token
      user {
        id
        first_name
        last_name
        email
      }
    }
  }
`;

interface CreateOrgModalProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
}

export function CreateOrgModal({ isOpen, onOpenChange }: CreateOrgModalProps) {
  const [name, setName] = useState("");
  const setAuth = useAuthStore((state) => state.setAuth); // <-- GET THE SETAUTH FUNCTION
  const client = useApolloClient();

  const [createOrg, { loading }] = useMutation(CREATE_ADDITIONAL_ORGANIZATION, {
    onCompleted: (data) => {
      const { token, user } = data.createAdditionalOrganization;
      toast.success(`Organization "${name}" created.`);
      setAuth(token, user);
      client.resetStore();

      onOpenChange(false);
    },
    onError: (error) => toast.error(error.message),
  });

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    createOrg({ variables: { input: { name } } });
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Create a new organization</DialogTitle>
            <DialogDescription>
              Give your new organization a name to get started.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <Label htmlFor="org-name">Organization Name</Label>
            <Input
              id="org-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Marketing Team"
              required
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading && <Loader className="mr-2" />}
              Create
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
