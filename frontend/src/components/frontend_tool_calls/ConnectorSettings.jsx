import { useEffect, useState } from "react";
import { Plug } from "lucide-react";
import { Input } from "@/components/ui/input";
import { useConnectorPort } from "./useConnectorPort.js";

export default function ConnectorSettings() {
  const { port, setPort, baseUrl, defaultPort } = useConnectorPort();
  const [draft, setDraft] = useState(String(port));
  const [savedHint, setSavedHint] = useState("");

  useEffect(() => {
    setDraft(String(port));
  }, [port]);

  const save = () => {
    const saved = setPort(draft);
    setDraft(String(saved));
    setSavedHint("Saved");
    window.setTimeout(() => setSavedHint(""), 2000);
  };

  return (
    <div className="px-3 py-2.5 rounded-lg bg-secondary dark:bg-slate-800/50 border border-border dark:border-slate-700/30 space-y-2">
      <div className="flex items-center gap-2 text-xs font-semibold text-foreground">
        <Plug className="h-3.5 w-3.5 text-primary shrink-0" />
        DB connector (local FastAPI)
      </div>
      <p className="text-[11px] text-muted-foreground leading-snug">
        <span className="font-mono">{baseUrl}</span>
        {" · "}
        POST <span className="font-mono">/query</span>
      </p>
      <div className="flex items-center gap-2">
        <span className="text-[11px] text-muted-foreground shrink-0">Port</span>
        <Input
          type="number"
          min={1}
          max={65535}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={save}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              save();
            }
          }}
          placeholder={String(defaultPort)}
          className="h-8 text-xs font-mono"
          aria-label="Connector port"
        />
      </div>
      {savedHint ? (
        <p className="text-[11px] text-emerald-600 dark:text-emerald-400">{savedHint}</p>
      ) : null}
    </div>
  );
}
