import React, { useEffect, useRef, useState } from "react";
import TeocoLoader from "../TEOCOLoading";
import { THINKING_WORDS } from "./thinkingWords";

const LoadingRow = React.memo(function LoadingRow() {
  const [index, setIndex] = useState(() => Math.floor(Math.random() * THINKING_WORDS.length));
  const [fade, setFade] = useState(true);
  const intervalRef = useRef(null);

  useEffect(() => {
    intervalRef.current = setInterval(() => {
      setFade(false);
      setTimeout(() => {
        setIndex((prev) => (prev + 1) % THINKING_WORDS.length);
        setFade(true);
      }, 200);
    }, 60000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  return (
    <div className="w-full max-w-6xl min-w-0 mx-auto flex items-center gap-3 py-2 px-1">
      <TeocoLoader />
      <span
        className="text-sm font-medium text-muted-foreground transition-opacity duration-200"
        style={{ opacity: fade ? 1 : 0 }}
      >
        {THINKING_WORDS[index]}...
      </span>
    </div>
  );
});

export default LoadingRow;
