'use client';

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, useFieldArray } from "react-hook-form";
import { z } from "zod";
import { toast } from "sonner";
import { PlusIcon, TrashIcon } from "@heroicons/react/24/outline";
import { CalendarDays, Link as LinkIcon, Loader2 } from "lucide-react";
import { useTransition } from 'react';

import { Button } from "@/components/ui/button";
import {
    Form,
    FormControl,
    FormField,
    FormItem,
    FormLabel,
    FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { findAvailability } from "@/app/wizard/actions";

// Helper function to check URL hostname
const isValidCalendarUrl = (url: string): boolean => {
    try {
        const parsedUrl = new URL(url);
        return [
            "calendly.com",
            "www.calendly.com",
            "calendar.google.com"
        ].includes(parsedUrl.hostname);
    } catch (_) {
        return false; // Invalid URL format
    }
};

// Updated schema for an array of links
const LinkSchema = z.object({
    value: z.string()
        .url({ message: "Please enter a valid URL." })
        .refine(isValidCalendarUrl, {
            message: "URL must be from calendly.com or calendar.google.com.",
        }),
});

// Define allowed duration values (in minutes)
const allowedDurations = [30, 60, 90, 120, 150] as const;

const FormSchema = z.object({
    links: z.array(LinkSchema).min(2, "Please provide at least two calendar links."),
    duration: z.coerce // Coerce string value from select to number
        .number({ invalid_type_error: "Please select a duration." })
        .refine((val) => allowedDurations.includes(val as typeof allowedDurations[number]), {
            message: "Please select a valid duration.",
        }),
});

type FormValues = z.infer<typeof FormSchema>;

// Define duration options for the Select component
const durationOptions = [
    { value: 15, label: "15 Minutes" },
    { value: 30, label: "30 Minutes" },
    { value: 45, label: "45 Minutes" },
    { value: 60, label: "1 Hour" },
    { value: 75, label: "1 Hour 15 Minutes" },
    { value: 90, label: "1 Hour 30 Minutes" },
    { value: 105, label: "1 Hour 45 Minutes" },
    { value: 120, label: "2 Hours" },
    { value: 135, label: "2 Hours 15 Minutes" },
    { value: 150, label: "2 Hours 30 Minutes" },
];

// Define default form values outside the component
const defaultFormValues: FormValues = {
    links: [{ value: "" }, { value: "" }],
    duration: 30,
};

export default function CalendarForm() {
    const [isPending, startTransition] = useTransition();

    const form = useForm<FormValues>({
        resolver: zodResolver(FormSchema),
        defaultValues: defaultFormValues, // Use static default values
        mode: "onChange",
    });

    const { fields, append, remove } = useFieldArray({
        control: form.control,
        name: "links"
    });

    // Log validation state for debugging
    console.log("Form Validity:", form.formState.isValid);
    console.log("Form Errors:", form.formState.errors);

    async function onSubmit(data: FormValues) {
        console.log("Form submitted with data:", data); // Adjusted log

        startTransition(async () => {
            try {
                const result = await findAvailability(data);

                if (result.success) {
                    toast.success(result.message || "Availability check started!");
                    console.log("Server Action Result (Success):", result.data);
                    // TODO: Navigate to the next step or handle success
                    // router.push('/wizard/step-2'); // Example navigation
                } else {
                    toast.error(result.error || "An unknown error occurred.");
                    console.error("Server Action Result (Error):", result.error);
                }
            } catch (error) {
                toast.error("Failed to communicate with the server.");
                console.error("Error calling server action:", error);
            }
        });
    }

    return (
        <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
                <div className="space-y-4">
                    {fields.map((item, index) => (
                        <FormField
                            key={item.id}
                            control={form.control}
                            name={`links.${index}.value` as const}
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel className="flex justify-between items-center">
                                        <span>{`Calendar Link ${index + 1}`}</span>
                                        {/* Allow removing only extra links */} 
                                        {index >= 2 && (
                                            <Button
                                                type="button"
                                                variant="ghost"
                                                size="icon"
                                                className="h-6 w-6 text-muted-foreground hover:text-destructive"
                                                onClick={() => remove(index)}
                                            >
                                                <TrashIcon className="h-4 w-4" />
                                                <span className="sr-only">Remove Link</span>
                                            </Button>
                                        )}
                                    </FormLabel>
                                    <FormControl>
                                        <div className="relative">
                                            <span className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground">
                                                {field.value?.includes("calendar.google.com") ? (
                                                    <CalendarDays className="h-4 w-4" />
                                                ) : field.value?.includes("calendly.com") ? (
                                                    <LinkIcon className="h-4 w-4" />
                                                ) : null} 
                                            </span>
                                            <Input
                                                placeholder="https://calendly.com/user/meeting" 
                                                {...field}
                                                className="pl-8" // Add padding for the icon
                                            />
                                        </div>
                                    </FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />
                    ))}
                </div>

                <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="mt-2"
                    onClick={() => append({ value: "" })} // Add a new empty link object
                >
                    <PlusIcon className="mr-2 h-4 w-4" />
                    Add Another Link
                </Button>

                {/* Duration Select Field */}
                <FormField
                    control={form.control}
                    name="duration"
                    render={({ field }) => (
                        <FormItem>
                            <FormLabel>Meeting Duration</FormLabel>
                            <Select
                                // Explicitly parse the incoming string value to a number for field.onChange
                                onValueChange={(value: string) => field.onChange(value ? parseInt(value, 10) : undefined)}
                                value={String(field.value ?? '')} // Ensure value is always a string
                            >
                                <FormControl>
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select a duration" />
                                    </SelectTrigger>
                                </FormControl>
                                <SelectContent 
                                    className="bg-background shadow-md"
                                >
                                    {durationOptions.map((option) => (
                                        <SelectItem key={option.value} value={String(option.value)}>
                                            {option.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            <FormMessage />
                        </FormItem>
                    )}
                />

                <div className="pt-4">
                    <Button 
                        type="submit" 
                        disabled={!form.formState.isValid || isPending} // Disable during submission
                    >
                        {isPending ? (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : null}
                        {isPending ? "Checking..." : "Find Availability"} 
                    </Button>
                </div>
            </form>
        </Form>
    );
} 