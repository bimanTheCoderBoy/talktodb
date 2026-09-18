import React, { useEffect, useMemo } from 'react';
import { Target, Save } from 'lucide-react';
import StatusIndicator from './StatusIndicator';
import LoadingButton from '../../LoadingButton';

/** LTE uses RSRP; 5G NR uses SS-RSRP. Backend goal labels always say RSRP. */
function metricLabel(label, technology) {
  if (!label) return label;
  if (technology === 'FiveG' || technology === 'NR' || technology === '5G') {
    return label.replace(/(?<!SS-)RSRP/g, 'SS-RSRP');
  }
  return label;
}

function DefineGoalStep({
  status,
  goalOptions,
  goalType,
  onGoalTypeChange,
  goalParameters,
  onGoalParametersChange,
  isGoalFormValid,
  onSaveGoal,
  goalsLoading,
  goalsError,
  isLocked = false,
  nCandidates = null,
  technology = null,
}) {
  const currentGoal = goalOptions?.find((g) => g.id === goalType) ?? null;
  const rawParamSpecs = currentGoal?.params ?? [];

  // K must be < N so we never evaluate the trivial C(N,N)=1 combination.
  // Floor at 1 because K=0 is undefined for a combination size.
  const kMax = useMemo(() => {
    if (nCandidates == null) return null;             // unknown → fall back to backend options
    const n = Number(nCandidates);
    if (!Number.isFinite(n) || n < 1) return null;
    return Math.max(1, n - 1);
  }, [nCandidates]);

  // Override the k_value param's options with [1..kMax] when nCandidates is known.
  // The backend ships a static [1, 2] default; this runs after we know the actual
  // candidate count and replaces the dropdown choices.
  const paramSpecs = useMemo(() => {
    if (kMax == null) return rawParamSpecs;
    return rawParamSpecs.map((p) => {
      if (p.id !== 'k_value') return p;
      const dynamicOptions = Array.from({ length: kMax }, (_, i) => i + 1);
      return { ...p, options: dynamicOptions };
    });
  }, [rawParamSpecs, kMax]);

  // Auto-clamp: if the user previously picked K > kMax (e.g. they reduced N
  // after picking K), pull the value down to the new cap so the dropdown
  // stays consistent with goalParameters.
  useEffect(() => {
    if (kMax == null) return;
    const current = Number(goalParameters?.k_value);
    if (Number.isFinite(current) && current > kMax) {
      onGoalParametersChange({ k_value: kMax });
    }
  }, [kMax, goalParameters?.k_value, onGoalParametersChange]);

  return (
    <div className={`
      relative p-3 rounded-lg transition-all duration-200
      ${status === 'done'
        ? 'bg-card/30 border border-transparent'
        : 'bg-muted/50 border border-border dark:bg-amber-500/10 dark:border-amber-500/30'
      }
    `}>
      <div className="flex items-center gap-3">
        <div className={`
          p-2 rounded-lg
          ${status === 'done' ? 'bg-green-500/20' : 'bg-muted dark:bg-amber-500/20'}
        `}>
          <Target className={`w-4 h-4 ${status === 'done' ? 'text-green-400' : 'text-muted-foreground dark:text-amber-400'}`} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium text-foreground">Define Goal</span>
            <StatusIndicator status={status} />
          </div>

          <div className="mt-2 space-y-2">
            {/* Goal Type Dropdown (from API) */}
            <div>
              <label className="text-[10px] text-muted-foreground block mb-1">Goal Type</label>
              <select
                className="w-full px-2 py-1.5 text-xs bg-secondary/50 border border-border
                  rounded-lg text-foreground focus:outline-none focus:border-primary/50
                  disabled:opacity-50 disabled:cursor-not-allowed"
                value={goalType}
                onChange={(e) => onGoalTypeChange(e.target.value)}
                disabled={goalsLoading || isLocked}
              >
                {goalsLoading && (
                  <option value="">Loading goals...</option>
                )}
                {!goalsLoading && goalOptions?.length === 0 && !goalsError && (
                  <option value="">No goals available</option>
                )}
                {goalsError && (
                  <option value="">Error loading goals</option>
                )}
                {goalOptions?.map((g) => (
                  <option key={g.id} value={g.id}>
                    {metricLabel(g.label, technology)}
                  </option>
                ))}
              </select>
            </div>

            {/* Dynamic parameter inputs from API (no frontend change needed for new goals) */}
            {paramSpecs.map((param) => {
              const rawValue = goalParameters?.[param.id] ?? '';
              const numValue = Number(rawValue);
              const hasRange = param.type === 'number' && (param.min != null || param.max != null);
              const outOfRange = hasRange
                && rawValue !== ''
                && Number.isFinite(numValue)
                && (
                  (param.min != null && numValue < param.min)
                  || (param.max != null && numValue > param.max)
                );

              return (
              <div key={param.id}>
                <label className="text-[10px] text-muted-foreground block mb-1">
                  {metricLabel(param.label, technology)}
                  {param.id === 'k_value' && kMax != null && (
                    <span className="ml-1 text-muted-foreground">
                      (1–{kMax}, capped at N−1 where N={nCandidates})
                    </span>
                  )}
                  {hasRange && (
                    <span className="ml-1 text-muted-foreground">
                      ({param.min ?? '…'}–{param.max ?? '…'})
                    </span>
                  )}
                </label>
                {param.type === 'select' ? (
                  <select
                    value={goalParameters?.[param.id] ?? (param.options?.[0] ?? '')}
                    onChange={(e) => {
                      const val = param.options?.some((o) => Number(o) === Number(e.target.value))
                        ? Number(e.target.value)
                        : e.target.value;
                      onGoalParametersChange({ [param.id]: val });
                    }}
                    disabled={isLocked}
                    className="w-full px-2 py-1.5 text-xs bg-secondary/50 border border-border
                      rounded-lg text-foreground focus:outline-none focus:border-primary/50
                      disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {(param.options ?? []).map((opt) => (
                      <option key={opt} value={opt}>
                        {opt}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    inputMode={param.type === 'number' ? 'decimal' : undefined}
                    value={rawValue}
                    onChange={(e) => {
                      const value = e.target.value;
                      if (param.type !== 'number') {
                        onGoalParametersChange({ [param.id]: value });
                        return;
                      }
                      // Numeric draft only (blocks non-numeric chars like "ppp")
                      const isValidNumberInput = /^-?(?:\d+(?:\.\d*)?|\.\d*)?$/.test(value);
                      if (!isValidNumberInput) return;
                      onGoalParametersChange({ [param.id]: value });
                    }}
                    disabled={isLocked}
                    placeholder={
                      param.type === 'number' && hasRange
                        ? `${param.min ?? ''}–${param.max ?? ''}`
                        : param.type === 'number'
                          ? 'Enter number'
                          : ''
                    }
                    className={`w-full px-2 py-1.5 text-xs bg-secondary/50 rounded-lg text-foreground
                      placeholder-muted-foreground focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed
                      ${outOfRange
                        ? 'border border-red-500 focus:border-red-500'
                        : 'border border-border focus:border-primary/50'
                      }`}
                  />
                )}
              </div>
              );
            })}

            {/* Save Goal Button */}
            {!isLocked && (
              <div className="mt-2">
                <LoadingButton
                  name="Save Goal"
                  onClick={onSaveGoal}
                  disabled={!isGoalFormValid}
                  icon={Save}
                  variant="success"
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default DefineGoalStep;
