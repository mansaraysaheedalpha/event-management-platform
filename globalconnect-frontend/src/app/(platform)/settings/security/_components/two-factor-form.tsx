"use client";

import { useQuery, useMutation, gql } from "@apollo/client";
import { toast } from "sonner";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader } from "@/components/ui/loader";
import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import Image from "next/image";
import { Input } from "@/components/ui/input";
import { GENERATE_2FA_MUTATION, GET_MY_PROFILE_2FA_STATUS, TURN_OFF_2FA_MUTATION, TURN_ON_2FA_MUTATION } from "@/graphql/security.graphql";

export function TwoFactorAuthForm() {
  const [qrCode, setQrCode] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const {
    data,
    loading: queryLoading,
    refetch,
  } = useQuery(GET_MY_PROFILE_2FA_STATUS);

  const [generate2FA, { loading: generating }] = useMutation(
    GENERATE_2FA_MUTATION,
    {
      onCompleted: (data) => setQrCode(data.generate2FA.qrCodeDataUrl),
      onError: (error) => toast.error(error.message),
    }
  );

  const [turnOn2FA, { loading: enabling }] = useMutation(TURN_ON_2FA_MUTATION, {
    onCompleted: (data) => {
      toast.success(data.turnOn2FA);
      setQrCode(null);
      refetch();
    },
    onError: (error) => toast.error(error.message),
  });

  const [turnOff2FA, { loading: disabling }] = useMutation(
    TURN_OFF_2FA_MUTATION,
    {
      onCompleted: (data) => {
        toast.success(data.turnOff2FA);
        refetch();
      },
      onError: (error) => toast.error(error.message),
    }
  );

  const handleEnableSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    turnOn2FA({ variables: { input: { code } } });
  };

  const is2FAEnabled = data?.getMyProfile.isTwoFactorEnabled;

  return (
    <>
      <Dialog open={!!qrCode} onOpenChange={() => setQrCode(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Enable Two-Factor Authentication</DialogTitle>
          </DialogHeader>
          <div className="p-4 border rounded-lg text-center">
            <p className="mb-4">
              Scan this QR Code with your authenticator app (e.g., Google
              Authenticator, Authy).
            </p>
            <div className="flex justify-center my-4">
              {qrCode && (
                <Image
                  src={qrCode}
                  alt="2FA QR Code"
                  width={200}
                  height={200}
                />
              )}
            </div>
            <form onSubmit={handleEnableSubmit} className="mt-4 space-y-4">
              <Input
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="Enter 6-digit code"
                maxLength={6}
                required
              />
              <Button type="submit" disabled={enabling} className="w-full">
                {enabling ? <Loader className="mr-2" /> : null}
                Verify & Enable
              </Button>
            </form>
          </div>
        </DialogContent>
      </Dialog>

      <Card>
        <CardHeader>
          <CardTitle>Two-Factor Authentication</CardTitle>
          <CardDescription>
            Add an extra layer of security to your account by requiring a code
            from your authenticator app to log in.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex items-center justify-between">
          {queryLoading ? (
            <Loader />
          ) : is2FAEnabled ? (
            <>
              <p className="text-sm font-medium text-green-600">
                2FA is currently enabled.
              </p>
              <Button
                variant="destructive"
                onClick={() => turnOff2FA()}
                disabled={disabling}
              >
                {disabling && <Loader className="mr-2" />}
                Disable 2FA
              </Button>
            </>
          ) : (
            <>
              <p className="text-sm text-muted-foreground">
                2FA is currently disabled.
              </p>
              <Button onClick={() => generate2FA()} disabled={generating}>
                {generating && <Loader className="mr-2" />}
                Enable 2FA
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </>
  );
}
