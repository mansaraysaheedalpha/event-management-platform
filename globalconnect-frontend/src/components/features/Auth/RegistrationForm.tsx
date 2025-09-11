// src/components/features/Auth/RegistrationForm.tsx
'use client';

import { useState } from 'react';
import { useMutation } from '@apollo/client';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/auth.store';
import { Button } from '@/components/ui/button';
import { PasswordInput } from '@/components/ui/password-input'; // Use our password component
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner'; // Import the toast function
import { Loader } from "@/components/ui/loader";
import { REGISTER_USER_MUTATION } from './auth.graphql';


export function RegistrationForm() {
  const [formData, setFormData] = useState({
    organization_name: '',
    first_name: '',
    last_name: '',
    email: '',
    password: '',
  });

  const router = useRouter();
  const setAuth = useAuthStore((state) => state.setAuth);

  const [registerUser, { loading }] = useMutation(REGISTER_USER_MUTATION, {
    onCompleted: (data) => {
      const { token, user } = data.registerUser;
      if (token && user) {
        toast.success('Account created successfully!');
        setAuth(token, user);
        router.push('/dashboard');
      }
    },
    onError: (error) => {
      toast.error(error.message);
    },
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    registerUser({ variables: { input: formData } });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4 max-w-sm mx-auto">
      <div className="space-y-2">
        <Label htmlFor="organization_name">Organization Name</Label>
        <Input id="organization_name" name="organization_name" type="text" value={formData.organization_name} onChange={handleChange} required />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="first_name">First Name</Label>
          <Input id="first_name" name="first_name" type="text" value={formData.first_name} onChange={handleChange} required />
        </div>
        <div className="space-y-2">
          <Label htmlFor="last_name">Last Name</Label>
          <Input id="last_name" name="last_name" type="text" value={formData.last_name} onChange={handleChange} required />
        </div>
      </div>
      <div className="space-y-2">
        <Label htmlFor="email">Email</Label>
        <Input id="email" name="email" type="email" value={formData.email} onChange={handleChange} required />
      </div>
      <div className="space-y-2">
        <Label htmlFor="password">Password</Label>
        <PasswordInput id="password" name="password" value={formData.password} onChange={handleChange} required />
      </div>

      <Button type="submit" className="w-full" disabled={loading}>
        {loading ? <Loader className="mr-2" /> : null}
        {loading ? 'Creating Account...' : 'Create Account'}
      </Button>
    </form>
  );
}