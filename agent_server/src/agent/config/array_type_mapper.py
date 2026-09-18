from pydantic import BaseModel
from typing import ClassVar, Dict


class ArrayTypeMapper(BaseModel):
    """Maps backend array-type folder names to frontend registry IDs.

    Backend array types (e.g. ``LTE_Best_RSRP``, ``FiveG_DL_Loss_Ctrl``)
    are folder names used by the coverage engine.  The frontend registry
    uses short IDs (``rsrp``, ``dl_loss``) to resolve color bands, units,
    and legends.  This class bridges the two.
    """

    _MAP: ClassVar[Dict[str, str]] = {
        # RSRP-based (dBm, -40 to -160 range)
        "LTE_Best_RSRP":            "rsrp",
        "LTE_BestServer_RSRP":      "rsrp",
        "FiveG_Best_RSRP":          "rsrp",
        "FiveG_BestServer_RSRP":    "rsrp",
        "FiveG_CSI_RSRP":           "rsrp",
        "FiveG_PDSCH_PPRE":         "rsrp",

        # Downlink path loss (dB, higher = worse, 50–190 range)
        "LTE_DL_Loss":              "dl_loss",
        "FiveG_DL_Loss_Ctrl":       "dl_loss",
        "FiveG_DL_Loss_Traffic":    "dl_loss",

        # SSB beam index (integer)
        "FiveG_SSB_Index":          "ssb_index",

        # DL beam index (integer)
        "FiveG_DL_BeamIndex_Traffic": "beam_index",
    }

    @classmethod
    def to_frontend_type(cls, array_type: str) -> str:
        """Resolve *array_type* to a frontend registry ID.

        Falls back to ``"rsrp"`` for unknown types so the frontend always
        gets a valid config key.
        """
        return cls._MAP.get(array_type, "rsrp")
