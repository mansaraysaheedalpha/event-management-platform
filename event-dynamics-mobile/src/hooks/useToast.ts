// Toast notification hook — provides a simple API to show transient in-app notifications.
// Uses Zustand for state so toasts can be triggered from anywhere.

import { create } from 'zustand';
import type { ToastMessage, ToastType } from '@/types/notifications';

let toastCounter = 0;

interface ToastState {
  toasts: ToastMessage[];
  addToast: (toast: Omit<ToastMessage, 'id'>) => void;
  removeToast: (id: string) => void;
  clearAll: () => void;
}

const useToastStore = create<ToastState>((set) => ({
  toasts: [],

  addToast: (toast) => {
    toastCounter += 1;
    const id = `toast-${Date.now()}-${toastCounter}`;
    set((state) => ({
      toasts: [{ ...toast, id }, ...state.toasts].slice(0, 5), // max 5 queued
    }));
  },

  removeToast: (id) => {
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    }));
  },

  clearAll: () => set({ toasts: [] }),
}));

export function useToast() {
  const { toasts, addToast, removeToast, clearAll } = useToastStore();

  const toast = (
    title: string,
    options?: { message?: string; type?: ToastType; duration?: number; actionUrl?: string },
  ) => {
    addToast({
      title,
      message: options?.message,
      type: options?.type ?? 'info',
      duration: options?.duration ?? 4000,
      actionUrl: options?.actionUrl,
    });
  };

  const success = (title: string, message?: string) =>
    toast(title, { message, type: 'success' });

  const error = (title: string, message?: string) =>
    toast(title, { message, type: 'error' });

  const info = (title: string, message?: string) =>
    toast(title, { message, type: 'info' });

  const warning = (title: string, message?: string) =>
    toast(title, { message, type: 'warning' });

  return {
    toasts,
    toast,
    success,
    error,
    info,
    warning,
    removeToast,
    clearAll,
  };
}

// Export store for direct access outside React components
export { useToastStore };
