import React, { useState } from "react";


import { StreamingChat } from "./StreamingChat";

const Body = ({ currentThread, setThreads, sidebarOpen, setThreadTitle, addNewThread, setCurrentThread }) => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");

  const sendMessage = (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const newMessage = { id: Date.now(), text: input, sender: "user" };
    setMessages((prev) => [...prev, newMessage]);
    setInput("");
  };

  return (
    // <div className="flex flex-col h-full w-full text-white bg-gradient-to-br from-slate-800 via-slate-700 to-slate-800">
    <div className="flex flex-col h-full w-full text-foreground dark:bg-linear-to-br from-slate-800 via-slate-700 to-slate-800">
      <div className="h-full w-full flex flex-col">
        <StreamingChat currentThread={currentThread} setThreads={setThreads} sidebarOpen={sidebarOpen} setThreadTitle={setThreadTitle}  addNewThread={addNewThread} setCurrentThread={setCurrentThread} />
      </div>
       {/* <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {activeChat ? (
          messages.length > 0 ? (
            messages.map((msg) => (
              <div
                key={msg.id}
                className={`p-3 rounded-lg max-w-lg ${
                  msg.sender === "user"
                    ? "bg-blue-600 self-end"
                    : "bg-gray-700 self-start"
                }`}
              >
                {msg.text}
              </div>
            ))
          ) : (
            <p className="text-gray-400 italic">
              Start typing to chat in <strong>{activeChat.title}</strong>
            </p>
          )
        ) : (
          <p className="text-gray-500 italic absolute top-10 ">Select a chat to start</p>
        )}
      </div>

       <form
        onSubmit={sendMessage}
        className="p-4 border-t border-gray-800 flex items-center gap-2"
      >
        <Input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            activeChat ? "Type your message..." : "Select a chat to start"
          }
          disabled={!activeChat}
          className="flex-1"
        />
        <button
          type="submit"
          disabled={!activeChat}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-md disabled:opacity-50"
        >
          Send
        </button>
      </form> */}
    </div>
  );
};

export default Body;
