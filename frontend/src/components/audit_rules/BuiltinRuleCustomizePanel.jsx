import React, { useEffect, useMemo, useState } from "react";
import { Loader2, RotateCcw, Save } from "lucide-react";
import { toast } from "react-toastify";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { updateBuiltinRuleConfig } from "@/api";

const SELECT_CONTENT_CLASS =
  "z-[10001] bg-slate-800 border border-slate-600 text-white shadow-xl";
const SELECT_ITEM_CLASS = "text-gray-100 focus:bg-slate-700 focus:text-white";

const METRIC_LABELS = {
  eci_assigned: "ECI Assigned",
  ecgi_assigned: "ECGI Assigned",
  tac_assigned: "TAC Assigned",
  carrier_assigned: "PCI Assigned",
  rsi_assigned: "RACH RSI Assigned",
  tx_power_configured: "Max Tx Power Set",
  rs_power_configured: "RS Power (PPRE) Set",
  bandwidth_configured: "Bandwidth Configured",
  carrier_earfcn_configured: "Carrier/EARFCN Set",
  dl_arfcn_configured: "DL ARFCN Configured",
  dl_prbs_configured: "DL PRBs (Bandwidth) Set",
  carrier_aggregation_enabled: "Carrier Aggregation Enabled",
  su_mimo_enabled: "SU-MIMO Enabled",
  mu_mimo_enabled: "MU-MIMO Enabled",
  beamforming_enabled: "Beamforming Enabled",
  coverage_range_configured: "Coverage Range Configured",
  cell_load_configured: "Cell Load Configured",
  downtilt_compliant: "Downtilt Compliant",
  beamforming_supported: "Beamforming Supported",
  sites_with_antennas: "Sites with Antennas",
  sites_with_lte_tac: "Sites with LTE TAC",
  sites_with_nr_tac: "Sites with NR TAC",
  total_cells: "Total Cells",
  lte_cells: "LTE Cells",
  nr_cells: "NR Cells",
};

function deepClone(value) {
  return JSON.parse(JSON.stringify(value ?? {}));
}

