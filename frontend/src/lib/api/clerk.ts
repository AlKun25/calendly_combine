'use server';

import { auth, clerkClient } from '@clerk/nextjs/server';

/**
 * Retrieves the Google OAuth access token for the currently authenticated Clerk user.
 * 
 * @returns {Promise<{ success: boolean; token?: string; error?: string }>}
 *          An object containing the success status, the token if successful,
 *          or an error message if failed.
 */
export async function getGoogleOauthToken(): Promise<{
  success: boolean;
  token?: string;
  error?: string;
}> {
  try {
    const authData = await auth(); // Await the auth() promise
    const userId = authData.userId;

    if (!userId) {
      return { success: false, error: 'User not authenticated.' };
    }

    const client = await clerkClient(); // Await the clerkClient() promise

    // Retrieve the OAuth access token for the Google provider
    // Ref: https://clerk.com/blog/using-clerk-sso-access-google-calendar
    // Ref: https://stackoverflow.com/questions/75977883/how-to-get-a-logged-in-users-google-access-token-when-using-clerk-for-auth
    const clerkResponse = await client.users.getUserOauthAccessToken(
      userId,
      'oauth_google' // Provider ID for Google
    );

    if (clerkResponse.data.length === 0) {
      return {
        success: false,
        error: 'Google OAuth token not found for this user.',
      };
    }

    // The response is an array, get the first token
    const googleToken = clerkResponse.data[0].token;

    if (!googleToken) {
       return { success: false, error: 'Empty Google OAuth token received.' };
    }

    console.log("Successfully retrieved Google OAuth token."); // Add server-side log
    return { success: true, token: googleToken };

  } catch (error) {
    console.error("Error retrieving Google OAuth token:", error);
    return {
      success: false,
      error: 'Failed to retrieve Google OAuth token.',
    };
  }
} 