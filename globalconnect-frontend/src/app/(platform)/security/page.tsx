// src/app/(platform)/security/page.tsx
"use client";

import { useState } from "react";
import { useMutation } from "@apollo/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  GENERATE_2FA_MUTATION,
  TURN_ON_2FA_MUTATION,
} from "@/components/features/Auth/auth.graphql";

export default function SecurityPage() {
  const [qrCode, setQrCode] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [message, setMessage] = useState("");

  const [generate2FA, { loading: generating }] = useMutation(
    GENERATE_2FA_MUTATION,
    {
      onCompleted: (data) => {
        setQrCode(data.generate2FA.qrCodeDataUrl);
        setMessage(
          "Scan the QR code with your authenticator app and enter the code below."
        );
      },
    }
  );

  const [turnOn2FA, { loading: enabling }] = useMutation(TURN_ON_2FA_MUTATION, {
    onCompleted: (data) => {
      setQrCode(null); // Clear the QR code on success
      setMessage(data.turnOn2FA); // Set success message from backend
    },
    onError: (error) => {
      setMessage(`Error: ${error.message}`);
    },
  });

  const handleEnableSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    turnOn2FA({ variables: { input: { code } } });
  };

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">Account Security</h1>
      <div className="max-w-md space-y-6">
        <div>
          <h2 className="text-xl font-semibold">
            Two-Factor Authentication (2FA)
          </h2>
          <p className="text-muted-foreground mt-1">
            Add an extra layer of security to your account.
          </p>
        </div>

        {!qrCode && (
          <Button onClick={() => generate2FA()} disabled={generating}>
            {generating ? "Generating..." : "Enable 2FA"}
          </Button>
        )}

        {qrCode && (
          <div className="p-4 border rounded-lg">
            <p className="mb-4 text-center">
              Scan this QR Code with your authenticator app (e.g., Google
              Authenticator, Authy).
            </p>
            <div className="flex justify-center">
              <img src={qrCode} alt="2FA QR Code" />
            </div>
            <form onSubmit={handleEnableSubmit} className="mt-4 space-y-4">
              <Label htmlFor="code">Verification Code</Label>
              <Input
                id="code"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="123456"
                maxLength={6}
                required
              />
              <Button type="submit" disabled={enabling}>
                {enabling ? "Verifying..." : "Verify & Enable"}
              </Button>
            </form>
          </div>
        )}

        {message && <p className="text-sm font-medium">{message}</p>}
      </div>
    </div>
  );
}
