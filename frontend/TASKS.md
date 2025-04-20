# Calendar Integrator Demo MVP Tasks

Based on the `frontend_mvp_plan.txt`.

## Week 1: Setup & Authentication

- [x] Set up Next.js 15 project with App Router
- [x] Integrate Tailwind CSS
- [x] Set up Clerk for authentication
- [x] Implement Google OAuth sign-in flow (`app/(auth)/sign-in/page.tsx`)
- [x] Configure Clerk middleware for route protection (`middleware.ts`)
- [ ] Configure tsconfig.json based on best practices (strict mode, paths)
- [ ] Create token retrieval utility (`lib/api/clerk.ts`)
- [ ] Create simple landing page (`app/page.tsx`)
- [ ] Create basic wizard layout (`app/wizard/layout.tsx`)
- [ ] Implement stepper component (`components/wizard/stepper.tsx`)
- [ ] Implement basic wizard navigation buttons (`components/wizard/wizard-buttons.tsx`)

## Week 2: Core Flow

- [ ] Build Step 1: Calendar Link Form (`app/wizard/step-1/page.tsx`)
    - [ ] Implement form UI (`components/wizard/calendar-form.tsx`)
    - [ ] Add form validation using React Hook Form (link regex, duration) (`lib/utils/validation.ts`)
    - [ ] Implement localStorage persistence for form data (`lib/utils/storage.ts`)
    - [ ] Create server action (`app/wizard/actions.ts`) to call backend API (`/api/calendar/process`) for finding slots
- [ ] Build Step 2: Availability Display (`app/wizard/step-2/page.tsx`)
    - [ ] Implement availability list UI (`components/wizard/availability-list.tsx`)
    - [ ] Handle slot selection (radio buttons)
    - [ ] Integrate timezone conversion/formatting using `date-fns` (`lib/utils/date.ts`)
    - [ ] Fetch availability data using server action from Week 2
    - [ ] Enable "Next" button only when a slot is selected
- [ ] Implement API Client utilities (`lib/api/calendar.ts`) - wrapper for fetch calls

## Week 3: Event Creation & Polish

- [ ] Build Step 3: Event Creation Form & Success (`app/wizard/step-3/page.tsx`)
    - [ ] Implement event form UI (`components/wizard/event-form.tsx`)
        - [ ] Display selected slot (read-only)
        - [ ] Add fields: title, description, location
        - [ ] Display participants (fetched from API if provided)
    - [ ] Create server action (`app/wizard/actions.ts`) to call backend API for event creation
    - [ ] Implement success message UI (`components/wizard/success-message.tsx`)
        - [ ] Add event details
        - [ ] Add "View in Calendar" link
        - [ ] Add "Create Another" button (restarts flow)
- [ ] Implement Error Handling
    - [ ] Add inline form validation errors
    - [ ] Add API error toast notifications using Shadcn/UI Toast
    - [ ] Handle auth errors (redirects, messages)
- [ ] Add Loading States/Spinners for API calls
- [ ] Implement Responsive Design using Tailwind utilities
- [ ] Implement Basic Accessibility
    - [ ] Keyboard Navigation (Tab order, Enter/Space)
    - [ ] Add ARIA Labels for forms and buttons
    - [ ] Check Color Contrast
- [ ] Perform Manual E2E Testing of the full flow
- [ ] Refine UI/UX based on testing

## Testing (Ongoing)

- [ ] Write unit tests for form validation (`lib/utils/validation.ts`) using Jest
- [ ] Write unit tests for date formatting (`lib/utils/date.ts`) using Jest
- [ ] Write unit tests for key components (e.g., `calendar-form.tsx`, `availability-list.tsx`) using Jest/RTL

## Deployment

- [ ] Configure Vercel deployment
- [ ] Set up environment variables (`.env`): `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `BACKEND_API_URL`
- [ ] Configure build optimization (if needed)
- [ ] Set up basic error monitoring (console logs initially) 