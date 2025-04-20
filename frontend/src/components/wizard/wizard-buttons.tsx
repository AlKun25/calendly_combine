import React from 'react';

interface WizardButtonsProps {
  // Define props later, e.g., onNext, onBack, isNextDisabled, isBackDisabled
  onNext?: () => void;
  onBack?: () => void;
  isNextDisabled?: boolean;
  isBackDisabled?: boolean;
  nextText?: string;
  backText?: string;
}

export default function WizardButtons({
  onNext,
  onBack,
  isNextDisabled = false,
  isBackDisabled = false,
  nextText = 'Next',
  backText = 'Back',
}: WizardButtonsProps) {
  // Basic placeholder rendering - replace with actual button elements later
  return (
    <div className="mt-8 pt-6 border-t flex justify-between">
      {/* Back Button Placeholder */}
      <button 
        type="button" 
        onClick={onBack}
        disabled={isBackDisabled}
        className="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 border border-input bg-background hover:bg-accent hover:text-accent-foreground h-10 px-4 py-2"
      >
        {backText}
      </button>

      {/* Next Button Placeholder */}
      <button 
        type="button" 
        onClick={onNext}
        disabled={isNextDisabled}
        className="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-4 py-2"
      >
        {nextText}
      </button>
    </div>
  );
} 