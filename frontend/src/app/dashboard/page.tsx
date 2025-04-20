'use client';

import { useAuth } from '@clerk/nextjs';
import Link from 'next/link';
import { Button } from '@/components/ui/button';

export default function DashboardPage() {
  const { isLoaded, userId } = useAuth();

  if (!isLoaded) {
    return <div className="flex items-center justify-center min-h-[calc(100vh-3.5rem)] text-muted-foreground">Loading...</div>;
  }

  if (!userId) {
    return null;
  }

  return (
    <div className="flex flex-col items-center py-12 sm:py-16 lg:py-20">
      <main className="flex flex-col items-center gap-10 text-center max-w-3xl w-full px-4">
        <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
          Ready to Schedule?
        </h1>
        <p className="text-lg text-muted-foreground">
          Combine multiple availability links (Calendly, Google Calendar) to find common free slots and create a new event.
        </p>

        <div className="mt-6">
          <Button asChild size="lg">
            <Link href="/wizard/step-1">
              Start Scheduling Wizard
            </Link>
          </Button>
        </div>

      </main>
    </div>
  );
} 