import React from "react";
import { StreamingChat } from "./StreamingChat";

const Body = ({ currentThread, sidebarOpen, setThreadTitle, addNewThread, setCurrentThread }) => {
  return (
    <div className="flex flex-col h-full w-full text-foreground">
      <StreamingChat
        currentThread={currentThread}
        sidebarOpen={sidebarOpen}
        setThreadTitle={setThreadTitle}
        addNewThread={addNewThread}
        setCurrentThread={setCurrentThread}
      />
    </div>
  );
};

export default Body;
