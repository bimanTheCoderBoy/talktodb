import re


def clean_final_answer(content: str) -> str:
    """
    Extract final answer from content by looking for "Final Answer:" separator.
    If found, extract content after it and clean it. Otherwise, clean the entire content.
    This preserves reasoning (Thought:, STEP, Action:, Observation:) in internal messages
    but only returns the final answer for UI display.
    
    Args:
        content: Raw content from LLM response
        
    Returns:
        Cleaned content with reasoning text removed
    """
    if not content:
        return ""
    
    text = content.strip()
    
    # First, try to find "Final Answer:" separator (case insensitive)
    final_answer_pattern = r'Final\s+Answer\s*:'
    match = re.search(final_answer_pattern, text, re.IGNORECASE)
    
    if match:
        # Extract everything after "Final Answer:"
        extracted = text[match.end():].strip()
        text = extracted
    
    # Remove JSON structures if present
    json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    text = re.sub(json_pattern, '', text, flags=re.DOTALL)
    
    # Remove markdown code blocks
    text = re.sub(r'```json\s*', '', text)
    
    # Split into lines and filter out any remaining reasoning lines
    lines = text.split('\n')
    cleaned_lines = []
    
    skip_patterns = [
        r'^\s*Thought\s*:',
        r'^\s*STEP\s*\d+',
        r'^\s*Action\s*:',
        r'^\s*Observation\s*:',
        r'^\s*Final\s+Answer:',
        r'^\s*-?\s*STEP',
        r'^\s*\[Final\s+Answer',
    ]
    
    for line in lines:
        # Skip lines that match reasoning patterns
        if any(re.match(pattern, line, re.IGNORECASE) for pattern in skip_patterns):
            continue
        cleaned_lines.append(line)
    
    cleaned_text = '\n'.join(cleaned_lines).strip()
    
    # Remove any remaining "Final Answer:" prefixes (fallback)
    if cleaned_text.lower().startswith('final answer:'):
        cleaned_text = cleaned_text[13:].strip()
    
    return cleaned_text

