"""
Encryption pipeline — encrypts sensitive telecom values in messages before
they reach the LLM, and decrypts hash tokens in AI responses before they
reach the user.

Uses the 3-layer rule engine for HumanMessages and deterministic taggers
for ToolMessages. No LLM calls required.
"""

import json
import re
import hashlib
import logging
from typing import Tuple, Optional, List, Dict
from langchain_core.messages import AnyMessage, HumanMessage, ToolMessage, AIMessage
from .rule_engine import detect_entities
from .known_values import KnownValuesStore

logger = logging.getLogger(__name__)


class Encryptor:
    def __init__(self, known_values: Optional[KnownValuesStore] = None):
        self._known_values = known_values
        self._tag = "<ENCRYPTED>"
        self._tag_len = len(self._tag)
        self._hash_pattern = r"<HASH:([a-f0-9]{32})>"

    async def encrypt(self, msg: AnyMessage) -> Tuple[AnyMessage, List[Dict]]:
        """
        Encrypt sensitive values in a message.

        Returns:
            (modified_message, entries) where entries is a list of dicts with
            keys: start_index, original_value, hash
        """
        if isinstance(msg, AIMessage):
            return msg, []

        if isinstance(msg, HumanMessage) or isinstance(msg, ToolMessage):
            # Use the rule engine for both HumanMessages and ToolMessages.
            # This only encrypts identifiers (site names, cell IDs) and leaves
            # numeric values (heights, PCI, tilt) and categories (LTE, NR)
            # readable so the LLM can reason about the data.
            entries = detect_entities(msg.content, self._known_values)
        else:
            return msg, []

        if not entries:
            return msg, []

        entries = self._add_hashes(entries)
        redacted_content = self._apply_redactions(msg.content, entries)
        msg.content = redacted_content

        logger.info(f"[Encryptor] Encrypted {len(entries)} entities")

        return msg, entries

    def decrypt(self, msg: AIMessage, entries: List[Dict]) -> AIMessage:
        """Replace <HASH:xxx> tokens in AI response with original values."""
        if not entries:
            return msg
        lookup = {entry["hash"]: entry["original_value"] for entry in entries}
        content = re.sub(
            self._hash_pattern,
            lambda m: lookup.get(m.group(1), m.group(0)),
            msg.content,
        )
        msg.content = content
        return msg

    def tool_message_tagger_dispatcher(self, text: str, tool_name: str) -> str:
        if tool_name == "asset_db_rag_tool":
            return self._tag_rag_tool_message(text)
        elif tool_name == "discrepancy_engine_tool":
            return self._tag_discrepancy_tool_message(text)
        else:
            return text

    def _tag_rag_tool_message(self, text: str) -> str:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if not match:
            return text

        json_str = match.group()
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return text

        new_rows = []
        for row in data.get("rows", []):
            new_rows.append([
                self._tag if cell is not None else None
                for cell in row
            ])
        data["rows"] = new_rows

        new_json_str = json.dumps(data)
        return text.replace(json_str, new_json_str)

    def _tag_discrepancy_tool_message(self, text: str) -> str:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if not match:
            return text
        json_str = match.group()
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return text
        data["total_discrepancies"] = self._tag
        for entry in data.get("cell_summary", []):
            entry["cell_name"] = self._tag
            entry["total"] = self._tag
        for entry in data.get("site_summary", []):
            entry["site_name"] = self._tag
            entry["total"] = self._tag
        for entry in data.get("parameter_summary", []):
            entry["total"] = self._tag
        new_json_str = json.dumps(data)
        return text.replace(json_str, new_json_str)

    def _map_from_encrypted_positions(self, original_text: str, encrypted_text: str) -> List[Dict]:
        TAG = self._tag
        TAG_LEN = self._tag_len
        mapping = []
        orig_pos = 0
        enc_pos = 0

        while enc_pos < len(encrypted_text):
            tag_idx = encrypted_text.find(TAG, enc_pos)
            if tag_idx == -1:
                break

            literal_before = encrypted_text[enc_pos:tag_idx]

            match_pos = original_text.find(literal_before, orig_pos)
            if match_pos == -1:
                break
            orig_value_start = match_pos + len(literal_before)

            enc_after_tag = tag_idx + TAG_LEN

            next_tag_idx = encrypted_text.find(TAG, enc_after_tag)
            if next_tag_idx == -1:
                literal_after = encrypted_text[enc_after_tag:]
            else:
                literal_after = encrypted_text[enc_after_tag:next_tag_idx]

            if literal_after:
                orig_value_end = original_text.find(literal_after, orig_value_start)
                if orig_value_end == -1:
                    break
            elif next_tag_idx == -1:
                orig_value_end = len(original_text)
            else:
                orig_value_end = orig_value_start

            original_value_raw = original_text[orig_value_start:orig_value_end]
            original_value = original_value_raw.strip()

            if not original_value:
                enc_pos = enc_after_tag
                continue

            leading_spaces = len(original_value_raw) - len(original_value_raw.lstrip())

            mapping.append({
                "start_index": orig_value_start + leading_spaces,
                "original_value": original_value,
            })

            orig_pos = orig_value_start + leading_spaces + len(original_value)
            enc_pos = enc_after_tag

        return mapping

    def _add_hashes(self, entries: List[Dict]) -> List[Dict]:
        for entry in entries:
            entry["hash"] = hashlib.blake2b(entry["original_value"].encode(), digest_size=16).hexdigest()
        return entries

    def _apply_redactions(self, content: str, entries: List[Dict]) -> str:
        sorted_entries = sorted(entries, key=lambda e: e["start_index"], reverse=True)
        redacted = content
        for entry in sorted_entries:
            start = entry["start_index"]
            end = start + len(entry["original_value"])
            redacted = redacted[:start] + f"<HASH:{entry['hash']}>" + redacted[end:]
        return redacted
