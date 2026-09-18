import React from "react";
import { Link } from "react-router-dom";
import { Map, ExternalLink } from "lucide-react";
import fembotIcon from "@/asset/fembot-icon.svg";

const MessageRowMapLink = React.memo(function MessageRowMapLink({ content }) {
  return (
    <div className="my-4 flex items-center gap-3 min-w-0">
      <div className="size-8 rounded-full bg-gradient-to-br from-teoco-real-blue to-teoco-navy-blue flex items-center justify-center ring-2 ring-teoco-real-blue/30">
        <img src={fembotIcon} alt="Assistant" className="w-5 h-5 object-contain" />
      </div>
      <Link
        to={content}
        target="_blank"
        rel="noopener noreferrer"
        className="group flex items-center gap-3 px-5 py-3 bg-gradient-to-r from-teoco-real-blue/20 to-teoco-navy-blue/30 hover:from-teoco-real-blue/30 hover:to-teoco-navy-blue/40 border border-teoco-real-blue/40 hover:border-teoco-real-blue/60 rounded-xl transition-all duration-300 shadow-lg hover:shadow-teoco-real-blue/20"
      >
        <div className="p-2 bg-teoco-real-blue/70 rounded-lg group-hover:bg-teoco-real-blue/130 transition-colors">
          <Map className="w-5 h-5 text-teoco-navy-blue/50" />
        </div>
        <div className="flex flex-col">
          <span className="text-foreground font-semibold text-sm">View Coverage Map</span>
          <span className="text-muted-foreground text-xs">Click to open the interactive map viewer</span>
        </div>
        <ExternalLink className="w-4 h-4 text-teoco-real-blue/70 group-hover:text-teoco-real-blue transition-colors ml-2" />
      </Link>
    </div>
  );
});

export default MessageRowMapLink;
