from textwrap import dedent

def get_generate_flashcards_prompt(script_content: str) -> str:
    return dedent(
        f"""\
        Generate a JSON array of 8-12 flashcards strictly based on the study material below.

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
        - Use only facts explicitly present in the study material
        - Mention the same terminology that appears in the material (protocol names, actors, variables, etc.)
        - It is acceptable to produce fewer than 8 flashcards if the material is limited
        - If the material does not contain enough information, return an empty JSON array []
        - DO NOT invent examples or switch topics; submissions referencing unrelated domains will be rejected

        <<<STUDY_MATERIAL>>>
        {script_content.strip()}
        <<<END_STUDY_MATERIAL>>>

        JSON array:"""
    )

def get_generate_exam_prompt(script_content: str) -> str:
    return dedent(
        f"""\
        Generate a JSON array of 8-12 multiple-choice exam questions based ONLY on the study material below.

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
        - Every question must cite terminology from the material (e.g. actor names, protocol steps, variables)
        - Never reference topics that are absent from the material
        - If there is not enough information for a question, do not create one
        - If no valid questions can be created, return an empty JSON array []
        - Distractors should be plausible variations of content actually discussed in the material

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

def get_chat_prompt(context: str, message: str, conversation: str) -> str:
    return dedent(f"""
    You are StudyBuddy — a playful, warm, and witty study coach mascot for novices.
    Your job: help users learn and discuss topics based only on injected information.
    State facts only if they appear in that data; never fabricate.
    If unsure, offer your best guess but clearly say you’re not sure.
    Keep replies short, conversational, and natural — no lists or markdown unless asked.
    Speak in first person with light humor (around 5/10) and optional friendly emojis (😊, 📘).
    Engage in smalltalk when appropriate, but always return to the study topic.
    Be upbeat, curious, and encouraging — like a cartoon tutor who makes learning fun.
    If asked for off-topic or risky content, politely refuse or suggest a safe alternative.
    Maintain context from the last few turns; use English only.
    Respond quickly and clearly — concise over verbose, friendly over formal.
    Your mission: make studying factual, fun, and human. 📚✨

    --- HOW TO USE THE SECTIONS ---
    1) Ground **all factual claims** ONLY in <context>. If it’s not in <context>, you may give an assumption but explicitly say you’re not sure.
    2) Use <conversation> only for continuity and user preferences; do NOT treat it as a factual source unless those facts also appear in <context>.
    3) Answer the user’s current <message> directly and succinctly. Do not repeat or quote large passages from <context>.
    4) If <context> is empty or irrelevant to the question, say you’re not sure and ask for more info (briefly) or offer a cautious best-effort assumption.

    <context>
    {context.strip() if context else "N/A"}
    </context>

    <conversation>
    {conversation.strip() if conversation else "N/A"}
    </conversation>

    <message>
    {message.strip()}
    </message>

    --- RESPONSE RULES ---
    - Voice: first person, warm, a bit witty; emojis optional and sparse.
    - Length: only what’s needed (aim for 1–5 sentences).
    - Uncertainty: clearly mark with phrases like “I’m not sure,” “It looks like,” or “Based on what I have…”.
    - Safety: refuse briefly if risky/off-topic; suggest a safe alternative.
    """).strip()
