// src/app/(platform)/auth/reset-password/page.tsx
"use client";

import { useState, useEffect, Suspense } from "react";
import { useMutation } from "@apollo/client";
import Link from "next/link";
import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { PasswordInput } from "@/components/ui/password-input"; // Use our special component
import { Label } from "@/components/ui/label";
import { Loader } from "@/components/ui/loader";
import { PERFORM_PASSWORD_RESET_MUTATION } from "@/components/features/Auth/auth.graphql";

function ResetPasswordComponent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [passwords, setPasswords] = useState({
    newPassword: "",
    confirmPassword: "",
  });
  const [message, setMessage] = useState("");
  const [error, setAppError] = useState("");

  const [performPasswordReset, { loading }] = useMutation(
    PERFORM_PASSWORD_RESET_MUTATION,
    {
      onCompleted: (data) => {
        setMessage(data.performPasswordReset);
        setTimeout(() => router.push("/auth/login"), 3000); // Redirect to login after 3 seconds
      },
      onError: (error) => {
        setAppError(error.message);
      },
    }
  );

  useEffect(() => {
    if (!token) {
      setAppError("No reset token provided. Please request a new link.");
    }
  }, [token]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setPasswords((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setAppError("");
    setMessage("");

    if (passwords.newPassword !== passwords.confirmPassword) {
      setAppError("Passwords do not match.");
      return;
    }
    if (!token) {
      setAppError("Missing reset token.");
      return;
    }

    performPasswordReset({
      variables: {
        input: {
          reset_token: token,
          new_password: passwords.newPassword,
        },
      },
    });
  };

  if (message) {
    return <p className="text-center text-green-400">{message}</p>;
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="newPassword">New Password</Label>
        <PasswordInput
          id="newPassword"
          name="newPassword"
          value={passwords.newPassword}
          onChange={handleChange}
          required
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="confirmPassword">Confirm New Password</Label>
        <PasswordInput
          id="confirmPassword"
          name="confirmPassword"
          value={passwords.confirmPassword}
          onChange={handleChange}
          required
        />
      </div>
      <Button type="submit" className="w-full" disabled={loading || !token}>
        {loading ? <Loader className="mr-2" /> : null}
        {loading ? "Resetting..." : "Reset Password"}
      </Button>
      {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-6">
      <div className="w-full max-w-md">
        <div className="flex justify-center mb-8">
          <Link href="/auth">
            <Image
              src="/logo.png"
              alt="GlobalConnect Logo"
              width={80}
              height={80}
            />
          </Link>
        </div>
        <h1 className="text-3xl font-bold text-center mb-6">
          Set a New Password
        </h1>
        <Suspense fallback={<p>Loading...</p>}>
          <ResetPasswordComponent />
        </Suspense>
      </div>
    </div>
  );
}
