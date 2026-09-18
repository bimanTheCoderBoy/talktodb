from typing import Any, Dict, List, Tuple
import pandas as pd
import json
import os
from pathlib import Path
from asp_app.db.schemas.candidate import CellEDSModel
from asp_app.config.json_config.pipeline_config import get_pipeline_config
from asp_app.config.tech_config_resolver import get_tech_config
import asyncio
import aiofiles
from datetime import datetime
from asp_app.utils.utils import safe_float, safe_int, safe_bool

class CellService:
    """Service for building cell payloads."""
    
    # Transformation functions
    TRANSFORMS = {
        "str": lambda v: str(v).strip() if v is not None else None,
        "int": safe_int,
        "float": safe_float,
        "bool": safe_bool,
        "split_backslash": lambda v: str(v).split("\\")[0].strip() if v else None
    }
    
    @staticmethod
    def set_path(obj: Dict[str, Any], path: str, value: Any) -> None:
        """Set a value in nested dict using dot notation."""
        keys = path.split('.')
        current = obj
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value
    
    @staticmethod
    async def load_json_file(file_path: str) -> Dict[str, Any]:
        """Load a JSON file and return its contents."""
        path = Path(file_path)
        if not await asyncio.to_thread(path.exists):
            raise FileNotFoundError(f"JSON file not found: {file_path}")
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            content = await f.read()
        return json.loads(content)
    
    @staticmethod
    async def build_cell_object(
        row: Dict[str, Any],
        base_cfg: Dict[str, Any],
        mapping: Dict[str, Any],
        mu_lookup: str,
        bvid: str
    ) -> Dict[str, Any]:
        tech_key = mapping.get("tech_key", "lte")

        # Read root fields from mapping
        root_map = mapping.get("root", {})
        cell_iid_col = root_map.get("iid", {}).get("excel", "Cell: Identity")
        site_id_col = root_map.get("location.iid", {}).get("excel", "Property: ID")
        site_id = row.get(site_id_col)

        # Read the enabled column from the technology section
        tech_section = mapping.get("technology", {})
        enabled_rule = next(iter(tech_section.values()), None)
        enabled_val = True
        if enabled_rule and "excel" in enabled_rule:
            enabled_val = CellService.TRANSFORMS["bool"](row.get(enabled_rule["excel"]))

        cell = {
            "$type": base_cfg["$type"],
            "iid": row.get(cell_iid_col),
            "bvid": bvid,
            "technology": {
                **base_cfg["technology"],
                "fixed": enabled_val
            },
            "parent": {"iid": mu_lookup},
            "location": {"iid": site_id},
            tech_key: {**base_cfg.get(tech_key, {})},
            "feeders": []
        }

        for json_path, rule in mapping.get("tech_fields", {}).items():
            val = CellService.TRANSFORMS[rule["transform"]](row.get(rule["excel"]))
            CellService.set_path(cell, json_path, val)

        feeder = {
            **base_cfg["feederDefaults"],
            "location": site_id
        }

        for json_path, rule in mapping["feeder"].items():
            val = CellService.TRANSFORMS[rule["transform"]](row.get(rule["excel"]))
            CellService.set_path(feeder, json_path, val)

        feeder["logicalindex"] = CellService.TRANSFORMS["int"](
            row.get("Property: Logical Antenna: Index")
        )
        cell["feeders"].append(feeder)

        return cell
    
    @staticmethod
    async def build_cell_payload(
        excel_path: str,
        project_name: str,
        tech: str = "LTE",
    ) -> Tuple[Dict[str, Any], Path]:
        """Build complete cell payload from Excel data."""
        try:
            pipeline_cfg = get_pipeline_config()
            tech_cfg = get_tech_config(tech)
            
            bvid = project_name

            base_cfg, mapping = await asyncio.gather(
                CellService.load_json_file(tech_cfg.cell_base_path),
                CellService.load_json_file(tech_cfg.cell_eds_mapping_path),
            )
            
            # Load Excel data
            df = await asyncio.to_thread(pd.read_excel, excel_path)
            
            # Group by site ID
            rows = df.to_dict(orient="records")
            grouped = {}
            for r in rows:
                grouped.setdefault(r.get("Property: ID"), []).append(r)

            sites = list(grouped.keys())

            # Build cell objects
            cell_nodes = []
            for site in sites:
                for row in grouped[site]:
                    # This or part might be removed if no such ID with this name exists
                    mu_iid = row.get("MU Node: Identity") or f"{site}_MU"

                    cell = await CellService.build_cell_object(
                        row, base_cfg, mapping, mu_iid, bvid
                    )
                    
                    # Validate with Pydantic
                    model = CellEDSModel.model_validate(cell)
                    cell_nodes.append(model.model_dump(by_alias=True, exclude_none=True))

            # Store the payload in a file (async I/O)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            payload_filename = f"CWE_CELL_PAYLOAD_{timestamp}.json"
            payload_path = Path(pipeline_cfg.output_dir) / "cell_payloads" / payload_filename
            await asyncio.to_thread(payload_path.parent.mkdir, parents=True, exist_ok=True)
            payload_json = json.dumps({"appData": cell_nodes}, indent=4)
            async with aiofiles.open(payload_path, "w", encoding="utf-8") as f:
                await f.write(payload_json)

            return {"appData": cell_nodes}, payload_path
        except Exception as e:
            raise Exception(f"Failed to build cell payload: {str(e)}") from e
