// src/app/(platform)/auth/login/page.tsx
import { RegistrationForm } from "@/components/features/Auth/RegistrationForm";
import Link from "next/link";

export default function RegisterPage() {
  return (
    <>
      <h1 className="text-3xl font-bold text-center mb-2">
        Create Your Account
      </h1>
      <p className="text-center text-gray-400 mb-6">
        Join GlobalConnect and redefine events.
      </p>
      <RegistrationForm />
      <p className="text-center text-sm text-gray-400 mt-6">
        Already have an account?{" "}
        <Link
          href="/auth/login"
          className="font-semibold text-primary hover:underline"
        >
          Sign In
        </Link>
      </p>
    </>
  );
}
