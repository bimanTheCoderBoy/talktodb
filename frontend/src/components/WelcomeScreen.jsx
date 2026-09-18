import React from "react";
import { MessageCircle, Database, Radar, HardDrive } from "lucide-react";
import logoRaNora from "@/asset/raNora-icon-coloured-text.png";

const WelcomeScreen = ( {addNewThread, handleAgentChange  }) => {
  return (
    <div>
    <div className="flex flex-col h-full bg-background overflow-auto  ">
      {/* Beta Badge - Top Bar */}
      <div className="flex justify-center pt-6">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 bg-amber-500/10 border border-amber-500/30 rounded-full">
          <div className="w-2 h-2 bg-amber-400 rounded-full animate-pulse" />
          <span className="text-amber-600 dark:text-amber-400 text-xs font-semibold tracking-wide">raNora v1.5.2</span>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-8">
        {/* Hero Section – logo (icon + text) */}
        <div className="text-center max-w-2xl mb-10">
          <div className="relative mb-4 flex justify-center">
            <div className="absolute inset-0 w-32 h-32 mx-auto bg-teoco-real-blue/20 rounded-full blur-2xl" />
            <img
              src={logoRaNora}
              alt=""
              className="relative w-20 h-auto object-contain drop-shadow-lg"
            />
          </div>
          {/* THEME: text-gray-300 → text-muted-foreground (adapts text color to theme) */}
          <p className="text-muted-foreground text-lg leading-relaxed">
            Your Intelligent Network Management Companion
          </p>
          <p className="text-muted-foreground/70 text-sm max-w-xl mx-auto">
          Leverage AI to query asset DB, run audits, resolve discrepancies, analyze RF coverage, plan new sites, 
                  and visualize your network coverage maps etc. — all through natural conversation
          </p>
        </div>

        {/* Agent Cards – DB Agent (Auditor + Implementor), Coverage Agent (Interactive Maps + ACSS) */}
        <div  className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-5xl w-full mb-8">
          {/* DB Agent – 2 connections: Auditor, Implementor (EDS Fixer) */}
          {/* THEME: bg-slate-800/50 → bg-card, border-slate-700/50 → border-border, text-white → text-foreground */}
          <div onClick={() => handleAgentChange("db_agent", true)} className="cursor-pointer group p-5 bg-card hover:bg-card/80 border border-border hover:border-emerald-500/80 rounded-2xl transition-all duration-300">
            <div className="w-12 h-12 mb-4 rounded-xl bg-gradient-to-br from-emerald-500/20 to-teal-600/30 flex items-center justify-center group-hover:scale-110 transition-transform">
              <Database className="w-6 h-6 text-emerald-400" />
            </div>
            <div className="flex items-center gap-2 mb-3">
              <h3 className="text-foreground font-semibold">DB Agent</h3>
              <span className="px-1.5 py-0.5 text-[10px] bg-emerald-500/20 text-emerald-400 rounded">AGENT</span>
            </div>
            {/* THEME: bg-slate-700/40 → bg-secondary/40, border-slate-600/50 → border-border, text-gray-400 → text-muted-foreground */}
            <div className="space-y-3">
              <div className="p-3 rounded-xl bg-secondary/40 border border-border">
                <p className="text-emerald-400/90 text-xs font-semibold mb-1">Auditor</p>
                <p className="text-muted-foreground text-sm leading-relaxed">
                  Query your asset database in plain English. Run audits, detect discrepancies, and auto-fix issues with EDS Fixer.
                </p>
              </div>
              <div className="p-3 rounded-xl bg-secondary/40 border border-border">
                <p className="text-emerald-400/90 text-xs font-semibold mb-1">Implementor</p>
                <p className="text-muted-foreground text-sm leading-relaxed">
                  EDS Fixer implementation — apply fixes and implement corrections from discrepancy results.
                </p>
              </div>
            </div>
          </div>

          {/* Coverage Agent – 2 connections: Interactive Maps, ASP */}
          {/* THEME: bg-slate-800/50 → bg-card, border-slate-700/50 → border-border */}
          <div onClick={() => handleAgentChange("agent", true)} className="cursor-pointer group p-5 bg-card hover:bg-card/80 border border-border hover:border-teoco-real-blue/90 rounded-2xl transition-all duration-300">
            <div className="w-12 h-12 mb-4 rounded-xl bg-gradient-to-br from-teoco-real-blue/70 to-teoco-navy-blue/30 flex items-center justify-center group-hover:scale-110 transition-transform">
              <Radar className="w-6 h-6 text-teoco-real-blue" />
            </div>
            <div className="flex items-center gap-2 mb-3">
              {/* THEME: text-white → text-foreground */}
              <h3 className="text-foreground font-semibold">Coverage Agent</h3>
              <span className="px-1.5 py-0.5 text-[10px] bg-orange-500/20 text-orange-600 rounded">AGENT</span>
            </div>
            {/* THEME: bg-slate-700/40 → bg-secondary/40, border-slate-600/50 → border-border, text-gray-400 → text-muted-foreground */}
            <div className="space-y-3">
              <div className="p-3 rounded-xl bg-secondary/40 border border-border">
                <p className="text-orange-500 text-xs font-semibold mb-1">Interactive Maps</p>
                <p className="text-muted-foreground text-sm leading-relaxed">
                  Interactive map viewer to explore and visualize coverage layers generated by the Coverage Agent.
                </p>
              </div>
              <div className="p-3 rounded-xl bg-secondary/40 border border-border">
                <p className="text-orange-500 text-xs font-semibold mb-1">ASP</p>
                <p className="text-muted-foreground text-sm leading-relaxed">
                  Automatic Site Placement — evaluates multiple candidates to select the best new site candidate.
                </p>
              </div>
            </div>
          </div>
        </div>

          {/* Computer Agent – filesystem workspace */}
          <div onClick={() => handleAgentChange("computer", true)} className="cursor-pointer group p-5 bg-card hover:bg-card/80 border border-border hover:border-violet-500/80 rounded-2xl transition-all duration-300">
            <div className="w-12 h-12 mb-4 rounded-xl bg-gradient-to-br from-violet-500/20 to-purple-600/30 flex items-center justify-center group-hover:scale-110 transition-transform">
              <HardDrive className="w-6 h-6 text-violet-400" />
            </div>
            <div className="flex items-center gap-2 mb-3">
              <h3 className="text-foreground font-semibold">Computer Agent</h3>
              <span className="px-1.5 py-0.5 text-[10px] bg-violet-500/20 text-violet-400 rounded">AGENT</span>
            </div>
            <div className="space-y-3">
              <div className="p-3 rounded-xl bg-secondary/40 border border-border">
                <p className="text-violet-400/90 text-xs font-semibold mb-1">Filesystem</p>
                <p className="text-muted-foreground text-sm leading-relaxed">
                  Create, read, edit, and manage files in a sandboxed virtual workspace through natural conversation.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Call to Action */}
        <div className="text-center cursor-pointer" onClick={addNewThread}>
          <div className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-teoco-real-blue/10 to-teoco-navy-blue/20 border border-teoco-real-blue/30 rounded-xl">
            <img src={logoRaNora} alt="" className="h-5 w-auto object-contain" aria-hidden />
            {/* THEME: text-gray-300 → text-muted-foreground */}
            <span className="text-muted-foreground">Start a conversation to explore your network insights</span>
          </div>
        </div>
      </div>

     
      <div className="text-center py-4 border-t border-border">
        <p className="text-gray-600 text-xs">
          Powered by{" "}
          <a
            href="https://www.teoco.com/"
            target="_blank"
            rel="noopener noreferrer"
            // className="text-teoco-real-blue font-medium hover:underline"
            className="text-blue-500 hover:text-blue-700 font-medium transition-colors"

          >
            TEOCO
          </a>
        </p>
      </div>
    </div>
  );
};

export default WelcomeScreen;

