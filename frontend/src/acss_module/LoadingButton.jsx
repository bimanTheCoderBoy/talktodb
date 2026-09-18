import React, { useState } from 'react';
import { Loader2 } from 'lucide-react';

function LoadingButton({ 
  name, 
  onClick, 
  disabled = false, 
  className = '', 
  icon: Icon = null,
  variant = 'primary'
}) {
  const [isLoading, setIsLoading] = useState(false);

  const handleClick = async () => {
    if (isLoading || disabled) return;
    
    setIsLoading(true);
    try {
      await onClick();
    } catch (error) {
      console.error('LoadingButton onClick error:', error);
      // Re-throw to let parent handle if needed
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  // Variant styles
  const variantStyles = {
    primary: 'bg-primary hover:bg-primary/90 text-primary-foreground',
    secondary: 'bg-secondary hover:bg-accent text-foreground',
    success: 'bg-green-500 hover:bg-green-600 text-white',
    danger: 'bg-red-500 hover:bg-red-600 text-white',
  };

  const baseStyles = `
    w-full flex items-center justify-center gap-2 px-3 py-1.5 
    rounded-lg font-medium text-xs transition-all duration-200
  `;

  const disabledStyles = 'bg-muted text-muted-foreground cursor-not-allowed';

  return (
    <button
      onClick={handleClick}
      disabled={disabled || isLoading}
      className={`
        ${baseStyles}
        ${disabled || isLoading ? disabledStyles : variantStyles[variant]}
        ${className}
        cursor-pointer
      `}
    >
      {isLoading ? (
        <>
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          Loading...
        </>
      ) : (
        <>
          {Icon && <Icon className="w-3.5 h-3.5" />}
          {name}
        </>
      )}
    </button>
  );
}

export default LoadingButton;
