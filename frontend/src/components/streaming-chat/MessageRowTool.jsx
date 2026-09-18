import React, { useMemo } from "react";
import { CoverageReportVisualization } from "@/components/reports/CoverageReportVisualization";
import ToolResultCard from "./ToolResultCard";

const REPORT_TOOL_NAMES = new Set(["get_report_data", "query_report_data"]);

const MessageRowTool = React.memo(function MessageRowTool({ message, onCopy }) {
  const isReport = REPORT_TOOL_NAMES.has(message.name) && message.artifact;

  const reportData = useMemo(() => {
    if (!isReport) return null;
    try {
      return typeof message.artifact === "string"
        ? JSON.parse(message.artifact)
        : message.artifact;
    } catch {
      return null;
    }
  }, [isReport, message.artifact]);

  if (isReport && reportData) {
    return (
      <div className="my-4 min-w-0">
        <CoverageReportVisualization reportData={reportData} />
      </div>
    );
  }

  return <ToolResultCard message={message} onCopy={onCopy} />;
});

export default MessageRowTool;
