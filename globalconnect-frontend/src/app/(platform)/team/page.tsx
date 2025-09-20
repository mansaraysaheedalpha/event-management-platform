// src/app/(platform)/team/page.tsx
"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation } from "@apollo/client";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ChevronsUpDown, MoreHorizontal } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSub,
  DropdownMenuSubTrigger,
  DropdownMenuSubContent,
  DropdownMenuPortal,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Loader } from "@/components/ui/loader";
import {
  CREATE_INVITATION_MUTATION,
  UPDATE_MEMBER_ROLE_MUTATION,
  TEAM_DATA_QUERY,
  REMOVE_MEMBER_MUTATION,
} from "@/components/features/Auth/auth.graphql";
import { OrganizationMember } from "@/types";

export default function TeamPage() {
  const [isInviteDialogOpen, setIsInviteDialogOpen] = useState(false);
  const [isRemoveDialogOpen, setIsRemoveDialogOpen] = useState(false);
  const [memberToRemove, setMemberToRemove] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("");
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
  }, []);

  const {
    data,
    loading: loadingMembers,
    error,
    refetch,
  } = useQuery(TEAM_DATA_QUERY);

  const [createInvitation, { loading: sendingInvite }] = useMutation(
    CREATE_INVITATION_MUTATION,
    {
      onCompleted: (data) => {
        toast.success(data.createInvitation);
        setEmail("");
        setRole("");
        setIsInviteDialogOpen(false);
        refetch();
      },
      onError: (error) => toast.error(error.message),
    }
  );

  const [removeMember] = useMutation(REMOVE_MEMBER_MUTATION, {
    onCompleted: () => {
      toast.success("Member removed successfully.");
      refetch();
    },
    onError: (error) => toast.error(error.message),
  });

  const [updateMemberRole] = useMutation(UPDATE_MEMBER_ROLE_MUTATION, {
    onCompleted: (data) => {
      toast.success(`Role updated to ${data.updateMemberRole.role.name}.`);
      refetch();
    },
    onError: (error) => toast.error(error.message),
  });

  const handleInvite = () => {
    if (!email || !role) {
      toast.error("Please enter an email and select a role.");
      return;
    }
    createInvitation({ variables: { input: { email, role } } });
  };

  const handleRemove = async () => {
    if (!memberToRemove) return;

    try {
      await removeMember({ variables: { memberId: memberToRemove.id } });
    } catch (e) {
      // Errors are already handled by the `onError` callback in useMutation,
      // but this catch block prevents an unhandled promise rejection error.
      console.error("Remove member failed", e);
    } finally {
      // This block runs after the mutation is complete, on success or failure.
      setIsRemoveDialogOpen(false);
      setMemberToRemove(null);
    }
  };

  const handleRoleChange = (memberId: string, roleId: string) => {
    updateMemberRole({ variables: { input: { memberId, roleId } } });
  };

  if (error)
    return (
      <p className="text-destructive">
        Error loading team members: {error.message}
      </p>
    );

  return (
    <TooltipProvider>
      <div>
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold">Team Management</h1>
          <Dialog
            open={isInviteDialogOpen}
            onOpenChange={setIsInviteDialogOpen}
          >
            <DialogTrigger asChild>
              <Button>Invite Member</Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[425px]">
              <DialogHeader>
                <DialogTitle>Invite a new team member</DialogTitle>
                <DialogDescription>
                  They will receive an email to create an account and join your
                  organization.
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4">
                <div className="grid grid-cols-4 items-center gap-4">
                  <Label htmlFor="email" className="text-right">
                    Email
                  </Label>
                  <Input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="col-span-3"
                  />
                </div>
                <div className="grid grid-cols-4 items-center gap-4">
                  <Label htmlFor="role" className="text-right">
                    Role
                  </Label>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="outline"
                        className="col-span-3 justify-between"
                      >
                        {role || "Select a role"}
                        <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                      </Button>
                    </DropdownMenuTrigger>

                    <DropdownMenuContent
                      sideOffset={5}
                      className="min-w-[200px] rounded-md border bg-white p-1 shadow-md dark:bg-neutral-900"
                    >
                      {data?.listRolesForOrg.map((orgRole) => (
                        <DropdownMenuItem
                          key={orgRole.id}
                          onSelect={() => setRole(orgRole.name)}
                          className="cursor-pointer px-3 py-2 hover:bg-gray-100 dark:hover:bg-neutral-800"
                        >
                          {orgRole.name}
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
              <DialogFooter>
                <Button
                  type="submit"
                  onClick={handleInvite}
                  disabled={sendingInvite}
                >
                  {sendingInvite ? "Sending..." : "Send Invitation"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>

        <div className="border rounded-lg">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Role</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loadingMembers || !isClient ? (
                <TableRow>
                  <TableCell colSpan={4} className="h-24 text-center">
                    <div className="flex justify-center items-center">
                      <Loader className="h-6 w-6" />
                    </div>
                  </TableCell>
                </TableRow>
              ) : (
                data?.organizationMembers.map(
                  ({ user, role }: OrganizationMember) => {
                    const isOwner = role.name === "OWNER";
                    return (
                      <TableRow key={user.id}>
                        <TableCell>
                          {user.first_name} {user.last_name}
                        </TableCell>
                        <TableCell>{user.email}</TableCell>
                        <TableCell>{role.name}</TableCell>
                        <TableCell className="text-right">
                          {isOwner ? (
                            <Tooltip delayDuration={0}>
                              <TooltipTrigger asChild>
                                <Button variant="ghost" size="icon">
                                  <MoreHorizontal className="h-4 w-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>
                                <p>
                                  The organization owner cannot be modified.
                                </p>
                              </TooltipContent>
                            </Tooltip>
                          ) : (
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" className="h-8 w-8 p-0">
                                  <MoreHorizontal className="h-4 w-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuPortal>
                                <DropdownMenuContent align="end">
                                  <DropdownMenuSub>
                                    <DropdownMenuSubTrigger>
                                      Change Role
                                    </DropdownMenuSubTrigger>
                                    <DropdownMenuPortal>
                                      <DropdownMenuSubContent>
                                        {data?.listRolesForOrg.map(
                                          (orgRole: {
                                            id: string;
                                            name: string;
                                          }) => (
                                            <DropdownMenuItem
                                              key={orgRole.id}
                                              disabled={orgRole.id === role.id}
                                              onSelect={() =>
                                                handleRoleChange(
                                                  user.id,
                                                  orgRole.id
                                                )
                                              }
                                            >
                                              {orgRole.name}
                                            </DropdownMenuItem>
                                          )
                                        )}
                                      </DropdownMenuSubContent>
                                    </DropdownMenuPortal>
                                  </DropdownMenuSub>
                                  <DropdownMenuSeparator />
                                  <DropdownMenuItem
                                    onSelect={() => {
                                      setMemberToRemove({
                                        id: user.id,
                                        name: `${user.first_name} ${user.last_name}`,
                                      });
                                      setIsRemoveDialogOpen(true);
                                    }}
                                    className="text-destructive"
                                  >
                                    Remove Member
                                  </DropdownMenuItem>
                                </DropdownMenuContent>
                              </DropdownMenuPortal>
                            </DropdownMenu>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  }
                )
              )}
            </TableBody>
          </Table>
        </div>

        <AlertDialog
          open={isRemoveDialogOpen}
          onOpenChange={setIsRemoveDialogOpen}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
              <AlertDialogDescription>
                This action will permanently remove{" "}
                <span className="font-bold">{memberToRemove?.name}</span> from
                the organization. They will lose all access.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={handleRemove}
                className="bg-destructive hover:bg-destructive/90"
              >
                Yes, remove member
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </TooltipProvider>
  );
}
