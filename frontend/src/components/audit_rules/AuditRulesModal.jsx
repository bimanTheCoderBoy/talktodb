import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { X, Loader2, Plus, Trash2, Pencil, Save, ShieldCheck, ArrowLeft, Download, Upload } from "lucide-react";
import { toast } from "react-toastify";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  getAuditRulesCatalog,
  getAuditRules,
  createCustomAuditRule,
  updateCustomAuditRule,
  deleteCustomAuditRule,
  updateAuditRulePreferences,
  downloadBuiltinRuleConfigsCsv,
  uploadBuiltinRuleConfigsCsv,
} from "@/api";
import {
  buildCustomRulePayload,
  customRuleToForm,
  emptyColumnCheck,
  emptyCustomRuleForm,
  formatColumnCheckSummary,
  formatRuleTablesSummary,
  getCheckParamInputKind,
  getTablesForEntity,
  pickRuleTypeForColumn,
  resolveRuleTypeOptionsForCheck,
  validateCustomRuleForm,
  BOOLEAN_VALUE_OPTIONS,
} from "./auditRulesValidation";
import BuiltinRuleCustomizePanel from "./BuiltinRuleCustomizePanel";

function ToggleSwitch({ checked, onChange, label }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer select-none">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-5 w-9 shrink-0 rounded-full border transition-colors ${
          checked ? "bg-teoco-real-blue border-teoco-real-blue" : "bg-muted border-border"
        }`}
      >
        <span
          className={`pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform mt-0.5 ${
            checked ? "translate-x-4" : "translate-x-0.5"
          }`}
        />
      </button>
      {label && <span className="text-sm text-foreground">{label}</span>}
    </label>
  );
}

function FieldError({ message }) {
  if (!message) return null;
  return <p className="text-xs text-red-400 mt-1">{message}</p>;
}

const SELECT_CONTENT_CLASS =
  "z-[10001] bg-popover border border-border text-popover-foreground shadow-xl";
const SELECT_ITEM_CLASS = "text-popover-foreground focus:bg-accent focus:text-accent-foreground";

function AuditRulesModal({ isOpen, onClose, projectName }) {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [catalog, setCatalog] = useState(null);
  const [rulesData, setRulesData] = useState(null);
  const [activeTab, setActiveTab] = useState("default");
  const [editingRule, setEditingRule] = useState(null);
  const [form, setForm] = useState(emptyCustomRuleForm());
  const [formErrors, setFormErrors] = useState({});
  const [pendingPrefs, setPendingPrefs] = useState({});
  const [customizingRule, setCustomizingRule] = useState(null);
  const [modalView, setModalView] = useState("list"); // list | customize | custom_form
  const [csvBusy, setCsvBusy] = useState(false);
  const csvInputRef = useRef(null);

  const loadData = useCallback(async () => {
    if (!projectName) return;
    setLoading(true);
    setPendingPrefs({});
    try {
      const catalogRes = await getAuditRulesCatalog();
      setCatalog(catalogRes);
    } catch (err) {
      toast.error(err.message || "Failed to load audit rule catalog");
    }
    try {
      const rulesRes = await getAuditRules(projectName);
      setRulesData(rulesRes);
    } catch (err) {
      toast.error(err.message || "Failed to load audit rules");
      setRulesData(null);
    } finally {
      setLoading(false);
    }
  }, [projectName]);

  useEffect(() => {
    if (isOpen) {
      setActiveTab("default");
      setEditingRule(null);
      setForm(emptyCustomRuleForm());
      setFormErrors({});
      setCustomizingRule(null);
      setModalView("list");
      loadData();
    }
  }, [isOpen, loadData]);

  const availableTables = useMemo(() => {
    return getTablesForEntity(catalog, form.entity_type);
  }, [catalog, form.entity_type]);

  const getTableMeta = useCallback(
    (tableName) => availableTables.find((t) => t.table_name === tableName),
    [availableTables]
  );

  const handlePrefToggle = (ruleKey, enabled) => {
    setPendingPrefs((prev) => ({ ...prev, [ruleKey]: enabled }));
    setRulesData((prev) => {
      if (!prev) return prev;
      const updateList = (list) =>
        list.map((r) => (r.rule_key === ruleKey ? { ...r, is_enabled: enabled } : r));
      return {
        ...prev,
        builtin_rules: updateList(prev.builtin_rules),
        custom_rules: updateList(prev.custom_rules),
      };
    });
  };

  const savePreferences = async () => {
    const entries = Object.entries(pendingPrefs);
    if (entries.length === 0) {
      toast.info("No preference changes to save");
      return;
    }
    setSaving(true);
    try {
      await updateAuditRulePreferences({
        projectName,
        preferences: entries.map(([rule_key, is_enabled]) => ({ rule_key, is_enabled })),
      });
      toast.success("Rule preferences saved");
      setPendingPrefs({});
    } catch (err) {
      toast.error(err.message || "Failed to save preferences");
    } finally {
      setSaving(false);
    }
  };

  const openCreateForm = () => {
    setEditingRule(null);
    setForm(emptyCustomRuleForm());
    setFormErrors({});
    setActiveTab("custom");
    setModalView("custom_form");
  };

  const openEditForm = (rule) => {
    setEditingRule(rule);
    setForm(customRuleToForm(rule));
    setFormErrors({});
    setActiveTab("custom");
    setModalView("custom_form");
  };

  const openCustomize = (rule) => {
    setCustomizingRule(rule);
    setActiveTab("default");
    setModalView("customize");
  };

  const backToList = () => {
    setModalView("list");
    setCustomizingRule(null);
    setEditingRule(null);
    setFormErrors({});
  };

  const handleFormChange = (field, value) => {
    setForm((prev) => {
      const next = { ...prev, [field]: value };
      if (field === "entity_type") {
        next.column_checks = [emptyColumnCheck()];
      }
      return next;
    });
    setFormErrors((prev) => ({ ...prev, [field]: undefined, column_checks: undefined }));
  };

  const updateColumnCheck = (checkId, field, value) => {
    setForm((prev) => ({
      ...prev,
      column_checks: prev.column_checks.map((check) => {
        if (check.id !== checkId) return check;
        const updated = { ...check, [field]: value };
        if (field === "table_name") {
          updated.column = "";
          updated.rule_type = "not_null";
          updated.rule_params = {};
        }
        if (field === "column") {
          updated.rule_type = pickRuleTypeForColumn(
            catalog,
            updated.table_name,
            value,
            updated.rule_type
          );
          updated.rule_params = {};
        }
        if (field === "rule_type") {
          updated.rule_params = {};
        }
        return updated;
      }),
    }));
    setFormErrors((prev) => ({ ...prev, column_checks: undefined }));
  };

  const updateCheckParam = (checkId, param, value, checkIndex) => {
    setForm((prev) => ({
      ...prev,
      column_checks: prev.column_checks.map((check) =>
        check.id === checkId
          ? { ...check, rule_params: { ...check.rule_params, [param]: value } }
          : check
      ),
    }));
    setFormErrors((prev) => ({
      ...prev,
      column_checks: undefined,
      ...(checkIndex >= 0 ? { [`check_${checkIndex}_param_${param}`]: undefined } : {}),
    }));
  };

  const addColumnCheck = () => {
    setForm((prev) => ({
      ...prev,
      column_checks: [...prev.column_checks, emptyColumnCheck()],
    }));
    setFormErrors((prev) => ({ ...prev, column_checks: undefined }));
  };

  const removeColumnCheck = (checkId) => {
    setForm((prev) => ({
      ...prev,
      column_checks: prev.column_checks.filter((check) => check.id !== checkId),
    }));
    setFormErrors((prev) => ({ ...prev, column_checks: undefined }));
  };

  const submitCustomRule = async () => {
    const errors = validateCustomRuleForm(form, catalog, {
      existingRules: rulesData?.custom_rules || [],
      editingRuleId: editingRule?.id ?? null,
    });
    setFormErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setSaving(true);
    try {
      const payload = buildCustomRulePayload(form, catalog);
      if (editingRule) {
        await updateCustomAuditRule(projectName, editingRule.id, payload);
        toast.success("Custom rule updated");
      } else {
        await createCustomAuditRule(projectName, payload);
        toast.success("Custom rule created");
      }
      setEditingRule(null);
      setForm(emptyCustomRuleForm());
      setModalView("list");
      await loadData();
    } catch (err) {
      toast.error(err.message || "Failed to save custom rule");
    } finally {
      setSaving(false);
    }
  };

  const handleDownloadConfigsCsv = async () => {
    setCsvBusy(true);
    try {
      const { blob, filename } = await downloadBuiltinRuleConfigsCsv(projectName);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      toast.success("Rule configurations downloaded");
    } catch (err) {
      toast.error(err.message || "Failed to download configurations");
    } finally {
      setCsvBusy(false);
    }
  };

  const handleUploadConfigsCsv = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    setCsvBusy(true);
    try {
      const result = await uploadBuiltinRuleConfigsCsv(projectName, file);
      toast.success(`Imported configurations for ${result.updated_rules} rule(s)`);
      await loadData();
    } catch (err) {
      toast.error(err.message || "Failed to upload configurations");
    } finally {
      setCsvBusy(false);
    }
  };

  const handleDeleteRule = async (rule) => {
    if (!window.confirm(`Delete custom rule "${rule.name}"?`)) return;
    setSaving(true);
    try {
      await deleteCustomAuditRule(projectName, rule.id);
      toast.success("Custom rule deleted");
      if (editingRule?.id === rule.id) {
        setModalView("list");
        setEditingRule(null);
      }
      await loadData();
    } catch (err) {
      toast.error(err.message || "Failed to delete rule");
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  const hasPendingPrefs = Object.keys(pendingPrefs).length > 0;
  const isSubView = modalView !== "list";
  const headerTitle =
    modalView === "customize"
      ? `Customize: ${customizingRule?.name || "Rule"}`
      : modalView === "custom_form"
        ? editingRule
          ? "Edit Custom Rule"
          : "Create Custom Rule"
        : "Audit Rules";

  return (
    <div className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-4xl max-h-[90vh] flex flex-col rounded-xl border border-border bg-card shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border bg-secondary/50">
          <div className="flex items-center gap-3 min-w-0">
            {isSubView && (
              <button
                onClick={backToList}
                className="p-1.5 rounded-lg hover:bg-accent text-muted-foreground hover:text-foreground transition-colors shrink-0"
                title="Back to rules"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
            )}
            {!isSubView && <ShieldCheck className="w-5 h-5 text-teoco-real-blue shrink-0" />}
            <div className="min-w-0">
              <h2 className="text-lg font-semibold text-foreground truncate">{headerTitle}</h2>
              {!isSubView && (
                <p className="text-xs text-muted-foreground">
                  Enable or disable rules for project <span className="text-teoco-real-blue">{projectName}</span>
                </p>
              )}
              {modalView === "customize" && customizingRule?.description && (
                <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{customizingRule.description}</p>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-accent text-muted-foreground hover:text-foreground transition-colors shrink-0"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {!isSubView && (
          <div className="flex border-b border-border px-5 gap-1">
            {[
              { id: "default", label: "Default Rules" },
              { id: "custom", label: "Custom Rules" },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? "border-teoco-real-blue text-teoco-real-blue"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        )}

        <div className="flex-1 overflow-y-auto p-5">
          {loading ? (
            <div className="flex items-center justify-center py-16 text-muted-foreground gap-2">
              <Loader2 className="w-5 h-5 animate-spin" />
              Loading audit rules...
            </div>
          ) : modalView === "customize" && customizingRule ? (
            <BuiltinRuleCustomizePanel
              rule={customizingRule}
              projectName={projectName}
              onSaved={async () => {
                backToList();
                await loadData();
              }}
              onCancel={backToList}
            />
          ) : modalView === "custom_form" ? (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Custom rules apply only to Detailed (1–10 entities) and Moderate (11–50 entities) audits.
              </p>
              <div className="rounded-lg border border-border bg-card/40 p-4 space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-muted-foreground mb-1 block">Rule Name *</label>
                    <Input
                      value={form.name}
                      onChange={(e) => handleFormChange("name", e.target.value)}
                      placeholder="e.g. PCI must be configured"
                      className="bg-background border-border text-foreground"
                      aria-invalid={!!formErrors.name}
                    />
                    <FieldError message={formErrors.name} />
                  </div>

                  <div>
                    <label className="text-xs text-muted-foreground mb-1 block">Entity Type *</label>
                    <Select value={form.entity_type} onValueChange={(v) => handleFormChange("entity_type", v)}>
                      <SelectTrigger className="w-full bg-background border-border text-foreground">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className={SELECT_CONTENT_CLASS}>
                        <SelectItem value="cell" className={SELECT_ITEM_CLASS}>Cell</SelectItem>
                        <SelectItem value="site" className={SELECT_ITEM_CLASS}>Site</SelectItem>
                      </SelectContent>
                    </Select>
                    <FieldError message={formErrors.entity_type} />
                  </div>
                </div>

                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">Description</label>
                  <Textarea
                    value={form.description}
                    onChange={(e) => handleFormChange("description", e.target.value)}
                    placeholder="Optional description for this rule"
                    className="bg-background border-border text-foreground min-h-[60px]"
                    maxLength={500}
                  />
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <label className="text-xs text-muted-foreground block">Column Checks *</label>
                      <p className="text-[10px] text-muted-foreground mt-0.5">
                        Pick columns from any related tables (cells, site, antennas). All checks must pass (AND).
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={addColumnCheck}
                      disabled={form.column_checks.length >= 10}
                      className="flex items-center gap-1 px-2.5 py-1 rounded-md border border-border text-xs text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-50"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      Add Check
                    </button>
                  </div>
                  <FieldError message={formErrors.column_checks} />

                  <div className="space-y-3">
                    {form.column_checks.map((check, index) => {
                      const allowedRuleTypes = resolveRuleTypeOptionsForCheck(
                        catalog,
                        check.table_name,
                        check.column
                      );
                      const ruleTypeMeta = allowedRuleTypes.find((rt) => rt.value === check.rule_type);
                      const checkTable = getTableMeta(check.table_name);
                      const usedPairs = form.column_checks
                        .filter((c) => c.id !== check.id)
                        .map((c) => `${c.table_name}::${c.column}`)
                        .filter((pair) => !pair.startsWith("::"));
                      const availableColumns = (checkTable?.columns || []).filter(
                        (col) => !usedPairs.includes(`${check.table_name}::${col.name}`)
                      );
                      const prefix = `check_${index}`;

                      return (
                        <div
                          key={check.id}
                          className="rounded-lg border border-border bg-background/60 p-3 space-y-3"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <p className="text-xs font-medium text-foreground">Check {index + 1}</p>
                            {form.column_checks.length > 1 && (
                              <button
                                type="button"
                                onClick={() => removeColumnCheck(check.id)}
                                className="p-1 rounded hover:bg-accent text-muted-foreground hover:text-red-400"
                                title="Remove check"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </div>

                          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                            <div>
                              <label className="text-xs text-muted-foreground mb-1 block">Table *</label>
                              <Select
                                value={check.table_name || undefined}
                                onValueChange={(v) => updateColumnCheck(check.id, "table_name", v)}
                              >
                                <SelectTrigger className="w-full bg-background border-border text-foreground">
                                  <SelectValue placeholder="Select table" />
                                </SelectTrigger>
                                <SelectContent className={SELECT_CONTENT_CLASS}>
                                  {availableTables.map((t) => (
                                    <SelectItem key={t.table_name} value={t.table_name} className={SELECT_ITEM_CLASS}>
                                      {t.label}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                              <FieldError message={formErrors[`${prefix}_table`]} />
                            </div>

                            <div>
                              <label className="text-xs text-muted-foreground mb-1 block">Column *</label>
                              <Select
                                value={check.column || undefined}
                                onValueChange={(v) => updateColumnCheck(check.id, "column", v)}
                                disabled={!check.table_name}
                              >
                                <SelectTrigger className="w-full bg-background border-border text-foreground">
                                  <SelectValue placeholder="Select column" />
                                </SelectTrigger>
                                <SelectContent className={SELECT_CONTENT_CLASS}>
                                  {availableColumns.map((col) => (
                                    <SelectItem key={col.name} value={col.name} className={SELECT_ITEM_CLASS}>
                                      {col.label}
                                    </SelectItem>
                                  ))}
                                  {check.column &&
                                    !availableColumns.some((col) => col.name === check.column) && (
                                      <SelectItem value={check.column} className={SELECT_ITEM_CLASS}>
                                        {check.column}
                                      </SelectItem>
                                    )}
                                </SelectContent>
                              </Select>
                              <FieldError message={formErrors[`${prefix}_column`]} />
                            </div>

                            <div>
                              <label className="text-xs text-muted-foreground mb-1 block">Check Type *</label>
                              <Select
                                value={check.rule_type}
                                onValueChange={(v) => updateColumnCheck(check.id, "rule_type", v)}
                                disabled={!check.column}
                              >
                                <SelectTrigger className="w-full bg-background border-border text-foreground">
                                  <SelectValue placeholder={check.column ? "Select check type" : "Select column first"} />
                                </SelectTrigger>
                                <SelectContent className={SELECT_CONTENT_CLASS}>
                                  {allowedRuleTypes.map((rt) => (
                                    <SelectItem key={rt.value} value={rt.value} className={SELECT_ITEM_CLASS}>
                                      {rt.label}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                              {ruleTypeMeta && (
                                <p className="text-[10px] text-muted-foreground mt-1">{ruleTypeMeta.description}</p>
                              )}
                              <FieldError message={formErrors[`${prefix}_rule_type`]} />
                            </div>
                          </div>

                          {ruleTypeMeta?.requires_params?.length > 0 && (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                              {ruleTypeMeta.requires_params.map((param) => {
                                const inputKind = getCheckParamInputKind(catalog, check, param);
                                const rawParamValue = check.rule_params?.[param] ?? "";
                                const normalizedBooleanValue =
                                  rawParamValue !== "" ? String(rawParamValue).toLowerCase() : "";
                                const paramValue =
                                  inputKind === "boolean"
                                    ? BOOLEAN_VALUE_OPTIONS.some((opt) => opt.value === normalizedBooleanValue)
                                      ? normalizedBooleanValue
                                      : undefined
                                    : rawParamValue;

                                return (
                                  <div key={param}>
                                    <label className="text-xs text-muted-foreground mb-1 block capitalize">{param} *</label>
                                    {inputKind === "boolean" ? (
                                      <Select
                                        value={paramValue || undefined}
                                        onValueChange={(v) => updateCheckParam(check.id, param, v, index)}
                                      >
                                        <SelectTrigger
                                          className="w-full bg-background border-border text-foreground"
                                          aria-invalid={!!formErrors[`${prefix}_param_${param}`]}
                                        >
                                          <SelectValue placeholder="Select value" />
                                        </SelectTrigger>
                                        <SelectContent className={SELECT_CONTENT_CLASS}>
                                          {BOOLEAN_VALUE_OPTIONS.map((opt) => (
                                            <SelectItem key={opt.value} value={opt.value} className={SELECT_ITEM_CLASS}>
                                              {opt.label}
                                            </SelectItem>
                                          ))}
                                        </SelectContent>
                                      </Select>
                                    ) : (
                                      <Input
                                        type={inputKind === "number" ? "number" : "text"}
                                        value={paramValue}
                                        onChange={(e) => updateCheckParam(check.id, param, e.target.value, index)}
                                        placeholder={inputKind === "number" ? `Enter numeric ${param}` : `Enter ${param}`}
                                        className="bg-background border-border text-foreground"
                                        aria-invalid={!!formErrors[`${prefix}_param_${param}`]}
                                      />
                                    )}
                                    <FieldError message={formErrors[`${prefix}_param_${param}`]} />
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-2">
                  <button
                    onClick={submitCustomRule}
                    disabled={saving}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-teoco-real-blue hover:bg-teoco-real-blue/90 text-white text-sm disabled:opacity-50"
                  >
                    {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                    {editingRule ? "Update Rule" : "Create Rule"}
                  </button>
                  <button
                    onClick={backToList}
                    className="px-4 py-2 rounded-lg border border-border text-muted-foreground hover:bg-accent text-sm"
                  >
                    Back to Rules
                  </button>
                </div>
              </div>
            </div>
          ) : activeTab === "default" ? (
            <div className="space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <p className="text-sm text-muted-foreground flex-1 min-w-[240px]">
                  Built-in audit rules run based on entity count. Toggle rules on or off — disabled rules are skipped during audit. Customizable rules can be configured per project or edited in bulk via CSV.
                </p>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={handleDownloadConfigsCsv}
                    disabled={csvBusy || loading}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-muted-foreground hover:bg-accent text-sm disabled:opacity-50"
                  >
                    {csvBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                    Download CSV
                  </button>
                  <button
                    onClick={() => csvInputRef.current?.click()}
                    disabled={csvBusy || loading}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-muted-foreground hover:bg-accent text-sm disabled:opacity-50"
                  >
                    {csvBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                    Upload CSV
                  </button>
                  <input
                    ref={csvInputRef}
                    type="file"
                    accept=".csv,text/csv"
                    className="hidden"
                    onChange={handleUploadConfigsCsv}
                  />
                </div>
              </div>

              {["cell", "site"].map((entityType) => {
                const rules = (rulesData?.builtin_rules || []).filter((r) =>
                  r.entity_types.includes(entityType)
                );
                if (rules.length === 0) return null;
                return (
                  <div key={entityType} className="rounded-lg border border-border overflow-hidden">
                    <div className="px-4 py-2 bg-secondary/80 border-b border-border">
                      <h3 className="text-sm font-semibold text-foreground capitalize">{entityType} Rules</h3>
                    </div>
                    <div className="divide-y divide-border">
                      {rules.map((rule) => (
                        <div key={rule.rule_key} className="flex items-start justify-between gap-4 px-4 py-3 hover:bg-accent/30">
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium text-foreground">{rule.name}</p>
                            <p className="text-xs text-muted-foreground mt-0.5">{rule.description}</p>
                            <p className="text-[10px] text-muted-foreground mt-1">
                              Categories: {rule.categories.join(", ")}
                            </p>
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            {rule.is_customizable && (
                              <button
                                onClick={() => openCustomize(rule)}
                                className="px-2 py-1 rounded text-xs border border-border text-muted-foreground hover:bg-accent hover:text-foreground"
                              >
                                Customize
                              </button>
                            )}
                            <ToggleSwitch
                              checked={rule.is_enabled}
                              onChange={(val) => handlePrefToggle(rule.rule_key, val)}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm text-muted-foreground">
                  Custom rules apply only to Detailed (1–10 entities) and Moderate (11–50 entities) audits.
                </p>
                <button
                  onClick={openCreateForm}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-teoco-real-blue hover:bg-teoco-real-blue/90 text-white text-sm transition-colors"
                >
                  <Plus className="w-4 h-4" />
                  New Rule
                </button>
              </div>

              {(rulesData?.custom_rules || []).length === 0 ? (
                <div className="text-center py-12 text-muted-foreground text-sm">
                  No custom rules yet. Create one to extend your audit checks.
                </div>
              ) : (
                <div className="rounded-lg border border-border overflow-hidden divide-y divide-border">
                  {(rulesData?.custom_rules || []).map((rule) => (
                    <div key={rule.id} className="flex items-start justify-between gap-4 px-4 py-3 hover:bg-accent/30">
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-foreground">{rule.name}</p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {rule.entity_type} · {formatRuleTablesSummary(rule, catalog)}
                        </p>
                        <p className="text-[10px] text-muted-foreground mt-1">
                          {(rule.column_checks || []).map((check) =>
                            formatColumnCheckSummary(check, catalog)
                          ).join(" · ")}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <ToggleSwitch
                          checked={rule.is_enabled}
                          onChange={(val) => handlePrefToggle(rule.rule_key, val)}
                        />
                        <button
                          onClick={() => openEditForm(rule)}
                          className="p-1.5 rounded hover:bg-accent text-muted-foreground hover:text-foreground"
                          title="Edit"
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDeleteRule(rule)}
                          className="p-1.5 rounded hover:bg-accent text-muted-foreground hover:text-red-400"
                          title="Delete"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between px-5 py-3 border-t border-border bg-secondary/50">
          <p className="text-xs text-muted-foreground">
            {!isSubView ? catalog?.categories_note : ""}
          </p>
          <div className="flex items-center gap-2">
            {!isSubView && hasPendingPrefs && (
              <button
                onClick={savePreferences}
                disabled={saving}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-teoco-real-blue hover:bg-teoco-real-blue/90 text-white text-sm disabled:opacity-50"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                Save Preferences
              </button>
            )}
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg border border-border text-muted-foreground hover:bg-accent text-sm"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AuditRulesModal;
