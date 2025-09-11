// src/components/features/Auth/TwoFactorForm.tsx
'use client';

import { useState } from 'react';
import { useMutation } from '@apollo/client';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/auth.store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { LOGIN_2FA_MUTATION } from './auth.graphql';

interface TwoFactorFormProps {
  userId: string;
}

export function TwoFactorForm({ userId }: TwoFactorFormProps) {
  const [code, setCode] = useState('');
  const router = useRouter();
  const setAuth = useAuthStore((state) => state.setAuth);

  const [login2FA, { loading, error }] = useMutation(LOGIN_2FA_MUTATION, {
    onCompleted: (data) => {
      const { token, user } = data.login2FA;
      if (token && user) {
        setAuth(token, user);
        router.push('/dashboard');
      }
    },
  });

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    login2FA({ variables: { input: { userId, code } } });
  };

  return (
    <div>
      <h2 className="text-2xl font-bold text-center mb-4">Two-Factor Authentication</h2>
      <p className="text-center text-gray-400 mb-6">Enter the code from your authenticator app.</p>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="code">6-Digit Code</Label>
          <Input
            id="code"
            name="code"
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            maxLength={6}
            required
          />
        </div>
        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? 'Verifying...' : 'Verify & Sign In'}
        </Button>
        {error && <p className="text-red-500 text-sm mt-2">Error: {error.message}</p>}
      </form>
    </div>
  );
}