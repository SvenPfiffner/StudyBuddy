import type {
  DocumentMetadata,
  DocumentWithContent,
  ExamQuestion,
  Flashcard,
  ProjectSummary,
  StudyMaterials,
  ChatMessage,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

const handleResponse = async <T>(response: Response): Promise<T> => {
  if (!response.ok) {
    let message = 'Request failed';
    try {
      const error = await response.json();
      message = error.detail || JSON.stringify(error);
    } catch (err) {
      // ignore JSON parse failure and keep default message
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
};

export const ensureUser = async (name: string): Promise<number> => {
  const response = await fetch(`${API_BASE_URL}/ensure_user`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  const data = await handleResponse<{ user_id: number }>(response);
  return data.user_id;
};

export const fetchProjects = async (userId: number): Promise<ProjectSummary[]> => {
  const response = await fetch(`${API_BASE_URL}/users/${userId}/projects`);
  const data = await handleResponse<{ projects: any[] }>(response);
  return data.projects.map((project) => ({
    id: project.id,
    name: project.name,
    summary: project.summary ?? null,
    documentCount: project.document_count ?? 0,
    createdAt: project.created_at,
    updatedAt: project.updated_at,
  }));
};

export const createProject = async (userId: number, name: string): Promise<number> => {
  const response = await fetch(`${API_BASE_URL}/create_project`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, name }),
  });
  const data = await handleResponse<{ project_id: number }>(response);
  return data.project_id;
};

export const removeProject = async (projectId: number): Promise<void> => {
  const response = await fetch(`${API_BASE_URL}/projects/${projectId}`, {
    method: 'DELETE',
  });
  await handleResponse(response);
};

export const fetchProjectDocuments = async (
  projectId: number,
  includeContent = false,
): Promise<DocumentMetadata[] | DocumentWithContent[]> => {
  const response = await fetch(
    `${API_BASE_URL}/projects/${projectId}/documents${includeContent ? '?include_content=true' : ''}`,
  );
  const data = await handleResponse<{ documents: any[] }>(response);
  return data.documents.map((doc) => ({
    id: doc.id,
    title: doc.title,
    createdAt: doc.created_at,
    updatedAt: doc.updated_at,
    ...(includeContent && doc.content !== undefined ? { content: doc.content } : {}),
  })) as DocumentMetadata[] | DocumentWithContent[];
};

export const uploadDocument = async (
  projectId: number,
  title: string,
  content: string,
): Promise<number> => {
  const response = await fetch(`${API_BASE_URL}/add_document`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectId, title, content }),
  });
  const data = await handleResponse<{ document_id: number }>(response);
  return data.document_id;
};

export const removeDocument = async (documentId: number): Promise<void> => {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}`, {
    method: 'DELETE',
  });
  await handleResponse(response);
};

export const triggerGeneration = async (projectId: number): Promise<void> => {
  const response = await fetch(`${API_BASE_URL}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectId }),
  });
  await handleResponse(response);
};

export const fetchFlashcards = async (projectId: number): Promise<Flashcard[]> => {
  const response = await fetch(`${API_BASE_URL}/flashcards`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectId }),
  });
  const data = await handleResponse<Flashcard[]>(response);
  return data;
};

export const fetchPracticeExam = async (projectId: number): Promise<ExamQuestion[]> => {
  const response = await fetch(`${API_BASE_URL}/practice-exam`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectId }),
  });
  const data = await handleResponse<ExamQuestion[]>(response);
  return data;
};

export const fetchSummary = async (projectId: number): Promise<string> => {
  const response = await fetch(`${API_BASE_URL}/summary-with-images`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectId }),
  });
  const data = await handleResponse<{ summary: string }>(response);
  return data.summary;
};

export const fetchStudyMaterials = async (projectId: number): Promise<StudyMaterials> => {
  const [flashcards, examQuestions, summary] = await Promise.all([
    fetchFlashcards(projectId),
    fetchPracticeExam(projectId),
    fetchSummary(projectId),
  ]);
  return { flashcards, examQuestions, summary };
};

export const fetchChatHistory = async (projectId: number): Promise<ChatMessage[]> => {
  const response = await fetch(`${API_BASE_URL}/projects/${projectId}/chat`);
  const data = await handleResponse<{ messages: ChatMessage[] }>(response);
  return data.messages;
};

export const sendChatMessage = async (projectId: number, message: string): Promise<ChatMessage[]> => {
  const response = await fetch(`${API_BASE_URL}/projects/${projectId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });
  const data = await handleResponse<{ messages: ChatMessage[] }>(response);
  return data.messages;
};

export { API_BASE_URL };
