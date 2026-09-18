import json
import os
from pathlib import Path
from typing import List, Dict, Tuple
import pandas as pd

_DEFAULT_COLUMNS_CONFIG = str(
    Path(__file__).resolve().parent.parent.parent / "config" / "json_config" / "lte" / "columns.json"
)


class ExcelColumnValidator:
    """Validates Excel file columns against required columns configuration."""
    
    @staticmethod
    def _load_required_columns(config_path: str) -> List[str]:

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Columns config file not found at: {config_path}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file: {str(e)}")
        
        if "required_columns" not in config_data:
            raise ValueError("Config file must contain 'required_columns' key")
        
        columns = config_data["required_columns"]
        if not isinstance(columns, list):
            raise ValueError("'required_columns' must be a list")
        
        return columns
    
    @staticmethod
    def _get_excel_columns(excel_path: str) -> List[str]:

        if not os.path.exists(excel_path):
            raise FileNotFoundError(f"Excel file not found at: {excel_path}")
        
        try:
            # Read only the header row (nrows=0) for efficiency
            df = pd.read_excel(excel_path, nrows=0)
            return list(df.columns)
        except Exception as e:
            raise ValueError(f"Error reading Excel file: {str(e)}")
    
    @staticmethod
    def _compare_columns(excel_columns: List[str], required_columns: List[str]) -> Tuple[bool, List[str], List[str]]:
        excel_set = set(excel_columns)
        required_set = set(required_columns)
        
        missing_columns = sorted(list(required_set - excel_set))
        extra_columns = sorted(list(excel_set - required_set))
        is_valid = len(missing_columns) == 0
        
        return is_valid, missing_columns, extra_columns
    
    @staticmethod
    def validate_excel_columns(excel_path: str, config_path: str = None) -> Dict[str, any]:
        if config_path is None:
            config_path = _DEFAULT_COLUMNS_CONFIG
        
        try:
            # Step 1: Load required columns from config
            required_columns = ExcelColumnValidator._load_required_columns(config_path)
            
            # Step 2: Get columns from Excel file
            excel_columns = ExcelColumnValidator._get_excel_columns(excel_path)
            
            # Step 3: Compare columns
            is_valid, missing_columns, extra_columns = ExcelColumnValidator._compare_columns(excel_columns, required_columns)
            
            # Step 4: Build result
            if is_valid:
                message = f"✅ All {len(required_columns)} required columns are present"
            else:
                missing_preview = ', '.join(missing_columns[:5])
                if len(missing_columns) > 5:
                    missing_preview += f" ... and {len(missing_columns) - 5} more"
                message = f"❌ Missing {len(missing_columns)} column(s): {missing_preview}"
            
            return {
                "valid": is_valid,
                "excel_path": excel_path,
                "total_excel_columns": len(excel_columns),
                "total_required_columns": len(required_columns),
                "missing_columns": missing_columns,
                "extra_columns": extra_columns,
                "message": message
            }
            
        except FileNotFoundError as e:
            return {
                "valid": False,
                "excel_path": excel_path,
                "total_excel_columns": 0,
                "total_required_columns": 0,
                "missing_columns": [],
                "extra_columns": [],
                "message": f"❌ File error: {str(e)}"
            }
        except ValueError as e:
            return {
                "valid": False,
                "excel_path": excel_path,
                "total_excel_columns": 0,
                "total_required_columns": 0,
                "missing_columns": [],
                "extra_columns": [],
                "message": f"❌ Validation error: {str(e)}"
            }
        except Exception as e:
            return {
                "valid": False,
                "excel_path": excel_path,
                "total_excel_columns": 0,
                "total_required_columns": 0,
                "missing_columns": [],
                "extra_columns": [],
                "message": f"❌ Unexpected error: {str(e)}"
            }




