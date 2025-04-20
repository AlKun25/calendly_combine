'use server';

import { z } from "zod";

// Replicate or import the form schema if needed for validation on the server
const LinkSchema = z.object({
    value: z.string().url(), // Basic validation for now
});

const FindAvailabilitySchema = z.object({
    links: z.array(LinkSchema).min(2),
    duration: z.number().int().positive(),
});

interface ActionResult {
    success: boolean;
    message?: string;
    data?: any; // Replace 'any' with your expected API response type later
    error?: string;
}

export async function findAvailability(formData: unknown): Promise<ActionResult> {
    console.log("Server Action: findAvailability called");

    // Validate the input using the Zod schema
    const validationResult = FindAvailabilitySchema.safeParse(formData);

    if (!validationResult.success) {
        console.error("Server Action Validation Error:", validationResult.error.flatten());
        return {
            success: false,
            error: "Invalid form data provided.",
            // Optionally include detailed errors: validationResult.error.flatten(),
        };
    }

    const { links, duration } = validationResult.data;

    console.log("Validated Data:", { links, duration });

    // --- TODO: Implement Backend API Call --- 
    // 1. Get user token (e.g., using getAuthToken from clerk.ts)
    // 2. Construct the API request body
    // 3. Use fetch or an API client utility to call your backend endpoint (e.g., POST /api/calendar/process)
    // 4. Handle the API response (success and error cases)
    // 5. Return appropriate ActionResult based on the API response

    // Placeholder response for now
    await new Promise(resolve => setTimeout(resolve, 1000)); // Simulate network delay

    // Simulate success or error for testing
    const success = true; // Math.random() > 0.3; // Simulate occasional errors

    if (success) {
        console.log("Server Action: Simulating successful API call.");
        return {
            success: true,
            message: "Availability check initiated successfully!",
            // data: { ... } // Include actual availability data from API later
        };
    } else {
        console.error("Server Action: Simulating failed API call.");
        return {
            success: false,
            error: "Failed to process calendar links. Please try again later.",
        };
    }
} 