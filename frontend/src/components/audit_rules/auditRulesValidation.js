const RULE_TYPES_REQUIRING = {
  in_range: ["min", "max"],
  gt: ["value"],
  lt: ["value"],
  gte: ["value"],
  lte: ["value"],
  eq: ["value"],
  neq: ["value"],
  regex: ["pattern"],
};

const FALLBACK_RULE_TYPES_BY_DATA_TYPE = {
  boolean: ["not_null", "boolean_true", "boolean_false", "eq", "neq"],
  integer: ["not_null", "in_range", "gt", "lt", "gte", "lte", "eq", "neq"],
  float: ["not_null", "in_range", "gt", "lt", "gte", "lte", "eq", "neq"],
  text: ["not_null", "eq", "neq", "regex"],
};

const RULE_TYPE_LABELS = {
  not_null: "Value is not null",
  in_range: "Within range",
  gt: "Greater than",
  lt: "Less than",
  gte: "Greater than or equal",
  lte: "Less than or equal",
  eq: "Equal to",
  neq: "Not equal to",
  boolean_true: "Boolean is true",
  boolean_false: "Boolean is false",
  regex: "Matches regex",
};

const RULE_TYPE_DESCRIPTIONS = {
  not_null: "Pass when the column has a non-null value.",
  in_range: "Pass when value is between min and max (inclusive).",
  gt: "Pass when value is greater than the threshold.",
  lt: "Pass when value is less than the threshold.",
  gte: "Pass when value is greater than or equal to the threshold.",
  lte: "Pass when value is less than or equal to the threshold.",
  eq: "Pass when value equals the expected value.",
  neq: "Pass when value does not equal the expected value.",
  boolean_true: "Pass when the value is true.",
  boolean_false: "Pass when the value is false.",
  regex: "Pass when the string value matches the regex pattern.",
};

const NUMERIC_DATA_TYPES = new Set(["integer", "float"]);
const NUMERIC_THRESHOLD_RULE_TYPES = new Set(["gt", "lt", "gte", "lte", "eq", "neq"]);

export const BOOLEAN_VALUE_OPTIONS = [
  { value: "true", label: "True" },
  { value: "false", label: "False" },
  { value: "yes", label: "Yes" },
  { value: "no", label: "No" },
];

const BOOLEAN_VALUE_SET = new Set(BOOLEAN_VALUE_OPTIONS.map((opt) => opt.value));

function isNumericDataType(dataType) {
  return NUMERIC_DATA_TYPES.has(dataType);
}

function parseNumericParam(raw) {
  if (raw === undefined || raw === null) return null;
  const text = String(raw).trim();
  if (text === "") return null;
  const num = Number(text);
  if (Number.isNaN(num)) return NaN;
  return num;
}

export function getCheckParamInputKind(catalog, check, param) {
  const colMeta = getColumnMeta(catalog, check.table_name, check.column);
  const dataType = colMeta?.data_type;

  if (dataType === "boolean" && param === "value" && ["eq", "neq"].includes(check.rule_type)) {
    return "boolean";
  }

  if (isNumericDataType(dataType)) {
    if (check.rule_type === "in_range" && (param === "min" || param === "max")) {
      return "number";
    }
    if (NUMERIC_THRESHOLD_RULE_TYPES.has(check.rule_type) && param === "value") {
      return "number";
    }
  }

  return "text";
}


let checkIdCounter = 0;

export function newCheckId() {
  checkIdCounter += 1;
  return `check-${checkIdCounter}`;
}

export function emptyColumnCheck() {
  return {
    id: newCheckId(),
    table_name: "",
    column: "",
    rule_type: "not_null",
    rule_params: {},
  };
}

