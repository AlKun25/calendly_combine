'use client';

import { useAuth } from '@clerk/nextjs';
// Example import for the token retrieval action (adjust path as needed)
// import { getGoogleOauthToken } from '../actions/googleAuthActions'; 
// import { useState } from 'react';

export default function DashboardPage() {
  const { isLoaded, userId } = useAuth();
  // Example state for token handling (remove/modify as needed)
  // const [token, setToken] = useState<string | null>(null);
  // const [error, setError] = useState<string | null>(null);
  // const [isLoadingToken, setIsLoadingToken] = useState(false);

  // Show a loading state while Clerk is initializing
  if (!isLoaded) {
    // Consistent loading state style
    return <div className="flex items-center justify-center min-h-[calc(100vh-3.5rem)] text-muted-foreground">Loading...</div>; 
  }

  // If user is not signed in, render null (or redirect)
  if (!userId) {
    return null; 
  }

  // Example handler for getting token (remove/modify as needed)
  // const handleGetToken = async () => { ... };

  // User is signed in, render the dashboard
  return (
    // Use py for vertical padding, adjust min-height for header height
    <div className="flex flex-col items-center py-12 sm:py-16 lg:py-20">
      {/* Adjusted max-width and gap */}
      <main className="flex flex-col items-center gap-10 text-center max-w-3xl w-full px-4">
        {/* Consistent typography with landing page */}
        <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
          Find the Perfect Meeting Time
        </h1>
        <p className="text-lg text-muted-foreground">
          Paste your Calendly or Google Calendar links below, and we'll find the overlapping times.
        </p>
        
        {/* Input form styled like a Notion block */}
        <div className="w-full mt-4 p-6 border border-border/60 rounded-lg bg-card text-card-foreground shadow-sm text-left">
          <h2 className="text-lg font-medium mb-1">Enter Calendar Links</h2>
          <p className="text-sm text-muted-foreground mb-5">
            (Functionality coming soon!)
          </p>
          <div className="space-y-4">
            <input 
              type="text" 
              placeholder="Paste first calendar link..." 
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              disabled
            />
            {/* Example of adding another input - can be dynamic later */}
            <input 
              type="text" 
              placeholder="Paste second calendar link..." 
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              disabled
            />
            {/* Consider an "Add Link" button here eventually */}
            
            <button 
              type="button" 
              className="mt-2 inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-9 px-4 py-2 w-full"
              disabled
            >
              Find Overlaps (Coming Soon)
            </button>
          </div>
        </div>

         {/* Example section for token button - remove/modify as needed */}
         {/* <div className="w-full mt-8 p-6 border border-border/60 rounded-lg bg-card text-card-foreground shadow-sm text-left"> 
          <h2 className="text-lg font-medium mb-1">Google Calendar Integration</h2>
          <p className="text-sm text-muted-foreground mb-5">
            Connect your Google account to check against your existing events.
          </p>
           <button onClick={handleGetToken} disabled={isLoadingToken} className="... button styles ...">
             {isLoadingToken ? 'Getting Token...' : 'Get Google Calendar Token'}
           </button>
           {token && <p className="text-green-600 mt-2 text-xs">Token retrieved!</p>}
           {error && <p className="text-red-600 mt-2 text-xs">Error: {error}</p>}
        </div> */} 

      </main>
    </div>
  );
} 