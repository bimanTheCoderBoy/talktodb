import React from "react";
import { AlertCircle, RefreshCw, Home } from "lucide-react";
import { useNavigate } from "react-router-dom";

const AcssError = ({ 
  message = "An error occurred", 
  error = null, 
  onRetry = null 
}) => {
  const navigate = useNavigate();

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-background">
      <div className="flex flex-col items-center justify-center gap-6 max-w-md px-6">
        {/* Error Icon */}
        <div className="w-24 h-24 flex items-center justify-center rounded-full bg-red-500/20 border border-red-500/30">
          <AlertCircle className="w-12 h-12 text-red-400" />
        </div>

        {/* Error Message */}
        <div className="text-center">
          <h2 className="text-xl font-semibold text-foreground mb-2">
            ASP Initialization Failed
          </h2>
          <p className="text-sm text-muted-foreground mb-4">
            {message}
          </p>
          {error && (
            <div className="bg-card/50 border border-border rounded-lg p-3 mt-2">
              <p className="text-xs text-red-400 font-mono break-all">
                {error}
              </p>
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex gap-3">
          {onRetry && (
            <button
              onClick={onRetry}
              className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 text-primary-foreground rounded-lg transition-colors duration-200 text-sm font-medium"
            >
              <RefreshCw className="w-4 h-4" />
              Retry
            </button>
          )}
          <button
            onClick={() => navigate("/")}
            className="flex items-center gap-2 px-4 py-2 bg-secondary hover:bg-accent text-foreground rounded-lg transition-colors duration-200 text-sm font-medium"
          >
            <Home className="w-4 h-4" />
            Go Home
          </button>
        </div>
      </div>
    </div>
  );
};

export default AcssError;