function validateCheckParams(check, index, errors, catalog) {
  const prefix = `check_${index}`;
  const requiredParams = RULE_TYPES_REQUIRING[check.rule_type] || [];
  const colMeta =
    catalog && check.table_name && check.column
      ? getColumnMeta(catalog, check.table_name, check.column)
      : null;
  const dataType = colMeta?.data_type;

  for (const param of requiredParams) {
    const raw = check.rule_params?.[param];
    if (raw === undefined || raw === null || String(raw).trim() === "") {
      errors[`${prefix}_param_${param}`] = `${param} is required`;
    }
  }

  if (isNumericDataType(dataType)) {
    if (check.rule_type === "in_range") {
      const min = parseNumericParam(check.rule_params?.min);
      const max = parseNumericParam(check.rule_params?.max);

      if (check.rule_params?.min !== undefined && check.rule_params?.min !== null && String(check.rule_params.min).trim() !== "" && Number.isNaN(min)) {
        errors[`${prefix}_param_min`] = "Min must be a number";
      }
      if (check.rule_params?.max !== undefined && check.rule_params?.max !== null && String(check.rule_params.max).trim() !== "" && Number.isNaN(max)) {
        errors[`${prefix}_param_max`] = "Max must be a number";
      }
      if (!Number.isNaN(min) && min !== null && !Number.isNaN(max) && max !== null && min > max) {
        errors[`${prefix}_param_max`] = "Max must be greater than or equal to min";
      }
    } else if (NUMERIC_THRESHOLD_RULE_TYPES.has(check.rule_type)) {
      const raw = check.rule_params?.value;
      if (raw !== undefined && raw !== null && String(raw).trim() !== "" && Number.isNaN(parseNumericParam(raw))) {
        errors[`${prefix}_param_value`] = "Value must be a number";
      }
    }
  } else if (check.rule_type === "in_range") {
    const min = Number(check.rule_params?.min);
    const max = Number(check.rule_params?.max);
    if (!Number.isNaN(min) && !Number.isNaN(max) && min > max) {
      errors[`${prefix}_param_max`] = "Max must be greater than or equal to min";
    }
  }

  if (dataType === "boolean" && ["eq", "neq"].includes(check.rule_type)) {
    const raw = check.rule_params?.value;
    if (raw !== undefined && raw !== null && String(raw).trim() !== "") {
      if (!BOOLEAN_VALUE_SET.has(String(raw).trim().toLowerCase())) {
        errors[`${prefix}_param_value`] = "Select true, false, yes, or no";
      }
    }
  }


  if (check.rule_type === "regex" && check.rule_params?.pattern) {
    try {
      // eslint-disable-next-line no-new
      new RegExp(check.rule_params.pattern);
    } catch (err) {
      errors[`${prefix}_param_pattern`] = `Invalid regex: ${err.message}`;
    }
  }
}

function checkPairKey(check) {
  return `${check.table_name || ""}::${check.column || ""}`;
}

export function getTablesForEntity(catalog, entityType) {
  if (!catalog?.tables) return [];
  return catalog.tables.filter((t) => t.entity_types.includes(entityType));
}

export function getColumnMeta(catalog, tableName, columnName) {
  if (!tableName || !columnName) return null;
  const table = catalog?.tables?.find((t) => t.table_name === tableName);
  return table?.columns?.find((c) => c.name === columnName) || null;
}

export function getAllowedRuleTypes(catalog, dataType) {
  if (!dataType) return [];
  const fromCatalog = catalog?.rule_types_by_data_type?.[dataType];
  if (fromCatalog?.length) return fromCatalog;
  return FALLBACK_RULE_TYPES_BY_DATA_TYPE[dataType] || ["not_null"];
}

export function getAllowedRuleTypesForCheck(catalog, tableName, columnName) {
  const colMeta = getColumnMeta(catalog, tableName, columnName);
  if (!colMeta) return [];
  if (colMeta.allowed_rule_types?.length) {
    return colMeta.allowed_rule_types;
  }
  return getAllowedRuleTypes(catalog, colMeta.data_type);
}

export function pickRuleTypeForColumn(catalog, tableName, columnName, currentRuleType) {
  const allowed = getAllowedRuleTypesForCheck(catalog, tableName, columnName);
  if (!allowed.length) return "not_null";
  if (currentRuleType && allowed.includes(currentRuleType)) {
    return currentRuleType;
  }
  return allowed[0];
}

