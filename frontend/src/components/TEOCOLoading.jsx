import React from "react"

const TeocoLoader = ({ size = 8 }) => {
    return (
      <div className="">
        {/* Injecting Styles Locally for Portability */}
        <style>{`
          /* Perimeter of smaller triangle (approx R=70) is ~360 units.
          */
          @keyframes crazy-flow {
            0% { 
              stroke-dashoffset: 360; 
              stroke-dasharray: 40 320; /* Short tail */
            }
            50% { 
              stroke-dasharray: 140 220; /* Long tail (stretches out) */
              stroke: #64748b; /* Lighter gray when fast */
            }
            100% { 
              stroke-dashoffset: 0; 
              stroke-dasharray: 40 320; /* Short tail */
            }
          }
          
          .animate-crazy-flow {
            stroke-linecap: round;
            /* Cubic-bezier creates the "Zip... Zip..." variable speed effect */
            animation: crazy-flow 1s cubic-bezier(0.6, -0.28, 0.735, 0.045) infinite;
          }
  
          @keyframes energetic-pulse {
             0%, 100% { transform: scale(.6); filter: drop-shadow(0 0 0px rgba(31, 79, 143, 0)); }
             50% { transform: scale(1.1); filter: drop-shadow(0 0 25px rgba(31, 79, 143, 0)); }
          }
          
          .animate-energetic {
            transform-origin: center;
            animation: energetic-pulse 1.2s ease-in-out infinite;
          }
        `}</style>
  
        <div className={`relative w-${size} h-${size} `}>
          {/* Main SVG Container */}
          <svg 
            viewBox="0 0 200 200" 
            xmlns="http://www.w3.org/2000/svg" 
            className="w-full h-full  "
            preserveAspectRatio="xMidYMid meet"
          >
            {/* Background Circle - Dark Blue */}
            <circle cx="100" cy="100" r="95" fill="#0d172b" stroke="#1f4f8f" strokeWidth="5" strokeLinejoin="round" className="animate-energetic" />
            
            {/* Geometry Fix:
               Shrunk Triangle points to ensure the 18px stroke stays INSIDE the circle.
               Radius approx 68px from center.
            */}
            <polygon
              points="100,168 41,66 159,66"
              fill="none"
              stroke="white"
              strokeWidth="22"
              strokeLinejoin="round"
            />
          </svg>
          
          {/* LAYER 2: Animation Overlay 
              - Contains ONLY the moving gray stroke
          */}
          <svg 
            viewBox="0 0 200 200" 
            xmlns="http://www.w3.org/2000/svg" 
            className="absolute inset-0 w-full h-full pointer-events-none"
            preserveAspectRatio="xMidYMid meet"
          >
             {/* The "Crazy" Stroke */}
            <polygon
              points="100,168 41,66 159,66"
              fill="none"
              stroke="#334155" 
              strokeWidth="18" 
              strokeLinejoin="round"
              className="animate-crazy-flow"
            />
          </svg>
        </div>
      </div>
    );
  };
  
  export default TeocoLoader;