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

export interface ProjectFile {
    name: string;
    content: string;
}

export interface Project {
    id: string;
    name: string;
    files: ProjectFile[];
    flashcards?: Flashcard[];
    examQuestions?: ExamQuestion[];
    summary?: string;
    history?: ChatMessage[];
}