/** Build check-type dropdown options for a selected column (never returns the full rule list). */
export function resolveRuleTypeOptionsForCheck(catalog, tableName, columnName) {
  if (!tableName || !columnName) {
    return [];
  }

  const allowedValues = getAllowedRuleTypesForCheck(catalog, tableName, columnName);
  const metaByValue = new Map((catalog?.rule_types || []).map((rt) => [rt.value, rt]));

  return allowedValues.map((value) => {
    const meta = metaByValue.get(value);
    return {
      value,
      label: meta?.label || RULE_TYPE_LABELS[value] || value.replace(/_/g, " "),
      description: meta?.description || RULE_TYPE_DESCRIPTIONS[value] || "",
      requires_params: meta?.requires_params || RULE_TYPES_REQUIRING[value] || [],
    };
  });
}

export function filterRuleTypeOptions(catalog, dataType) {
  const allowed = new Set(getAllowedRuleTypes(catalog, dataType));
  return (catalog?.rule_types || []).filter((rt) => allowed.has(rt.value));
}

export function validateCustomRuleForm(form, catalog, options = {}) {
  const errors = {};
  const { existingRules = [], editingRuleId = null } = options;

  const name = (form.name || "").trim();
  if (!name) {
    errors.name = "Rule name is required";
  } else if (name.length < 3) {
    errors.name = "Rule name must be at least 3 characters";
  } else if (name.length > 120) {
    errors.name = "Rule name must be 120 characters or fewer";
  } else {
    const normalizedName = name.toLowerCase();
    const duplicate = existingRules.some(
      (rule) =>
        rule.id !== editingRuleId && (rule.name || "").trim().toLowerCase() === normalizedName
    );
    if (duplicate) {
      errors.name = "A custom rule with this name already exists";
    }
  }

  if (!form.entity_type) {
    errors.entity_type = "Entity type is required";
  }

  const checks = form.column_checks || [];
  if (checks.length === 0) {
    errors.column_checks = "Add at least one column check";
  } else if (checks.length > 10) {
    errors.column_checks = "A rule can have at most 10 column checks";
  }

  const usedPairs = [];
  const tableNames = new Set();

  checks.forEach((check, index) => {
    const prefix = `check_${index}`;

    if (!check.table_name) {
      errors[`${prefix}_table`] = "Select a table";
    } else {
      tableNames.add(check.table_name);
    }

    if (!check.column) {
      errors[`${prefix}_column`] = "Select a column";
    } else if (check.table_name) {
      const pairKey = checkPairKey(check);
      if (usedPairs.includes(pairKey)) {
        errors[`${prefix}_column`] = "This table/column pair is already used";
      } else {
        usedPairs.push(pairKey);
      }
    }

    if (!check.rule_type) {
      errors[`${prefix}_rule_type`] = "Select a rule type";
    }

    if (catalog && check.table_name && check.column && check.rule_type) {
      const allowed = getAllowedRuleTypesForCheck(catalog, check.table_name, check.column);
      if (allowed.length && !allowed.includes(check.rule_type)) {
        const colMeta = getColumnMeta(catalog, check.table_name, check.column);
        errors[`${prefix}_rule_type`] =
          `Check type is not valid for ${colMeta?.data_type || "this"} columns`;
      }
    }

    validateCheckParams(check, index, errors, catalog);
  });

  if (catalog && form.entity_type && tableNames.size > 0) {
    const availableTables = getTablesForEntity(catalog, form.entity_type);
    const availableByName = new Map(availableTables.map((t) => [t.table_name, t]));

    if (tableNames.has("cell_lte") && tableNames.has("cell_nr")) {
      errors.column_checks = "LTE and NR cell tables cannot be combined in one rule";
    }

    checks.forEach((check, index) => {
      const prefix = `check_${index}`;
      if (!check.table_name) return;

      const table = availableByName.get(check.table_name);
      if (!table) {
        errors[`${prefix}_table`] = "Invalid table for this entity type";
        return;
      }

      if (check.column) {
        const allowed = new Set(table.columns.map((c) => c.name));
        if (!allowed.has(check.column)) {
          errors[`${prefix}_column`] = "Invalid column for this table";
        }
      }
    });

    if (
      form.entity_type === "cell" &&
      tableNames.has("location") &&
      !tableNames.has("cell_lte") &&
      !tableNames.has("cell_nr")
    ) {
      errors.column_checks =
        "Site columns on a cell audit require at least one LTE or NR cell check (used to join and filter cells)";
    }
  }

  return errors;
}

