from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.database import get_user_db_session
from api.schemas.audit_rules import (
    AuditRulesCatalogResponse,
    AuditRulesListResponse,
    BuiltinRuleConfigImportResponse,
    BuiltinRuleConfigResponse,
    BuiltinRuleConfigUpdate,
    CustomAuditRuleCreate,
    CustomAuditRuleResponse,
    CustomAuditRuleUpdate,
    RulePreferencesBulkUpdate,
)
from api.services.audit_rules_service import AuditRulesService

router = APIRouter(
    prefix="/api/v1/audit-rules",
    tags=["Audit Rules"],
)


def _resolve_email(request: Request, email: str | None) -> str:
    is_admin = "CONFIG_MANAGEMENT" in request.state.user.get("roles", [])
    if not is_admin and email:
        raise HTTPException(status_code=401, detail="You are not authorized to access this resource")
    resolved = email or request.state.user.get("email")
    if not resolved:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return resolved


@router.get("/catalog", response_model=AuditRulesCatalogResponse)
async def get_audit_rules_catalog():
    """Return auditable tables, columns, and supported rule types."""
    return AuditRulesService.get_catalog()


@router.get("", response_model=AuditRulesListResponse)
async def list_audit_rules(
    request: Request,
    project_name: str = Query(..., description="Project name"),
    email: str = Query(None, description="Lookup email (admin override)"),
    db: AsyncSession = Depends(get_user_db_session),
):
    """List built-in and custom audit rules with enable/disable state for the user."""
    resolved_email = _resolve_email(request, email)
    return await AuditRulesService.list_rules(db, resolved_email, project_name)


@router.post("/custom", response_model=CustomAuditRuleResponse, status_code=201)
async def create_custom_audit_rule(
    request: Request,
    project_name: str = Query(..., description="Project name"),
    body: CustomAuditRuleCreate = ...,
    db: AsyncSession = Depends(get_user_db_session),
):
    """Create a new user-defined audit rule."""
    resolved_email = _resolve_email(request, None)
    return await AuditRulesService.create_custom_rule(db, resolved_email, project_name, body)


@router.put("/custom/{rule_id}", response_model=CustomAuditRuleResponse)
async def update_custom_audit_rule(
    request: Request,
    rule_id: int,
    project_name: str = Query(..., description="Project name"),
    body: CustomAuditRuleUpdate = ...,
    db: AsyncSession = Depends(get_user_db_session),
):
    """Update an existing custom audit rule."""
    resolved_email = _resolve_email(request, None)
    return await AuditRulesService.update_custom_rule(db, resolved_email, project_name, rule_id, body)


@router.delete("/custom/{rule_id}", status_code=204)
async def delete_custom_audit_rule(
    request: Request,
    rule_id: int,
    project_name: str = Query(..., description="Project name"),
    db: AsyncSession = Depends(get_user_db_session),
):
    """Delete a custom audit rule."""
    resolved_email = _resolve_email(request, None)
    await AuditRulesService.delete_custom_rule(db, resolved_email, project_name, rule_id)


@router.get("/builtin/export")
async def export_builtin_rule_configs_csv(
    request: Request,
    project_name: str = Query(..., description="Project name"),
    email: str = Query(None, description="Lookup email (admin override)"),
    db: AsyncSession = Depends(get_user_db_session),
):
    """Download customizable built-in rule configurations as CSV (defaults + saved values)."""
    resolved_email = _resolve_email(request, email)
    csv_content = await AuditRulesService.export_builtin_configs_csv(db, resolved_email, project_name)
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in project_name)
    filename = f"audit-rules-config-{safe_name}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/builtin/import", response_model=BuiltinRuleConfigImportResponse)
async def import_builtin_rule_configs_csv(
    request: Request,
    project_name: str = Query(..., description="Project name"),
    file: UploadFile = File(..., description="CSV file with built-in rule configurations"),
    db: AsyncSession = Depends(get_user_db_session),
):
    """Upload CSV to bulk-update customizable built-in rule configurations."""
    resolved_email = _resolve_email(request, None)
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail="A .csv file is required")

    raw = await file.read()
    try:
        csv_content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="CSV file must be UTF-8 encoded") from exc

    return await AuditRulesService.import_builtin_configs_csv(
        db, resolved_email, project_name, csv_content
    )


@router.put("/builtin/{rule_key}", response_model=BuiltinRuleConfigResponse)
async def update_builtin_rule_config(
    request: Request,
    rule_key: str,
    body: BuiltinRuleConfigUpdate,
    db: AsyncSession = Depends(get_user_db_session),
):
    """Save user configuration overrides for a customizable built-in rule."""
    resolved_email = _resolve_email(request, None)
    return await AuditRulesService.upsert_builtin_config(db, resolved_email, rule_key, body)


@router.put("/preferences")
async def update_audit_rule_preferences(
    request: Request,
    body: RulePreferencesBulkUpdate,
    db: AsyncSession = Depends(get_user_db_session),
):
    """Bulk update enable/disable preferences for built-in and custom rules."""
    resolved_email = _resolve_email(request, None)
    updated = await AuditRulesService.update_preferences(db, resolved_email, body)
    return {"updated": updated}
