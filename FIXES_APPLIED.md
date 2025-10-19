# Backend Structured Output Fixes

## Problem Identified

Your LLM was hallucinating and adding conversational text around the JSON output instead of returning pure JSON. This happened because:

1. **Prompt Design Issue**: Prompts were too conversational (e.g., "Respond by filling the JSON schema"), which caused the model to generate explanatory text like:
   - "Here is the start of the JSON schema:"
   - "Please fill out the remaining questions..."
   - Additional commentary after the JSON

2. **Temperature Not Optimized**: Using default temperature (~0.7) for structured output allowed the model to be creative and add extra text

3. **Instructor Mode**: Was using `Mode.JSON` which may not be optimal for local models

4. **JSON Extraction**: The extraction logic wasn't robust enough to handle nested brackets and cut off at the right place

## Fixes Applied

### 1. **Improved Prompts** (`service.py`)
   - Removed conversational framing
   - Added explicit "CRITICAL OUTPUT REQUIREMENTS" section
   - Changed from "Respond by filling..." to direct "JSON array:" prompt
   - Explicitly forbids common hallucination patterns:
     - "Do NOT include phrases like 'Here is' or 'Please fill out'"
     - "Do NOT include markdown code fences"
     - "Output ONLY a valid JSON array"

### 2. **Fixed Temperature** (`service.py`)
   - All structured JSON generation now uses `temperature=0.0` (deterministic)
   - This eliminates creative hallucinations
   - Applied to both initial generation and retry attempts

### 3. **Better JSON Extraction** (`service.py`)
   - Implemented proper bracket matching algorithm
   - Handles nested arrays/objects correctly
   - Stops extraction at the matching closing bracket
   - Properly handles strings with escaped characters

### 4. **Instructor Mode** (`llm.py`)
   - Changed from `Mode.JSON` to `Mode.JSON_SIMPLE` (if available)
   - JSON_SIMPLE is more forgiving with local/smaller models
   - Falls back to JSON if JSON_SIMPLE isn't available

## Files Modified

1. `/home/svenp/Documents/StudyBuddy/backend/service.py`
   - `generate_flashcards()` - Updated prompt
   - `generate_practice_exam()` - Updated prompt
   - `_generate_json_with_retry()` - Added temperature=0.0
   - `_maybe_generate_structured()` - Added temperature parameter
   - `_extract_json()` - Implemented bracket matching

2. `/home/svenp/Documents/StudyBuddy/backend/llm.py`
   - `TextGenerationClient.__init__()` - Changed instructor mode

## Testing Recommendations

1. **Test Practice Exam Generation**:
   ```bash
   # In your frontend or via curl
   # Upload a document and try generating a practice exam
   ```
   
2. **Check Logs**: Look for these patterns in the terminal:
   - ✅ No "Failed to parse JSON payload" errors
   - ✅ No "Retrying JSON generation" warnings (ideally)
   - ✅ Clean HTTP 200 responses

3. **Verify Output Quality**:
   - Questions should be clear and relevant
   - All questions should have exactly 4 options
   - `correctAnswer` should match one of the options exactly

4. **Test Flashcard Generation**: Same process as exam generation

## What Changed in Behavior

### Before:
```
Output: "Here is the start of the JSON schema:

[
  {"question": "...", ...}
]

Please fill out the remaining questions..."
```

### After:
```
Output: [
  {"question": "...", ...}
]
```

## If Issues Persist

If you still see hallucinations:

1. **Check the model**: Some models are more instruction-following than others
   - Llama 3.1 Instruct models work well
   - Mistral Instruct models work well
   - Base models (non-instruct) will struggle

2. **Increase max_new_tokens**: If JSON is cut off mid-generation
   - Current: 768 for flashcards, 1024 for exams
   - May need to increase if you have very long study materials

3. **Try without instructor**: The fallback path (JSON parsing) should now work better with the improved extraction logic

4. **Model-specific prompting**: Some models need specific formatting:
   - Llama models: `<|start_header_id|>system<|end_header_id|>`
   - Mistral models: `[INST]...[/INST]`
   
   However, the current prompts should work with most instruction-tuned models.

## Additional Notes

- The `temperature=0.0` change makes output deterministic (same input = same output)
- This is actually desirable for educational content generation
- If you want more variety, you could add a parameter to control this
- The improved JSON extraction now handles the case in your error log where the JSON was valid but had text after it
