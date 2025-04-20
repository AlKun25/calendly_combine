import React from 'react';

interface WizardLayoutProps {
  children: React.ReactNode;
}

export default function WizardLayout({ children }: WizardLayoutProps) {
  return (
    <div className="py-8 sm:py-12">
      {/* Maybe add a container or max-width here later */}
      {/* Placeholder for Stepper component could go here */}
      {/* <Stepper currentStep={...} /> */}
      
      <div className="mt-6">
        {children} 
      </div>

      {/* Placeholder for Navigation buttons could go here */}
      {/* <WizardButtons /> */}
    </div>
  );
} 