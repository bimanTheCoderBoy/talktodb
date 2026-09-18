import React from "react";
import TeocoLoader from "../components/TEOCOLoading";

const AcssLoading = ({message = "Loading ASP [Automatic Site Placement]"}) => {
  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-background">
      <div className="flex flex-col items-center justify-center gap-6">
        <div className="w-32 h-32 flex items-center justify-center scale-150">
          <TeocoLoader />
        </div>
        <div className="text-center">
          <h2 className="text-xl font-semibold text-foreground mb-2">
            {message}
          </h2>
          {/* <p className="text-sm text-muted-foreground">
            Please wait while we initialize the ASP session...
          </p> */}
        </div>
      </div>
    </div>
  );
};

export default AcssLoading;

