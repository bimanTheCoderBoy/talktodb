// import React from "react";
// import TeocoLoader from "./TEOCOLoading";

// const LoadingPage = () => {
//   return (
//     <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-teoco-navy-blue/80">
//       <div className="flex flex-col items-center justify-center gap-6">
//         <div className="w-32 h-32 flex items-center justify-center scale-150">
//           <TeocoLoader />
//         </div>
//         <div className="text-center">
//           <h2 className="text-xl font-semibold text-white mb-2">Loading</h2>
//           <div className="text-2xl font-bold mb-2 bg-gradient-to-r from-white via-teoco-real-blue to-cyan-400 bg-clip-text text-transparent">
//             raNora
//           </div>
//           <p className="text-sm text-gray-400">
//             Please wait while we initialize...
//           </p>
//         </div>
//       </div>
//     </div>
//   );
// };

// export default LoadingPage;

import React from "react";
import TeocoLoader from "./TEOCOLoading";
import logoRaNora from "@/asset/raNora-icon-light-text.svg";

const LoadingPage = () => {
  return (
    // THEME: bg-gradient-to-br from-slate-900 via-slate-800 to-teoco-navy-blue/80 → bg-background (adapts to light/dark)
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-background">
      <div className="flex flex-col items-center justify-center gap-6">
        <div className="w-32 h-32 flex items-center justify-center scale-150">
          <TeocoLoader />
        </div>
        <div className="text-center">
          {/* THEME: text-white → text-foreground (adapts text to theme) */}
          <h2 className="text-xl font-semibold text-foreground mb-2">Loading</h2>
          <img src={logoRaNora} alt="" className="h-8 w-auto mx-auto mb-2 object-contain" />
          {/* THEME: text-gray-400 → text-muted-foreground */}
          <p className="text-sm text-muted-foreground">
            Please wait while we initialize...
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoadingPage;

