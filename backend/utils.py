import re
from fastapi import HTTPException, status

def fix_markdown(markdown: str) -> str:
    """
    Fix common markdown issues in the provided markdown string.

    Args:
        markdown (str): The markdown content to be fixed.

    Returns:
        str: The fixed markdown content.
    """
    # If the model didn't include the ## Introduction prefix, add it back
    if not markdown.strip().startswith("##"):
        markdown = "## Introduction\n" + markdown
        
    # Remove everything after common hallucination patterns
    stop_patterns = [
        r'---+\s*Human:',
        r'---+\s*Revised',
        r'---+\s*\*\*Revised',
        r'Human:\s*',
        r'Assistant:\s*',
        r'Revised\s+Introduction',
        r'Can you rephrase',
    ]
        
    for pattern in stop_patterns:
        match = re.search(pattern, markdown, re.IGNORECASE)
        if match:
            markdown = markdown[:match.start()]
            break
        
    # Remove trailing incomplete sentences
    markdown = markdown.strip()
    if markdown and not markdown[-1] in '.!?)':
        # Find last complete sentence
        last_period = max(
            markdown.rfind('. '),
            markdown.rfind('.\n'),
            markdown.rfind('!\n'),
            markdown.rfind('?\n')
        )
        if last_period > 0:
            markdown = markdown[:last_period + 1]
        
    # Remove meta-commentary
    cleanup_patterns = [
        r'Please note.*?(?:\.|$)',
        r'Remember.*?(?:\.|$)',
        r'Note:.*?(?:\.|$)',
        r'\*\*Note:.*?(?:\.|$)',
    ]
        
    for pattern in cleanup_patterns:
        markdown = re.sub(pattern, "", markdown, flags=re.IGNORECASE)
        
    # Clean up markdown image syntax that the model might hallucinate
    # Convert ![alt text](url) to a generic IMAGE_PROMPT if found
    markdown_image_pattern = r'!\[([^\]]*)\]\([^\)]+\)'
    def replace_markdown_image(match):
        alt_text = match.group(1)
        # Try to extract a meaningful description from the alt text
        if alt_text and len(alt_text) > 10:
            return f"[IMAGE_PROMPT: {alt_text}]"
        else:
            # If alt text is empty or too short, create a generic prompt
            return "[IMAGE_PROMPT: An illustration related to the study material]"
        
    markdown = re.sub(markdown_image_pattern, replace_markdown_image, markdown)
    
    lines = markdown.split('\n')
    fixed_lines = []
        
    for i, line in enumerate(lines):
        # Strip leading whitespace from ALL non-empty lines
        # The model often adds indentation which breaks markdown
        if line.strip():
            cleaned_line = line.strip()
                
            # Check if this is an IMAGE_PROMPT line
            if cleaned_line.startswith('[IMAGE_PROMPT:'):
                # Ensure blank line before (if not already)
                if fixed_lines and fixed_lines[-1].strip():
                    fixed_lines.append('')
                fixed_lines.append(cleaned_line)
                # Ensure blank line after
                if i + 1 < len(lines) and lines[i + 1].strip():
                    fixed_lines.append('')
            # Check if this is a header
            elif cleaned_line.startswith('##'):
                # Ensure blank line before header (if not already and not first line)
                if fixed_lines and fixed_lines[-1].strip():
                    fixed_lines.append('')
                fixed_lines.append(cleaned_line)
                # No extra line after headers
            else:
                # Regular content line - just strip the indentation
                fixed_lines.append(cleaned_line)
        else:
            # Preserve empty lines
            fixed_lines.append('')
    
    markdown = '\n'.join(fixed_lines)
    # Clean up excessive whitespace (more than 2 blank lines)
    markdown = re.sub(r'\n{3,}', '\n\n', markdown.strip())
    return markdown

def validate_exam_questions(questions):
    for idx, question in enumerate(questions):
        if len(question.options) != 4:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Generated exam question {idx+1} does not have exactly four options (has {len(question.options)}).",
            )

        if question.correctAnswer not in question.options:
            matched_option = None
            correct_lower = question.correctAnswer.lower()
            for option in question.options:
                option_lower = option.lower()
                if correct_lower in option_lower or option_lower in correct_lower:
                    matched_option = option
                    break

            if matched_option:
                question.correctAnswer = matched_option
            else:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Generated exam question {idx+1} has a correctAnswer that is not one of the options.",
                )
    return questions