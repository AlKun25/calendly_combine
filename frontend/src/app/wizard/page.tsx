import { redirect } from 'next/navigation';

export default function WizardPage() {
  // Immediately redirect to the first step of the wizard
  redirect('/wizard/step-1');

  // This part will technically not be reached, but returning null is good practice
  return null;
} 