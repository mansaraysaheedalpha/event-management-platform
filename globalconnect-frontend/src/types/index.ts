// src/types/index.ts

export interface User {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  imageUrl?: string | null;
}

export interface Role {
  id: string;
  name: string;
}

export interface OrganizationMember {
  user: User;
  role: Role;
}
