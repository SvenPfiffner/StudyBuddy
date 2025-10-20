from textwrap import dedent

def get_generate_flashcards_prompt(script_content: str) -> str:
    return dedent(
        f"""\
        Generate a JSON array of 8-12 flashcards from the study material below.

        CRITICAL OUTPUT REQUIREMENTS:
        - Output ONLY a valid JSON array. Start with [ and end with ]
        - Do NOT include any explanatory text before or after the JSON
        - Do NOT include markdown code fences (```)
        - Do NOT include phrases like "Here is" or "Please complete"
        - Your entire response must be parseable as JSON

        Each flashcard object must have:
        - "question": A single sentence prompt (not yes/no question)
        - "answer": A specific answer in 1-3 sentences

        Quality guidelines:
        - Cover core definitions, facts, processes, and relationships
        - Make each card self-contained and memorizable
        - Avoid repeating information across cards
        - Prioritize factual precision over creative wording

        <<<STUDY_MATERIAL>>>
        {script_content.strip()}
        <<<END_STUDY_MATERIAL>>>

        JSON array:"""
    )

def get_generate_exam_prompt(script_content: str) -> str:
    return dedent(
        f"""\
        Generate a JSON array of 5-7 multiple-choice exam questions based on the study material below.

        CRITICAL OUTPUT REQUIREMENTS:
        - Output ONLY a valid JSON array. Start with [ and end with ]
        - Do NOT include any explanatory text before or after the JSON
        - Do NOT include markdown code fences (```)
        - Do NOT include phrases like "Here is" or "Please fill out"
        - Your entire response must be parseable as JSON

        Each question object must have:
        - "question": A clear, direct question (one sentence)
        - "options": An array of exactly 4 answer choices (strings)
        - "correctAnswer": The exact text of one of the options

        Quality guidelines:
        - Target distinct, high-value concepts from the material
        - Make options mutually exclusive and similar in length
        - Only the correct answer should be fully accurate
        - Create realistic distractors based on common misconceptions

        <<<STUDY_MATERIAL>>>
        {script_content.strip()}
        <<<END_STUDY_MATERIAL>>>

        JSON array:"""
    )

def get_generate_summary_prompt(script_content: str) -> str:
    return dedent(
        f"""\
        Create a study guide summary following this EXACT structure. Do not deviate from this format.

        MANDATORY FORMAT - Copy this structure exactly:

        ## Introduction
        [Write 1-2 paragraphs here introducing the main topic and why it matters]

        [IMAGE_PROMPT: Describe a vivid illustration scene here with concrete visual details]

        ## Key Concepts
        [Write 2-3 paragraphs here explaining the main ideas, processes, or mechanisms]

        [IMAGE_PROMPT: Describe another illustration showing the concepts in action]

        ## Summary
        [Write 1-2 paragraphs here summarizing the key takeaways]

        [IMAGE_PROMPT: Describe a final illustration that reinforces the main message]

        CRITICAL RULES:
        1. Start with "## Introduction" exactly as shown
        2. After introduction paragraphs, add ONE line: [IMAGE_PROMPT: description]
        3. Then add "## Key Concepts" section with paragraphs
        4. After key concepts, add ONE line: [IMAGE_PROMPT: description]
        5. Then add "## Summary" section with paragraphs
        6. After summary, add ONE line: [IMAGE_PROMPT: description]
        7. Do NOT use markdown image syntax like ![text](url)
        8. Do NOT skip sections or change section names
        9. IMAGE_PROMPT descriptions should be SHORT (20-40 words maximum)
            
        IMAGE PROMPT RULES - READ CAREFULLY:
        - Create SYMBOLIC or CONCEPTUAL scenes, NOT technical diagrams
        - NO charts, graphs, flowcharts, circuit diagrams, protocol diagrams, or network diagrams
        - NO text, labels, arrows, or annotations in the image
        - Think like stock photography: what OBJECTS, SCENES, or METAPHORS represent this concept?
        - Use concrete objects: locks, keys, doors, hands, books, light, nature, architecture
        - Focus on: lighting, mood, composition, realistic objects, symbolic representation
            
        GOOD examples (symbolic/conceptual):
        [IMAGE_PROMPT: A glowing padlock surrounded by floating digital keys in a dark blue environment, symbolizing encryption and security]
        [IMAGE_PROMPT: Two hands exchanging a sealed envelope with a wax stamp, representing secure message transfer, warm lighting]
        [IMAGE_PROMPT: A fortress gate with intricate lock mechanisms, symbolizing authentication, dramatic sunset lighting]
            
        BAD examples (too technical - avoid these):
        ❌ A flowchart showing client-server handshake protocol
        ❌ A diagram with arrows connecting nodes
        ❌ A cryptographic algorithm visualization with equations
        ❌ A network topology diagram

        <<<STUDY_MATERIAL>>>
        {script_content.strip()}
        <<<END_STUDY_MATERIAL>>>

        Now write the study guide following the exact format above:

        ## Introduction"""
    )

def get_chat_prompt(system_instruction: str, message: str, conversation: str) -> str:
    return dedent(
        f"""{system_instruction.strip()}

        You are StudyBuddy, a focused tutor who responds with clear, evidence-based explanations grounded in the conversation history.

        Instructions:
        - Provide the best possible answer to the latest user question.
        - If key information is missing, ask the user to clarify instead of guessing.
        - Use concrete examples when they improve understanding.
        - Keep the reply within four short paragraphs or fewer.
        - Do not include meta-commentary such as "Please note" or system-level reminders.
        - When referencing earlier turns, quote short phrases from the conversation in quotation marks.
        - Silently reflect on the user's intent before responding, but do not reveal that reflection.

        Conversation so far:
        {conversation}

        User: {message}
        Assistant:"""
    )