function buildCheckParams(check, catalog) {
  const rule_params = {};
  const requiredParams = RULE_TYPES_REQUIRING[check.rule_type] || [];
  const colMeta = getColumnMeta(catalog, check.table_name, check.column);
  const dataType = colMeta?.data_type;

  for (const param of requiredParams) {
    const raw = check.rule_params?.[param];
    if (isNumericDataType(dataType)) {
      if (check.rule_type === "in_range" || NUMERIC_THRESHOLD_RULE_TYPES.has(check.rule_type)) {
        rule_params[param] = Number(raw);
        continue;
      }
    } else if (check.rule_type === "in_range" || ["gt", "lt", "gte", "lte"].includes(check.rule_type)) {
      rule_params[param] = Number(raw);
      continue;
    }
    if (dataType === "boolean" && param === "value") {
      rule_params[param] = String(raw).trim().toLowerCase();
      continue;
    }
    rule_params[param] = raw;
  }

  return rule_params;
}

export function buildCustomRulePayload(form, catalog) {
  const checks = form.column_checks || [];
  const primaryTable = checks[0]?.table_name || "";

  return {
    name: form.name.trim(),
    description: (form.description || "").trim(),
    entity_type: form.entity_type,
    table_name: primaryTable,
    column_checks: checks.map((check) => ({
      table_name: check.table_name,
      column: check.column,
      rule_type: check.rule_type,
      rule_params: buildCheckParams(check, catalog),
    })),
  };
}

export function emptyCustomRuleForm() {
  return {
    name: "",
    description: "",
    entity_type: "cell",
    column_checks: [emptyColumnCheck()],
  };
}

export function customRuleToForm(rule) {
  return {
    name: rule.name || "",
    description: rule.description || "",
    entity_type: rule.entity_type || "cell",
    column_checks: (rule.column_checks || []).map((check) => ({
      id: newCheckId(),
      table_name: check.table_name || "",
      column: check.column || "",
      rule_type: check.rule_type || "not_null",
      rule_params: check.rule_params || {},
    })),
  };
}

export function formatColumnCheckSummary(check, catalog) {
  const table = catalog?.tables?.find((t) => t.table_name === check.table_name);
  const colMeta = table?.columns?.find((c) => c.name === check.column);
  const tableLabel = table?.label || check.table_name || "Table";
  const colLabel = colMeta?.label || check.column;
  const ruleLabel = (check.rule_type || "").replace(/_/g, " ");

  const params = check.rule_params || {};
  const prefix = `${tableLabel} · ${colLabel}`;

  if (check.rule_type === "in_range") {
    return `${prefix}: ${ruleLabel} ${params.min}–${params.max}`;
  }
  if (["gt", "lt", "gte", "lte", "eq", "neq"].includes(check.rule_type)) {
    return `${prefix}: ${ruleLabel} ${params.value}`;
  }
  if (check.rule_type === "regex") {
    return `${prefix}: matches /${params.pattern}/`;
  }
  return `${prefix}: ${ruleLabel}`;
}

export function formatRuleTablesSummary(rule, catalog) {
  const tables = [
    ...new Set(
      (rule.column_checks || []).map((c) => c.table_name || rule.table_name).filter(Boolean)
    ),
  ];
  if (tables.length === 0) return rule.table_name || "";
  return tables
    .map((name) => catalog?.tables?.find((t) => t.table_name === name)?.label || name)
    .join(", ");
}
