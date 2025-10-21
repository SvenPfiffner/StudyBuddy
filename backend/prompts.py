from textwrap import dedent

def get_generate_flashcards_prompt(script_content: str) -> str:
    return dedent(
        f"""\
        Generate a JSON array of 20-30 flashcards from the study material below.

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
        Generate a JSON array of 15-20 multiple-choice exam questions based on the study material below.

        CRITICAL OUTPUT REQUIREMENTS:
        - Output ONLY a valid JSON array. Start with [ and end with ]
        - Do NOT include any explanatory text before or after the JSON
        - Do NOT include markdown code fences (```)
        - Your entire response must be parseable as JSON
        - Each question MUST have EXACTLY 4 options - no more, no less

        Each question object must have:
        - "question": A clear, direct question (one sentence)
        - "options": An array of EXACTLY 4 answer choices (strings) - this is mandatory
        - "correctAnswer": The exact text of one of the 4 options

        Quality guidelines:
        - Target distinct, high-value concepts from the material
        - Make all 4 options mutually exclusive and similar in length
        - Only the correct answer should be fully accurate
        - Create 3 realistic distractors based on common misconceptions

        <<<STUDY_MATERIAL>>>
        {script_content.strip()}
        <<<END_STUDY_MATERIAL>>>

        JSON array with each question having EXACTLY 4 options:"""
    )

def get_generate_summary_prompt(script_content: str) -> str:
    return dedent(
        f"""\
        Create a study guide summary following this EXACT structure. Do not deviate from this format.

        MANDATORY FORMAT - Copy this structure exactly:

        ## Introduction
        [Write 3-4 paragraphs here introducing the main topic and why it matters]

        [IMAGE_PROMPT: Describe a vivid illustration scene here with concrete visual details]

        ## Key Concepts
        [Write 4-6 paragraphs here explaining the main ideas, processes, or mechanisms]

        [IMAGE_PROMPT: Describe another illustration showing the concepts in action]

        ## Summary
        [Write 2-3 paragraphs here summarizing the key takeaways]

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
    return dedent(f"""You are a Tutor that answers using ONLY the STUDY MATERIALS.

        STUDY MATERIALS (verbatim context)
        {system_instruction}

        YOUR TASK
        Answer the user's CURRENT QUESTION using only the materials above.

        STRICT RULES
        - If the answer IS found: respond concisely with concrete facts and (if useful) a short quote.
        - If the answer is NOT found: reply with exactly:
        I couldn't find that information in your study materials.
        - Do NOT mention document selection, do NOT ask for more documents, do NOT add meta commentary.
        - No chit-chat; only answer the question.
        - Style: max 5 sentences; no lists unless asked; no markdown headers; no extra blank lines.

        PREVIOUS CONVERSATION (may be empty)
        {conversation if conversation.strip() else "(none)"}

        CURRENT QUESTION
        {message}

        YOUR ANSWER (plain text, compact):"""
    )
