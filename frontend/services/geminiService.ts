import type { Flashcard, ExamQuestion, ChatMessage } from '../types';

// Backend API base URL - change this to your deployed backend URL
const API_BASE_URL = 'http://localhost:8000';


export const generateFlashcards = async (scriptContent: string): Promise<Flashcard[]> => {
    try {
        const response = await fetch(`${API_BASE_URL}/flashcards`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ scriptContent }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to generate flashcards');
        }

        const flashcards = await response.json();
        return flashcards as Flashcard[];

    } catch (error) {
        console.error("Error generating flashcards:", error);
        throw new Error("Failed to generate flashcards. Please check the script content and try again.");
    }
};

export const generatePracticeExam = async (scriptContent: string): Promise<ExamQuestion[]> => {
    try {
        const response = await fetch(`${API_BASE_URL}/practice-exam`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ scriptContent }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to generate practice exam');
        }

        const examQuestions = await response.json();
        return examQuestions as ExamQuestion[];
    } catch (error) {
        console.error("Error generating practice exam:", error);
        throw new Error("Failed to generate practice exam. Please check the script content and try again.");
    }
};

const generateImage = async (prompt: string): Promise<string> => {
    try {
        const response = await fetch(`${API_BASE_URL}/generate-image`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ prompt }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to generate image');
        }

        const data = await response.json();
        return data.image; // base64 encoded image

    } catch (error) {
        console.error(`Error generating image for prompt "${prompt}":`, error);
        throw new Error(`Failed to generate image for prompt: ${prompt}`);
    }
};

export const generateSummary = async (scriptContent: string, onProgress: (message: string) => void): Promise<string> => {
    try {
        onProgress("Consulting the muses for a summary...");
        
        // Step 1: Generate Markdown Summary with Image Placeholders from backend
        const summaryResponse = await fetch(`${API_BASE_URL}/summary-with-images`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ scriptContent }),
        });

        if (!summaryResponse.ok) {
            const error = await summaryResponse.json();
            throw new Error(error.detail || 'Failed to generate summary');
        }

        const data = await summaryResponse.json();
        let markdownSummary = data.summary;

        onProgress("Ideating some artistic masterpieces...");
        
        // Step 2: Parse Placeholders
        const imagePromptRegex = /\[IMAGE_PROMPT:\s*(.*?)\]/g;
        const prompts = [...markdownSummary.matchAll(imagePromptRegex)].map(match => match[1].trim());

        if (prompts.length === 0) {
            onProgress("This one's a masterpiece of words alone!");
            return markdownSummary; // No images to generate
        }

        onProgress(`Warming up the digital easel for ${prompts.length} image(s)...`);
        
        // Step 3: Generate Images using Promise.allSettled for resilience
        const imagePromises = prompts.map(prompt => generateImage(prompt));
        const imageResults = await Promise.allSettled(imagePromises);

        onProgress("Adding the finishing touches to the gallery...");
        
        // Step 4: Replace Placeholders with Markdown Images or error messages
        let imageIndex = 0;
        markdownSummary = markdownSummary.replace(imagePromptRegex, () => {
            if (imageIndex < imageResults.length) {
                const result = imageResults[imageIndex];
                const promptText = prompts[imageIndex];
                imageIndex++;

                if (result.status === 'fulfilled') {
                    const base64Data = result.value;
                    return `\n\n<img src="data:image/jpeg;base64,${base64Data}" alt="${promptText}" class="my-6 rounded-lg shadow-lg w-full" />\n\n`;
                } else {
                    console.error(`Failed to generate image for prompt: "${promptText}"`, result.reason);
                    // Embed a user-friendly error message in the summary
                    return `\n\n<div class="my-6 p-4 bg-gray-700/50 border border-red-500/50 rounded-lg text-center text-red-400"><em>The AI artist had a creative block while trying to paint: "${promptText}". Please try again later.</em></div>\n\n`;
                }
            }
            return ''; // Should not happen if logic is correct
        });

        return markdownSummary;

    } catch (error) {
        console.error("Error generating summary:", error);
        throw new Error("Failed to generate summary with images. Please check the content and try again.");
    }
};

export const continueChat = async (history: ChatMessage[], systemInstruction: string, newMessage: string): Promise<string> => {
    try {
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                history,
                systemInstruction,
                message: newMessage,
            }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to get chat response');
        }

        const data = await response.json();
        return data.message;
    } catch (error) {
        console.error("Error continuing chat:", error);
        throw new Error("Failed to get a response from the AI. Please try again.");
    }
};
