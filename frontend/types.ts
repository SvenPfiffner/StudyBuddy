export interface Flashcard {
  question: string;
  answer: string;
}

export interface ExamQuestion {
  question:string;
  options: string[];
  correctAnswer: string;
}

export interface ChatMessage {
  role: 'user' | 'model';
  parts: { text: string }[];
}

export type StudyMode = 'flashcards' | 'exam' | 'summary' | 'chat';

export interface DocumentMetadata {
  id: number;
  title: string;
  createdAt: string;
  updatedAt: string;
}

export interface DocumentWithContent extends DocumentMetadata {
  content: string;
}

export interface ProjectSummary {
  id: number;
  name: string;
  summary?: string | null;
  documentCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface StudyMaterials {
  flashcards: Flashcard[];
  examQuestions: ExamQuestion[];
  summary: string;
}
