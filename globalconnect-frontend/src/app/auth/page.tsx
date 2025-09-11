// src/app/auth/page.tsx
import Link from 'next/link';
import Image from 'next/image';
import { Button } from '@/components/ui/button';

export default function AuthWelcomePage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-6 bg-background text-foreground">
      <div className="text-center">
        <Image src="/logo.png" alt="GlobalConnect Logo" width={100} height={100} className="mx-auto mb-6" />
        <h1 className="text-4xl md:text-5xl font-bold">Welcome to GlobalConnect</h1>
        <p className="mt-4 max-w-xl text-lg text-muted-foreground">The future of event management starts here. Log in to continue or create an account to get started.</p>
        <div className="mt-8 flex justify-center gap-4">
          <Button asChild size="lg">
            <Link href="/auth/login">Login</Link>
          </Button>
          <Button asChild variant="secondary" size="lg">
            <Link href="/auth/register">Register</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}