function ToggleSwitch({ checked, onChange, label }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer select-none">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-5 w-9 shrink-0 rounded-full border transition-colors ${
          checked ? "bg-teoco-real-blue border-teoco-real-blue" : "bg-slate-600 border-slate-500"
        }`}
      >
        <span
          className={`pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform mt-0.5 ${
            checked ? "translate-x-4" : "translate-x-0.5"
          }`}
        />
      </button>
      {label && <span className="text-sm text-gray-200">{label}</span>}
    </label>
  );
}

function BooleanColumnsEditor({ columns, onChange }) {
  return (
    <div className="space-y-2">
      {(columns || []).map((col, idx) => (
        <div key={col.key} className="flex flex-wrap items-center gap-3 rounded-md border border-slate-700/50 px-3 py-2">
          <ToggleSwitch
            checked={col.enabled !== false}
            onChange={(val) => {
              const next = [...columns];
              next[idx] = { ...col, enabled: val };
              onChange(next);
            }}
            label={col.label || col.key}
          />
          <ToggleSwitch
            checked={col.require_true !== false}
            onChange={(val) => {
              const next = [...columns];
              next[idx] = { ...col, require_true: val };
              onChange(next);
            }}
            label="Require true"
          />
        </div>
      ))}
    </div>
  );
}

function NumericColumnsEditor({ columns, onChange }) {
  return (
    <div className="space-y-2">
      {(columns || []).map((col, idx) => (
        <div key={col.key} className="rounded-md border border-slate-700/50 px-3 py-2 space-y-2">
          <ToggleSwitch
            checked={col.enabled !== false}
            onChange={(val) => {
              const next = [...columns];
              next[idx] = { ...col, enabled: val };
              onChange(next);
            }}
            label={col.label || col.key}
          />
          <div className="flex flex-wrap gap-3 pl-1">
            <ToggleSwitch
              checked={col.require_value === true}
              onChange={(val) => {
                const next = [...columns];
                next[idx] = { ...col, require_value: val };
                onChange(next);
              }}
              label="Require value"
            />
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400">Min</span>
              <Input
                type="number"
                value={col.min ?? ""}
                onChange={(e) => {
                  const next = [...columns];
                  next[idx] = { ...col, min: e.target.value === "" ? null : Number(e.target.value) };
                  onChange(next);
                }}
                className="w-24 h-8 bg-slate-900 border-slate-600 text-white text-sm"
              />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400">Max</span>
              <Input
                type="number"
                value={col.max ?? ""}
                onChange={(e) => {
                  const next = [...columns];
                  next[idx] = { ...col, max: e.target.value === "" ? null : Number(e.target.value) };
                  onChange(next);
                }}
                className="w-24 h-8 bg-slate-900 border-slate-600 text-white text-sm"
              />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function MetricTogglesEditor({ metrics, onChange }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
      {Object.entries(metrics || {}).map(([key, enabled]) => (
        <ToggleSwitch
          key={key}
          checked={enabled !== false}
          onChange={(val) => onChange({ ...metrics, [key]: val })}
          label={METRIC_LABELS[key] || key.replace(/_/g, " ")}
        />
      ))}
    </div>
  );
}

function BuiltinRuleCustomizePanel({ rule, projectName, onSaved, onCancel }) {
  const initialConfig = useMemo(
    () => deepClone(rule?.defaults || {}),
    [rule?.rule_key, rule?.defaults]
  );

  const [config, setConfig] = useState(() => {
    const merged = deepClone(rule?.defaults || {});
    const overrides = rule?.user_config || {};
    return { ...merged, ...overrides, ...(overrides.metrics ? { metrics: { ...merged.metrics, ...overrides.metrics } } : {}) };
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const merged = deepClone(rule?.defaults || {});
    const overrides = rule?.user_config || {};
    if (overrides.metrics && merged.metrics) {
      merged.metrics = { ...merged.metrics, ...overrides.metrics };
    }
    setConfig({ ...merged, ...overrides, ...(merged.metrics ? { metrics: merged.metrics } : {}) });
  }, [rule]);

  const setField = (key, value) => setConfig((prev) => ({ ...prev, [key]: value }));

  const handleReset = () => setConfig(deepClone(initialConfig));

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateBuiltinRuleConfig(projectName, rule.rule_key, config);
      toast.success("Rule configuration saved");
      onSaved?.();
    } catch (err) {
      toast.error(err.message || "Failed to save rule configuration");
    } finally {
      setSaving(false);
    }
  };

  const fields = rule?.config_schema?.fields || [];

  const renderField = (field) => {
    if (field.type === "number") {
      return (
        <div key={field.key}>
          <label className="text-xs text-gray-400 mb-1 block">{field.label}</label>
          <Input
            type="number"
            value={config[field.key] ?? ""}
            onChange={(e) => setField(field.key, e.target.value === "" ? null : Number(e.target.value))}
            className="bg-slate-900 border-slate-600 text-white"
          />
        </div>
      );
    }
    if (field.type === "boolean") {
      return (
        <div key={field.key}>
          <ToggleSwitch
            checked={!!config[field.key]}
            onChange={(val) => setField(field.key, val)}
            label={field.label}
          />
        </div>
      );
    }
    if (field.type === "select") {
      const isBoolSelect = field.key === "expected_value" && field.options?.includes("True");
      const selectValue = isBoolSelect
        ? (config[field.key] === true || config[field.key] === "True" ? "True" : "False")
        : String(config[field.key] ?? field.options?.[0] ?? "");
      return (
        <div key={field.key}>
          <label className="text-xs text-gray-400 mb-1 block">{field.label}</label>
          <Select
            value={selectValue}
            onValueChange={(v) => setField(field.key, isBoolSelect ? v === "True" : v)}
          >
            <SelectTrigger className="w-full bg-slate-900 border-slate-600 text-white">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className={SELECT_CONTENT_CLASS}>
              {(field.options || []).map((opt) => (
                <SelectItem key={opt} value={opt} className={SELECT_ITEM_CLASS}>
                  {opt}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      );
    }
    if (field.type === "boolean_columns") {
      return (
        <div key={field.key} className="md:col-span-2">
          <label className="text-xs text-gray-400 mb-2 block">{field.label}</label>
          <BooleanColumnsEditor
            columns={config[field.key] || config.boolean_columns || config.columns}
            onChange={(val) => setField(field.key in config ? field.key : (config.boolean_columns ? "boolean_columns" : "columns"), val)}
          />
        </div>
      );
    }
    if (field.type === "numeric_columns") {
      return (
        <div key={field.key} className="md:col-span-2">
          <label className="text-xs text-gray-400 mb-2 block">{field.label}</label>
          <NumericColumnsEditor
            columns={config[field.key] || config.columns || config.numeric_columns}
            onChange={(val) => setField(field.key in config ? field.key : (config.numeric_columns ? "numeric_columns" : "columns"), val)}
          />
        </div>
      );
    }
    if (field.type === "metric_toggles") {
      return (
        <div key={field.key} className="md:col-span-2">
          <label className="text-xs text-gray-400 mb-2 block">{field.label}</label>
          <MetricTogglesEditor
            metrics={config.metrics || {}}
            onChange={(val) => setField("metrics", val)}
          />
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {fields.map(renderField)}
      </div>

      <div className="flex items-center gap-2 pt-2">
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-teoco-real-blue hover:bg-teoco-real-blue/90 text-white text-sm disabled:opacity-50"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          Save Configuration
        </button>
        <button
          onClick={handleReset}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg border border-slate-600 text-gray-300 hover:bg-slate-800 text-sm"
        >
          <RotateCcw className="w-4 h-4" />
          Reset to Defaults
        </button>
        <button
          onClick={onCancel}
          className="px-4 py-2 rounded-lg border border-slate-600 text-gray-300 hover:bg-slate-800 text-sm"
        >
          Back to Rules
        </button>
      </div>
    </div>
  );
}

export default BuiltinRuleCustomizePanel;
