import CalendarForm from "@/components/wizard/calendar-form";

export default function Step1Page() {
  return (
    <div>
      <h2 className="text-2xl font-semibold mb-6">Step 1: Enter Calendar Links</h2>
      <p className="mb-4 text-muted-foreground">
        Please provide the links to the Calendly (or similar) scheduling pages you
        want to find common availability for.
      </p>
      <CalendarForm />
    </div>
  );
} 