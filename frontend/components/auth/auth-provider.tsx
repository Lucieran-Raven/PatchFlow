import { ClerkProvider } from '@clerk/nextjs';
import { ReactNode } from 'react';

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  return (
    <ClerkProvider
      appearance={{
        variables: {
          colorPrimary: '#0F172A',
          colorText: '#1E293B',
          colorBackground: '#FFFFFF',
          colorInputBackground: '#F8FAFC',
          colorInputText: '#1E293B',
          colorDanger: '#EF4444',
          colorSuccess: '#10B981',
          borderRadius: '0.5rem',
        },
        elements: {
          card: {
            boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
          },
          formButtonPrimary: {
            fontSize: '14px',
            fontWeight: '600',
          },
        },
      }}
    >
      {children}
    </ClerkProvider>
  );
}
