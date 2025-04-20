This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Integration with Calendar Backend

This frontend application interacts with a backend calendar integration service that finds overlapping availability across multiple scheduling links (Calendly and Google Calendar) and creates events.

### Required Frontend Components

1. **Calendar Link Input Form**:
   - Allow users to input multiple calendar links
   - Support for both Calendly and Google Calendar links
   - Option to specify desired meeting duration

2. **Availability Display**:
   - Show overlapping time slots from all calendar links
   - Display participant information derived from links
   - Enable selection of a preferred time slot

3. **Event Creation Form**:
   - Fields for event title, description, and location
   - Participant selection/confirmation
   - Submit button to create the event

### Backend API Integration

The frontend should integrate with these backend endpoints:

1. **Find Overlapping Availability**:
   - Endpoint: `POST /api/calendar/process`
   - Request Body:
     ```json
     {
       "links": [
         {"type": "calendly", "url": "https://calendly.com/user/slot"},
         {"type": "google", "url": "https://calendar.google.com/..."}
       ],
       "duration_minutes": 30 // Optional
     }
     ```
   - Response: List of overlapping time slots and participant details

2. **Create Calendar Event**:
   - Endpoint: `POST /api/calendar/create-event`
   - Request Body:
     ```json
     {
       "slot": {
         "start": "2023-05-01T14:00:00Z",
         "end": "2023-05-01T15:00:00Z"
       },
       "title": "Meeting Title",
       "description": "Meeting description",
       "location": "Virtual",
       "participants": [
         {"email": "user1@example.com", "name": "User 1"},
         {"email": "user2@example.com", "name": "User 2"}
       ]
     }
     ```
   - Response: Details of the created event (ID, link, status)

### Authentication Requirements

The application needs to handle:
- Google OAuth for calendar access (redirects to Google's auth flow)
- Storing and refreshing tokens as needed

### Error Handling

The frontend should gracefully handle:
- Failed API requests
- No overlapping availability
- Authentication failures
- Service-specific errors (e.g., Calendly API issues)

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
