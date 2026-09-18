import React, { useState, useEffect } from "react";
import { X, Edit2, Check, FolderOpen, FileText } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const FIELD_DEFS = [
  { key: "resolution", label: "Resolution", placeholder: "e.g., 50, 100, 200" },
  { key: "mode", label: "Mode", options: ["Composite"] },
  { key: "terminal", label: "Terminal", placeholder: "e.g.," },
  { key: "height", label: "Height", placeholder: "e.g., 5, 10, 15" },
  {
    key: "carrier",
    label: "Carrier",
    placeholder: "e.g., L800_10M_6400",
    placeholderByTech: {
      lte: "e.g., L800_10M_6400",
      nr: "e.g., 5G-NR-3500_40MHz",
    },
  },
];

function SettingsField({ fieldKey, fieldLabel, placeholder, options, value, onChange, isEditing, onEditClick, onBlur }) {
  if (options) {
    return (
      <Select value={value || ""} onValueChange={onChange}>
        <SelectTrigger className="w-full px-3 py-2 bg-secondary/50 border border-border rounded-lg text-foreground flex items-center justify-between">
          <SelectValue placeholder={`Select ${fieldLabel}`} />
        </SelectTrigger>
        <SelectContent className="z-[10000000] flex flex-col gap-2 bg-popover text-popover-foreground border border-border">
          {options.map((opt) => (
            <SelectItem key={opt} value={opt} className="text-popover-foreground my-1">{opt}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    );
  }

  if (isEditing) {
    return (
      <input
        type="text"
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
        autoFocus
        placeholder={placeholder}
        className="w-full px-3 py-2 bg-card border-2 border-primary dark:border-primary rounded-lg text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary transition-all text-sm"
      />
    );
  }

  return (
    <div
      className="w-full px-3 py-2 bg-secondary/50 border border-border rounded-lg text-foreground flex items-center justify-between cursor-pointer"
      onClick={onEditClick}
    >
      <span className="text-sm font-medium">
        {value || <span className="text-muted-foreground">{placeholder}</span>}
      </span>
      <Edit2 className="w-3.5 h-3.5 text-primary shrink-0" />
    </div>
  );
}

function TechSettingsColumn({ techKey, label, settings, onChange, outputConfig, onOutputChange, editingField, onFieldClick, onFieldBlur }) {
  const handleChange = (field, value) => {
    onChange(techKey, { ...settings, [field]: value });
  };

  return (
    <div className="flex-1 min-w-0">
      <h4 className="text-sm font-bold text-primary uppercase tracking-wider mb-4 pb-2 border-b border-border">
        {label}
      </h4>

      <div className="space-y-3">
        {FIELD_DEFS.map(({ key, label: fieldLabel, placeholder, placeholderByTech, options }) => (
          <div key={`${techKey}-${key}`}>
            <label className="block text-xs font-medium text-muted-foreground mb-1">{fieldLabel}</label>
            <SettingsField
              fieldKey={`${techKey}-${key}`}
              fieldLabel={fieldLabel}
              placeholder={placeholderByTech?.[techKey] || placeholder}
              options={options}
              value={settings?.[key]}
              onChange={(val) => handleChange(key, val)}
              isEditing={editingField === `${techKey}-${key}`}
              onEditClick={() => onFieldClick(`${techKey}-${key}`)}
              onBlur={onFieldBlur}
            />
          </div>
        ))}
      </div>

      {outputConfig && (
        <div className="mt-5 pt-4 border-t border-border">
          <div className="flex items-center gap-1.5 mb-3">
            <FolderOpen className="w-3.5 h-3.5 text-primary" />
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Output</span>
          </div>
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1">Path</label>
              <div className="relative">
                <FolderOpen className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                <input
                  type="text"
                  value={outputConfig?.path || ""}
                  onChange={(e) => onOutputChange(techKey, { ...outputConfig, path: e.target.value })}
                  placeholder="Output path..."
                  className="w-full pl-8 pr-3 py-2 bg-secondary/50 border border-border rounded-lg text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all text-sm"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1">Name</label>
              <div className="relative">
                <FileText className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                <input
                  type="text"
                  value={outputConfig?.name || ""}
                  onChange={(e) => onOutputChange(techKey, { ...outputConfig, name: e.target.value })}
                  placeholder="Output name..."
                  className="w-full pl-8 pr-3 py-2 bg-secondary/50 border border-border rounded-lg text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all text-sm"
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ParameterSettingsModal({
  isOpen,
  onClose,
  urlParameterSettings = {},
  onUrlParameterSettingsChange,
  outputConfig = {},
  onOutputConfigChange
}) {
  const [localSettings, setLocalSettings] = useState(urlParameterSettings);
  const [localOutputConfig, setLocalOutputConfig] = useState(outputConfig);
  const [editingField, setEditingField] = useState(null);

  useEffect(() => { setLocalSettings(urlParameterSettings); }, [urlParameterSettings]);
  useEffect(() => { setLocalOutputConfig(outputConfig); }, [outputConfig]);

  if (!isOpen) return null;

  const handleTechSettingsChange = (techKey, updated) => {
    setLocalSettings(prev => ({ ...prev, [techKey]: updated }));
  };

  const handleOutputChange = (techKey, updated) => {
    setLocalOutputConfig(prev => ({ ...prev, [techKey]: updated }));
  };

  const handleSave = () => {
    if (onUrlParameterSettingsChange) onUrlParameterSettingsChange(localSettings);
    if (onOutputConfigChange) onOutputConfigChange(localOutputConfig);
    onClose();
  };

  const techKeys = Object.keys(localSettings);

  const modalContent = (
    <div className="fixed inset-0 z-[10000] bg-black/60 backdrop-blur-sm flex items-center justify-center p-6">
      <div className="bg-white dark:bg-card rounded-xl shadow-2xl border border-gray-200 dark:border-border w-full max-w-3xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-border bg-linear-to-r from-secondary to-transparent shrink-0">
          <h3 className="text-lg font-semibold text-gray-800 dark:text-foreground">
            Coverage API Parameter Settings
          </h3>
          <button onClick={onClose} className="p-1.5 hover:bg-black/30 dark:hover:bg-accent rounded-lg transition-colors">
            <X className="w-5 h-5 text-gray-600 dark:text-muted-foreground" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 bg-white dark:bg-card">
          {techKeys.length === 0 ? (
            <div className="text-center text-sm text-slate-500 py-8">
              No technology-specific settings available.
            </div>
          ) : techKeys.length === 1 ? (
            <TechSettingsColumn
              techKey={techKeys[0]}
              label={techKeys[0] === "lte" ? "LTE Settings" : "5G NR Settings"}
              settings={localSettings[techKeys[0]]}
              onChange={handleTechSettingsChange}
              outputConfig={localOutputConfig[techKeys[0]]}
              onOutputChange={handleOutputChange}
              editingField={editingField}
              onFieldClick={setEditingField}
              onFieldBlur={() => setEditingField(null)}
            />
          ) : (
            <div className="flex gap-6">
              {techKeys.map((tech) => (
                <TechSettingsColumn
                  key={tech}
                  techKey={tech}
                  label={tech === "lte" ? "LTE Settings" : "5G NR Settings"}
                  settings={localSettings[tech]}
                  onChange={handleTechSettingsChange}
                  outputConfig={localOutputConfig[tech]}
                  onOutputChange={handleOutputChange}
                  editingField={editingField}
                  onFieldClick={setEditingField}
                  onFieldBlur={() => setEditingField(null)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 dark:border-border bg-blue-50/50 dark:bg-secondary/50 flex justify-end space-x-3 shrink-0">
          <button
            onClick={onClose}
            className="px-5 py-2 text-gray-700 dark:text-muted-foreground bg-gray-200 dark:bg-secondary hover:bg-gray-300 dark:hover:bg-accent rounded-lg transition-colors font-medium"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="px-6 py-2 bg-primary hover:bg-primary/90 text-primary-foreground rounded-lg transition-colors font-medium shadow-lg shadow-primary/20"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );

  return modalContent;
}
