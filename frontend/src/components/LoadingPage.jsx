import React from "react";
import AppLoader from "./AppLoader";
import BrandMark from "./BrandMark";

const LoadingPage = () => {
  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-background">
      <div className="flex flex-col items-center justify-center gap-8">
        <AppLoader className="h-14 w-14" />
        <div className="text-center space-y-3">
          <BrandMark size="lg" />
          <p className="text-sm text-muted-foreground">Starting talkToDB…</p>
        </div>
      </div>
    </div>
  );
};

export default LoadingPage;
