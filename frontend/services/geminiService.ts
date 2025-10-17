import { GoogleGenAI, Type } from "@google/genai";
import type { Flashcard, ExamQuestion, ChatMessage } from '../types';

if (!process.env.API_KEY) {
    throw new Error("API_KEY environment variable not set");
}

const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });

const flashcardSchema = {
  type: Type.ARRAY,
  items: {
    type: Type.OBJECT,
    properties: {
      question: {
        type: Type.STRING,
        description: 'The question or term for the front of the flashcard.'
      },
      answer: {
        type: Type.STRING,
        description: 'The answer or definition for the back of the flashcard.'
      }
    },
    required: ['question', 'answer']
  }
};

const examSchema = {
    type: Type.ARRAY,
    items: {
      type: Type.OBJECT,
      properties: {
        question: {
          type: Type.STRING,
          description: 'The multiple-choice question.'
        },
        options: {
          type: Type.ARRAY,
          items: {
            type: Type.STRING,
          },
          description: 'An array of 4 possible answers.'
        },
        correctAnswer: {
            type: Type.STRING,
            description: 'The correct answer, which must be one of the provided options.'
        }
      },
      required: ['question', 'options', 'correctAnswer']
    }
  };


export const generateFlashcards = async (scriptContent: string): Promise<Flashcard[]> => {
    try {
        const response = await ai.models.generateContent({
            model: 'gemini-2.5-flash',
            contents: `Based on the following script, generate a comprehensive set of flashcards. Each flashcard should have a 'question' and an 'answer'. The questions should cover the key concepts, definitions, and important facts in the text.

            Script:
            ---
            ${scriptContent}
            ---
            
            Please provide the output in the specified JSON format.`,
            config: {
                responseMimeType: 'application/json',
                responseSchema: flashcardSchema,
            }
        });

        const jsonString = response.text.trim();
        const flashcards = JSON.parse(jsonString);
        return flashcards as Flashcard[];

    } catch (error) {
        console.error("Error generating flashcards:", error);
        throw new Error("Failed to generate flashcards. Please check the script content and try again.");
    }
};

export const generatePracticeExam = async (scriptContent: string): Promise<ExamQuestion[]> => {
    try {
        const response = await ai.models.generateContent({
            model: 'gemini-2.5-flash',
            contents: `Based on the following script, generate a multiple-choice practice exam with at least 5 questions. Each question should have a 'question', an array of 4 'options', and the 'correctAnswer' which must be one of the provided options. The questions should test the understanding of the material.

            Script:
            ---
            ${scriptContent}
            ---
            
            Please provide the output in the specified JSON format.`,
             config: {
                responseMimeType: 'application/json',
                responseSchema: examSchema,
            }
        });

        const jsonString = response.text.trim();
        const examQuestions = JSON.parse(jsonString);
        return examQuestions as ExamQuestion[];
    } catch (error) {
        console.error("Error generating practice exam:", error);
        throw new Error("Failed to generate practice exam. Please check the script content and try again.");
    }
};

const generateImage = async (prompt: string): Promise<string> => {
    try {
        const response = await ai.models.generateImages({
            model: 'imagen-4.0-generate-001',
            prompt: prompt,
            config: {
              numberOfImages: 1,
              outputMimeType: 'image/jpeg',
              aspectRatio: '16:9',
            },
        });

        if (response.generatedImages && response.generatedImages.length > 0) {
            return response.generatedImages[0].image.imageBytes;
        }
        throw new Error("No image was generated.");

    } catch (error) {
        console.error(`Error generating image for prompt "${prompt}":`, error);
        throw new Error(`Failed to generate image for prompt: ${prompt}`);
    }
};

export const generateSummary = async (scriptContent: string, onProgress: (message: string) => void): Promise<string> => {
    try {
        onProgress("Consulting the muses for a summary...");
        // Step 1: Generate Markdown Summary with Image Placeholders
        const summaryResponse = await ai.models.generateContent({
            model: 'gemini-2.5-pro',
            contents: `Your task is to create a comprehensive, well-structured summary of the provided text. The summary must be in Markdown format.
While summarizing, identify up to 3 key concepts that would be significantly clarified by a visual aid.
For each of these concepts, you must insert a placeholder at the most relevant point in the text.
The placeholder MUST be in the exact format: \`[IMAGE_PROMPT: Your descriptive and concise image prompt here]\`.

Example:
...This led to the development of the photosynthesis process.
[IMAGE_PROMPT: A detailed diagram of the photosynthesis process in a plant cell, showing chloroplasts, light, water, and CO2.]
Photosynthesis allows plants to convert...

Now, process the following text:
---
${scriptContent}
---`,
        });

        let markdownSummary = summaryResponse.text;

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
        const chat = ai.chats.create({
            model: 'gemini-2.5-flash',
            history: history,
            config: {
                systemInstruction: systemInstruction,
            },
        });
        const response = await chat.sendMessage({ message: newMessage });
        return response.text;
    } catch (error) {
        console.error("Error continuing chat:", error);
        throw new Error("Failed to get a response from the AI. Please try again.");
    }
};
