from typing import Any, Dict, List, Tuple
import pandas as pd
import json
from pathlib import Path
from asp_app.db.schemas.candidate import MUNodeEDSModel
from asp_app.config.json_config.pipeline_config import get_pipeline_config
from asp_app.config.tech_config_resolver import get_tech_config
import asyncio
import aiofiles
from datetime import datetime


class MUService:
    """Service for building MU node payloads."""

    # Transformation functions
    TRANSFORMS = {
        "str": lambda v: str(v).strip() if v is not None else None
    }

    @staticmethod
    async def load_json_file(file_path: str) -> Dict[str, Any]:
        """Load a JSON file asynchronously and return its contents."""
        path = Path(file_path)
        if not await asyncio.to_thread(path.exists):
            raise FileNotFoundError(f"JSON file not found: {file_path}")
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            content = await f.read()
        return json.loads(content)
    
    @staticmethod
    def set_path_with_array(obj: Dict[str, Any], path: str, value: Any) -> None:
        """
        Set path with special handling for array notation (e.g., 'carriers[]').
        
        Args:
            obj: Dictionary to modify
            path: Path with optional [] for arrays
            value: Value to set
        """
        if "[]" in path:
            key = path.replace("[]", "")
            obj.setdefault(key, []).append({"iid": value})
            return

        keys = path.split(".")
        cur = obj
        for k in keys[:-1]:
            cur = cur.setdefault(k, {})
        cur[keys[-1]] = value
    
    @staticmethod
    def build_mu_objects(
        rows: List[Dict[str, Any]],
        base_cfg: Dict[str, Any],
        mapping: Dict[str, Any],
        bvid: str
    ) -> List[Dict[str, Any]]:
        """Build MU objects using mapping configuration."""

        mu_groups = {}
        mu_index_map = {}

        grouping = mapping.get("grouping", {})
        identity_col = grouping["identity"]["excel"]
        plmn_col = grouping["plmn"]["excel"]
        plmn_default = grouping["plmn"].get("default", "PLMN0")
        carrier_col = grouping["carriers"]["excel"]

        site_id_rule = mapping["root"]["location.iid"]
        site_id_col = site_id_rule["excel"]

        for row in rows:
            identity = MUService.TRANSFORMS["str"](row.get(identity_col))
            plmn = MUService.TRANSFORMS["str"](row.get(plmn_col)) or plmn_default
            carrier = MUService.TRANSFORMS["str"](row.get(carrier_col))
            site_id = MUService.TRANSFORMS["str"](row.get(site_id_col))

            if not identity:
                identity = f"{site_id}_MU"

            key = (identity, plmn, carrier)

            if key not in mu_groups:
                if identity not in mu_index_map:
                    mu_index_map[identity] = 0
                    final_iid = identity
                else:
                    mu_index_map[identity] += 1
                    suffix = chr(ord("A") + mu_index_map[identity] - 1)
                    final_iid = f"{identity}_MU_{suffix}"

                mu_groups[key] = {
                    "final_iid": final_iid,
                    "rows": []
                }

            mu_groups[key]["rows"].append(row)

        mu_nodes = []
        tech_key = mapping.get("tech_key", "lte")

        for (identity, plmn, carrier), group in mu_groups.items():
            row = group["rows"][0]
            site_id = MUService.TRANSFORMS["str"](row.get(site_id_col))

            carriers = []
            if carrier:
                carriers.append({"iid": str(carrier)})

            mu = {
                "$type": base_cfg["$type"],
                "iid": group["final_iid"],
                "bvid": bvid,
                "technology": base_cfg["technology"],
                tech_key: {
                    **base_cfg.get(tech_key, {}),
                    "carriers": carriers
                }
            }

            MUService.set_path_with_array(mu, "location.iid", site_id)
            MUService.set_path_with_array(mu, "plmn.iid", plmn)

            model = MUNodeEDSModel.model_validate(mu)
            mu_nodes.append(model.model_dump(by_alias=True, exclude_none=True))

        return mu_nodes
    
    @staticmethod
    async def build_mu_payload(
        excel_path: str,
        project_name: str,
        tech: str = "LTE",
    ) -> Tuple[Dict[str, Any], Path]:
        """Build complete MU payload from Excel data."""
        try:
            pipeline_cfg = get_pipeline_config()
            tech_cfg = get_tech_config(tech)

            bvid = project_name

            base_cfg, mapping = await asyncio.gather(
                MUService.load_json_file(tech_cfg.mu_base_path),
                MUService.load_json_file(tech_cfg.mu_eds_mapping_path),
            )

            # Load Excel data in thread pool (blocking I/O)
            df = await asyncio.to_thread(pd.read_excel, excel_path)

            # Group by site ID
            rows = df.to_dict(orient="records")
            grouped = {}
            for r in rows:
                site_id = r.get("Property: ID")
                grouped.setdefault(site_id, []).append(r)

            site_ids = list(grouped.keys())

            # Build MU objects for each site using mapping
            mu_nodes = []
            for site_id in site_ids:
                mu_nodes.extend(
                    MUService.build_mu_objects(
                        grouped[site_id],
                        base_cfg,
                        mapping,
                        bvid
                    )
                )

            # Store the payload in a file (async I/O)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            payload_filename = f"CWE_MU_PAYLOAD_{timestamp}.json"
            payload_path = Path(pipeline_cfg.output_dir) / "mu_payloads" / payload_filename
            await asyncio.to_thread(payload_path.parent.mkdir, parents=True, exist_ok=True)
            payload_json = json.dumps({"appData": mu_nodes}, indent=4)
            async with aiofiles.open(payload_path, "w", encoding="utf-8") as f:
                await f.write(payload_json)

            return {"appData": mu_nodes}, payload_path
        except Exception as e:
            raise Exception(f"Failed to build MU payload: {str(e)}") from e
