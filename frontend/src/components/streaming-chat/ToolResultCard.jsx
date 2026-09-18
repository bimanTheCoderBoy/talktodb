import React from "react";
import { Copy, Eye, EyeOff } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Tool,
  ToolContent,
  ToolHeader,
  ToolOutput,
} from "@/components/ui/shadcn-io/ai/tool";

import { LazyMDResponse } from "@/components/ui/shadcn-io/ai/lazy-md-response";
import { Button } from "../ui/button";
import DownloadOptionsButton from "../DownloadOptionsButton";
import { getAllowedDownloadFiletypesForTool, getToolDisplayName } from "@/constants/toolUi";
import { trimLargeTables } from "@/services/downloadService.js";
import { serveImageUrl } from "@/lib/docRagAssetServeUrl"
const ToolResultCard = ({ message, onCopy }) => {
  const toolName = message?.name;
  const displayName = getToolDisplayName(toolName);
  const allowedFiletypes = getAllowedDownloadFiletypesForTool(toolName);
  
  const contentText =
    typeof message?.content === "string"
      ? message.content
      : JSON.stringify(message?.content, null, 2);

  const [open, setOpen] = useState(false);
  const parsedArtifact = (message) => {
    if (message?.artifact) {
      try {
        return JSON.parse(message?.artifact);
      } catch (error) {
        return null;
      }
    }
    return null;
  }
  const trimmedContentText = trimLargeTables(contentText,10);
  return (
    <>
    <Tool defaultOpen={false} open={open} onOpenChange={setOpen} className="w-full max-w-full min-w-0 bg-gray-200 dark:bg-teoco-navy-blue/30 border border-gray-300 dark:border-teoco-real-blue/30">
      <span className="cursor-pointer">
      <ToolHeader state={message?.status} type={`${displayName}` } />
      </span>
      <ToolContent className="w-full min-w-0">
        <ToolOutput
          className="max-w-full"
          output={(
            <div className="p-4 min-w-0">
              <LazyMDResponse className="min-w-0 wrap-anywhere">
                {trimmedContentText}
              </LazyMDResponse>
            </div>
          )}
        />
        <div className="flex items-end justify-end pb-3 gap-2 min-w-full">
          <Button
            variant="outline"
            size="icon"
            className="cursor-pointer"
            onClick={() => setOpen(!open)}
            type="button"
            title="Show less"
          >
            {open ? <EyeOff className="w-4 h-4 " /> : <Eye className="w-4 h-4 " />}
          </Button>
          <Button
            variant="outline"
            size="icon"
            className="cursor-pointer"
            onClick={() => onCopy?.(message?.content)}
            type="button"
            title="Copy Tool Output"
          >
            <Copy className="w-4 h-4 " />
          </Button>

          <DownloadOptionsButton
            content={message?.content}
            allowedFiletypes={allowedFiletypes}
            titlePrefix={`Download ${displayName} Tool Output`}
          />
        </div>
      </ToolContent>
    </Tool>
  {toolName === "doc_retrieval_tool" && parsedArtifact(message)?.citation_map && (
    <div className="min-w-0 cursor-pointer">
      <div className="flex items-center gap-2 mb-3 cursor-pointer">
        <div className="h-4 w-1 bg-teoco-real-blue rounded-full cursor-pointer"></div>
        <p className="text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-wider">References</p>
      </div>
      <div className="flex gap-4 overflow-x-auto pb-4 no-scrollbar scroll-smooth whitespace-nowrap [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
        {Object.values(parsedArtifact(message).citation_map).map((item) => (
          <Link key={item.id} to={`/pdf/${item.source_file}?page=${item.page_start}`} target="_blank" title="View in PDF" className="cursor-pointer">
              <div
              className="shrink-0 w-80 h-36 p-4 bg-gray-100 dark:bg-slate-900/60 border border-gray-300 dark:border-teoco-navy-blue/40 rounded-xl hover:border-teoco-real-blue/50 hover:bg-gray-50 dark:hover:bg-slate-800/80 transition-all cursor-pointer flex flex-col shadow-lg shadow-black/5 dark:shadow-black/20 group"
            >
              <div className="flex gap-3 flex-1 overflow-hidden">
                <div className="flex-1 flex flex-col overflow-hidden text-wrap wrap-break-word">
                  <p className="text-[12px] text-gray-700 dark:text-slate-200 line-clamp-3 leading-relaxed italic group-hover:text-gray-900 dark:group-hover:text-white transition-colors">
                    "{item.content}"
                  </p>
                </div>
                {item.image_urls?.[0] && (
                  <div className="w-16 h-16 shrink-0 rounded-lg overflow-hidden border border-gray-200 dark:border-white/10 bg-gray-200/60 dark:bg-black/20 mt-1">
                    <img
                      src={serveImageUrl(item.image_urls[0])}
                      alt="Preview"
                      className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-300"
                    />
                  </div>
                )}
              </div>

              <div className="mt-2 pt-2 border-t border-gray-200 dark:border-white/5 flex items-center justify-between">
                <div className="flex items-center gap-1.5 overflow-hidden">
                  <div className="w-1.5 h-1.5 rounded-full bg-teoco-real-blue/70"></div>
                  <span className="text-[10px] font-medium text-gray-500 dark:text-slate-400 truncate max-w-[180px]">
                    {item.source_file}
                  </span>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded-md bg-gray-200 dark:bg-teoco-navy-blue/50 text-teoco-real-blue border border-teoco-real-blue/20 font-semibold">
                  Pg {item.page_start}
                </span>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  )}
    </>
  );
};

export default ToolResultCard;

