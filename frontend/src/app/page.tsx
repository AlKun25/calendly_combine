'use client';

import { SignInButton, SignUpButton, useAuth } from '@clerk/nextjs';
import { useRouter } from 'next/navigation';

export default function LandingPage() {
  const { isLoaded, userId } = useAuth();
  const router = useRouter();

  if (!isLoaded) {
    return <div className="flex items-center justify-center min-h-[calc(100vh-3.5rem)] text-muted-foreground">Loading...</div>;
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-3.5rem)] py-12 sm:py-16 lg:py-20">
      <main className="flex flex-col items-center gap-10 text-center max-w-2xl px-4">
        <div className="w-20 h-20 bg-muted/50 rounded-full flex items-center justify-center text-muted-foreground text-xs mb-2">
          Logo
        </div>

        <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl md:text-6xl">
          Simplify Your Scheduling
        </h1>
        <p className="text-lg text-muted-foreground md:text-xl">
          Combine multiple calendar links (Calendly, Google Calendar, etc.) to find common availability and schedule meetings faster.
        </p>
        
        {!userId && (
          <div className="mt-6 flex flex-col sm:flex-row gap-4 w-full max-w-xs sm:max-w-none">
            <SignInButton mode="modal">
              <button className="flex-1 inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 border border-input bg-background hover:bg-accent hover:text-accent-foreground h-10 px-5 py-2">
                Sign In
              </button>
            </SignInButton>
            <SignUpButton mode="modal">
              <button className="flex-1 inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-5 py-2">
                Sign Up
              </button>
            </SignUpButton>
          </div>
        )}

        {userId && (
           <div className="mt-6">
              <button 
                onClick={() => router.push('/dashboard')} 
                className="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-5 py-2">
                Go to Dashboard
              </button>
           </div>
        )}

        <div className="mt-16 text-xs text-muted-foreground/80">
          [ Animation Placeholder: Visualize calendar merging? ]
        </div>
      </main>
    </div>
  );
}
