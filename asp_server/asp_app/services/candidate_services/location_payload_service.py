import asyncio
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import aiofiles
import pandas as pd

from asp_app.config.json_config.pipeline_config import get_pipeline_config
from asp_app.config.tech_config_resolver import get_tech_config
from asp_app.db.schemas.candidate import LocationEDSModel
from asp_app.utils.utils import safe_float, safe_int


class LocationService:
    """Service for building location payloads."""
    
    # Transformation functions
    TRANSFORMS = {
        "str": lambda v: str(v).strip() if v is not None else None,
        "float": safe_float,
        "int": safe_int,
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
        """Load a JSON file asynchronously and return its contents."""
        path = Path(file_path)
        if not await asyncio.to_thread(path.exists):
            raise FileNotFoundError(f"JSON file not found: {file_path}")
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            content = await f.read()
        return json.loads(content)
    
    @staticmethod
    def build_location_object(
        rows: List[Dict[str, Any]],
        base_cfg: Dict[str, Any],
        mapping: Dict[str, Any],
        bvid: str,
    ) -> Dict[str, Any]:

        first_row = rows[0]

        location = {
            "$type": base_cfg["$type"],
            "bvid": bvid
        }

        for json_path, rule in mapping["root"].items():
            val = first_row.get(rule["excel"])
            val = LocationService.TRANSFORMS[rule["transform"]](val)
            LocationService.set_path(location, json_path, val)

        location["propertyCode"] = location.get("iid")

        physical_antennas = []
        for row in rows:
            ant = {"antennaType_RO": base_cfg["antennaType_RO"]}
            for json_path, rule in mapping["physicalAntennas"].items():
                val = row.get(rule["excel"])
                val = LocationService.TRANSFORMS[rule["transform"]](val)
                LocationService.set_path(ant, json_path, val)
            physical_antennas.append(ant)

        logical_antennas = []
        beam_switching_map = mapping.get("beamSwitching")
        for row in rows:
            ant = {"antennaType_RO": base_cfg["antennaType_RO"]}
            for json_path, rule in mapping["logicalAntennas"].items():
                val = row.get(rule["excel"])
                val = LocationService.TRANSFORMS[rule["transform"]](val)
                LocationService.set_path(ant, json_path, val)

            if beam_switching_map:
                freq = LocationService.TRANSFORMS[beam_switching_map["patternFrequency"]["transform"]](
                    row.get(beam_switching_map["patternFrequency"]["excel"])
                )
                name = LocationService.TRANSFORMS[beam_switching_map["patternName"]["transform"]](
                    row.get(beam_switching_map["patternName"]["excel"])
                )
                gain = LocationService.TRANSFORMS[beam_switching_map["gain"]["transform"]](
                    row.get(beam_switching_map["gain"]["excel"])
                )
                etilt = LocationService.TRANSFORMS[beam_switching_map["electricalTilt"]["transform"]](
                    row.get(beam_switching_map["electricalTilt"]["excel"])
                )
                angle = LocationService.TRANSFORMS[beam_switching_map["antennaPatternAngle"]["transform"]](
                    row.get(beam_switching_map["antennaPatternAngle"]["excel"])
                )
                ant["beamSwitching"] = {
                    "patternFrequency": freq,
                    "sbaCtrlPatterns_RO": [
                        {
                            "patterns": [
                                {
                                    "name": name,
                                    "gain": gain,
                                    "electricalTilt": etilt,
                                    "antennaPatternAngle": angle,
                                }
                            ]
                        }
                    ]
                }

            logical_antennas.append(ant)

        location["physicalAntennas"] = physical_antennas
        location["logicalAntennas"] = logical_antennas

        return location
    
    @staticmethod
    async def build_location_payload(
        excel_path: str,
        project_name: str,
        tech: str = "LTE",
    ) -> Tuple[Dict[str, Any], Path]:
        """Build complete location payload from Excel data."""
        try:
            pipeline_cfg = get_pipeline_config()
            tech_cfg = get_tech_config(tech)
            
            bvid = project_name

            base_cfg, mapping = await asyncio.gather(
                LocationService.load_json_file(tech_cfg.location_base_path),
                LocationService.load_json_file(tech_cfg.location_eds_mapping_path),
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

            # Build location objects (lat/lon from Excel columns Property: Location: X/Y Coordinate)
            locations = []
            for site_id in site_ids:
                loc = LocationService.build_location_object(
                    grouped[site_id],
                    base_cfg,
                    mapping,
                    bvid=bvid,
                )

                # Validate with Pydantic
                model = LocationEDSModel.model_validate(loc)
                locations.append(model.model_dump(by_alias=True, exclude_none=True))
            
            # Store the payload in a file (async I/O)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            payload_filename = f"CWE_LOCATION_PAYLOAD_{timestamp}.json"
            payload_path = Path(pipeline_cfg.output_dir) / "location_payloads" / payload_filename
            await asyncio.to_thread(payload_path.parent.mkdir, parents=True, exist_ok=True)
            payload_json = json.dumps({"appData": locations}, indent=4)
            async with aiofiles.open(payload_path, "w", encoding="utf-8") as f:
                await f.write(payload_json)

            return {"appData": locations}, payload_path      
            
        except Exception as e:
            raise Exception(f"Failed to build location payload: {str(e)}")
