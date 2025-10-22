import React, { useState, useCallback, useEffect } from 'react';
import ProjectList from './components/ProjectList';
import ProjectDetail from './components/ProjectDetail';
import FlashcardViewer from './components/FlashcardViewer';
import PracticeExam from './components/PracticeExam';
import SummaryViewer from './components/SummaryViewer';
import ChatInterface from './components/ChatInterface';
import Spinner from './components/Spinner';
import {
  ensureUser,
  fetchProjects,
  createProject as apiCreateProject,
  removeProject as apiRemoveProject,
  fetchProjectDocuments,
  uploadDocument,
  removeDocument,
  triggerGeneration,
  fetchStudyMaterials,
  continueChat,
} from './services/api';
import type {
  ProjectSummary,
  DocumentWithContent,
  StudyMaterials,
  ChatMessage,
  StudyMode,
} from './types';

import iconPng from './icons/icon.png';

const Logo = () => (
  <img src={iconPng} alt="Study Buddy icon" className="w-10 h-10 object-contain" />
);

const DEFAULT_USER_NAME = 'study-buddy-user';

type View = 'list' | 'detail' | 'study';

const App: React.FC = () => {
  const [userId, setUserId] = useState<number | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [currentProjectId, setCurrentProjectId] = useState<number | null>(null);
  const [currentView, setCurrentView] = useState<View>('list');
  const [studyMode, setStudyMode] = useState<StudyMode>('summary');
  const [isInitialising, setIsInitialising] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isProjectLoading, setIsProjectLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [documentList, setDocumentList] = useState<DocumentWithContent[]>([]);
  const [materials, setMaterials] = useState<StudyMaterials | null>(null);
  const [chatHistories, setChatHistories] = useState<Record<number, ChatMessage[]>>({});
  const [isChatResponding, setIsChatResponding] = useState(false);

  const refreshProjects = useCallback(async (uid: number) => {
    const projectList = await fetchProjects(uid);
    setProjects(projectList);
  }, []);

  useEffect(() => {
    const initializeApp = async () => {
      try {
        const ensuredUserId = await ensureUser(DEFAULT_USER_NAME);
        setUserId(ensuredUserId);
        await refreshProjects(ensuredUserId);
      } catch (e) {
        const message = e instanceof Error ? e.message : 'Could not load your projects.';
        setError(message);
      } finally {
        setIsInitialising(false);
      }
    };

    initializeApp();
  }, [refreshProjects]);

  const currentProject = currentProjectId !== null
    ? projects.find((p) => p.id === currentProjectId) ?? null
    : null;

  const hasStudyMaterials = Boolean(
    materials && (
      materials.flashcards.length > 0 ||
      materials.examQuestions.length > 0 ||
      materials.summary.trim().length > 0
    )
  );

  useEffect(() => {
    if (currentView === 'detail' && currentProjectId !== null) {
      const projectExists = projects.some((p) => p.id === currentProjectId);
      if (!projectExists) {
        setCurrentProjectId(null);
        setCurrentView('list');
      }
    }
    if (currentView === 'study' && !hasStudyMaterials) {
      setCurrentView('detail');
    }
  }, [currentProjectId, currentView, projects, hasStudyMaterials]);

  const loadProjectData = useCallback(async (projectId: number) => {
    setIsProjectLoading(true);
    try {
      const docsWithContent = await fetchProjectDocuments(projectId, true) as DocumentWithContent[];
      setDocumentList(docsWithContent);

      const storedMaterials = await fetchStudyMaterials(projectId);
      const containsContent =
        storedMaterials.flashcards.length > 0 ||
        storedMaterials.examQuestions.length > 0 ||
        storedMaterials.summary.trim().length > 0;
      setMaterials(containsContent ? storedMaterials : null);
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to load project data.';
      setError(message);
      setMaterials(null);
    } finally {
      setIsProjectLoading(false);
    }
  }, []);

  const handleCreateProject = useCallback(async (name: string) => {
    if (!userId) return;
    try {
      await apiCreateProject(userId, name);
      await refreshProjects(userId);
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to create the project.';
      setError(message);
    }
  }, [userId, refreshProjects]);

  const handleDeleteProject = useCallback(async (idToDelete: number) => {
    if (!userId) return;
    if (window.confirm('Are you sure you want to delete this project and all its files? This action cannot be undone.')) {
      try {
        await apiRemoveProject(idToDelete);
        await refreshProjects(userId);
        if (currentProjectId === idToDelete) {
          setCurrentProjectId(null);
          setCurrentView('list');
          setDocumentList([]);
          setMaterials(null);
        }
      } catch (e) {
        const message = e instanceof Error ? e.message : 'Failed to delete the project.';
        setError(message);
      }
    }
  }, [userId, currentProjectId, refreshProjects]);

  const handleSelectProject = useCallback(async (id: number) => {
    setCurrentProjectId(id);
    setCurrentView('detail');
    setStudyMode('summary');
    setError(null);
    await loadProjectData(id);
  }, [loadProjectData]);

  const handleBackToProjects = useCallback(() => {
    setCurrentProjectId(null);
    setCurrentView('list');
  }, []);

  const handleAddFileToProject = useCallback(async (fileName: string, content: string) => {
    if (!currentProjectId) return;
    if (documentList.some((doc) => doc.title === fileName)) {
      alert(`A file named "${fileName}" already exists in this project.`);
      return;
    }

    try {
      await uploadDocument(currentProjectId, fileName, content);
      const docsWithContent = await fetchProjectDocuments(currentProjectId, true) as DocumentWithContent[];
      setDocumentList(docsWithContent);
      setMaterials(null);
      if (userId) {
        await refreshProjects(userId);
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to add the file to your project.';
      setError(message);
    }
  }, [currentProjectId, documentList, userId, refreshProjects]);

  const handleDeleteFile = useCallback(async (documentId: number) => {
    if (!currentProjectId) return;
    const targetDocument = documentList.find((doc) => doc.id === documentId);
    const fileName = targetDocument?.title ?? 'this file';

    if (window.confirm(`Are you sure you want to delete the file "${fileName}"?`)) {
      try {
        await removeDocument(documentId);
        const docsWithContent = await fetchProjectDocuments(currentProjectId, true) as DocumentWithContent[];
        setDocumentList(docsWithContent);
        setMaterials(null);
        if (userId) {
          await refreshProjects(userId);
        }
      } catch (e) {
        const message = e instanceof Error ? e.message : 'Failed to delete the file.';
        setError(message);
      }
    }
  }, [currentProjectId, documentList, userId, refreshProjects]);

  const handleGenerateMaterials = useCallback(async () => {
    if (!currentProjectId || documentList.length === 0) return;

    setIsGenerating(true);
    setLoadingMessage('Waking up the AI study buddy...');
    setError(null);

    try {
      setLoadingMessage('Generating new study materials...');
      await triggerGeneration(currentProjectId);

      setLoadingMessage('Retrieving your study package...');
      const generatedMaterials = await fetchStudyMaterials(currentProjectId);
      const containsContent =
        generatedMaterials.flashcards.length > 0 ||
        generatedMaterials.examQuestions.length > 0 ||
        generatedMaterials.summary.trim().length > 0;

      setMaterials(containsContent ? generatedMaterials : null);
      if (containsContent) {
        setStudyMode('summary');
        setCurrentView('study');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'An unexpected error occurred.';
      setError(message);
    } finally {
      setIsGenerating(false);
      setLoadingMessage(null);
    }
  }, [currentProjectId, documentList.length]);

  const handleSendMessage = useCallback(async (message: string) => {
    if (!currentProjectId) return;

    const history = chatHistories[currentProjectId] ?? [];
    const userMessage: ChatMessage = { role: 'user', parts: [{ text: message }] };
    const updatedHistory = [...history, userMessage];

    setChatHistories((prev) => ({ ...prev, [currentProjectId]: updatedHistory }));
    setIsChatResponding(true);

    try {
      const systemInstruction = `You are a helpful tutor. The user has provided the following study material, split into one or more files. Answer their questions based ONLY on this content. If the answer cannot be found in the content, say that you don't have enough information from the provided documents.
        ---
        CONTENT START
        ${documentList
          .map((doc) => `--- Start of file: ${doc.title} ---\n${doc.content}\n--- End of file: ${doc.title} ---`)
          .join('\n\n')}
        CONTENT END
        ---`;

      const aiResponseText = await continueChat(history, systemInstruction, message);
      const aiMessage: ChatMessage = { role: 'model', parts: [{ text: aiResponseText }] };
      const finalHistory = [...updatedHistory, aiMessage];
      setChatHistories((prev) => ({ ...prev, [currentProjectId]: finalHistory }));
    } catch (err) {
      const messageText = err instanceof Error ? err.message : 'An error occurred while chatting.';
      setError(messageText);
      setChatHistories((prev) => ({ ...prev, [currentProjectId]: history }));
    } finally {
      setIsChatResponding(false);
    }
  }, [currentProjectId, chatHistories, documentList]);

  const projectDocuments = documentList.map(({ content, ...meta }) => meta);
  const currentHistory = currentProjectId !== null ? chatHistories[currentProjectId] ?? [] : [];

  const renderContent = () => {
    if (isInitialising) {
      return (
        <div className="flex flex-col items-center justify-center text-center">
          <Spinner />
          <p className="mt-4 text-gray-400">Loading your projects...</p>
        </div>
      );
    }

    switch (currentView) {
      case 'study':
        if (currentProject && materials && hasStudyMaterials) {
          return (
            <div className="w-full">
              <div className="flex items-center justify-between mb-8">
                <div>
                  <h2 className="text-2xl font-bold text-white">{currentProject.name}</h2>
                  <p className="text-md text-gray-400">Generated from {documentList.length} file(s)</p>
                </div>
                <button
                  onClick={() => setCurrentView('detail')}
                  className="px-4 py-2 border border-gray-600 hover:bg-gray-700 text-gray-300 font-semibold rounded-lg transition-colors"
                >
                  &larr; Back to Project
                </button>
              </div>

              <div className="mb-8 flex justify-center border-b border-gray-700">
                <button
                  onClick={() => setStudyMode('summary')}
                  className={`px-6 py-3 text-lg font-semibold transition-colors duration-200 ${studyMode === 'summary' ? 'text-cyan-400 border-b-2 border-cyan-400' : 'text-gray-400 hover:text-white'}`}
                >
                  Summary
                </button>
                <button
                  onClick={() => setStudyMode('flashcards')}
                  className={`px-6 py-3 text-lg font-semibold transition-colors duration-200 ${studyMode === 'flashcards' ? 'text-cyan-400 border-b-2 border-cyan-400' : 'text-gray-400 hover:text-white'}`}
                >
                  Flashcards
                </button>
                <button
                  onClick={() => setStudyMode('exam')}
                  className={`px-6 py-3 text-lg font-semibold transition-colors duration-200 ${studyMode === 'exam' ? 'text-cyan-400 border-b-2 border-cyan-400' : 'text-gray-400 hover:text-white'}`}
                >
                  Practice Exam
                </button>
                <button
                  onClick={() => setStudyMode('chat')}
                  className={`px-6 py-3 text-lg font-semibold transition-colors duration-200 ${studyMode === 'chat' ? 'text-cyan-400 border-b-2 border-cyan-400' : 'text-gray-400 hover:text-white'}`}
                >
                  Chat
                </button>
              </div>

              {studyMode === 'flashcards' && <FlashcardViewer flashcards={materials.flashcards} />}
              {studyMode === 'exam' && <PracticeExam questions={materials.examQuestions} />}
              {studyMode === 'summary' && <SummaryViewer summary={materials.summary} />}
              {studyMode === 'chat' && (
                <ChatInterface
                  history={currentHistory}
                  onSendMessage={handleSendMessage}
                  isResponding={isChatResponding}
                />
              )}
            </div>
          );
        }
        return null;

      case 'detail':
        if (currentProject) {
          return (
            <ProjectDetail
              project={currentProject}
              documents={projectDocuments}
              onAddFile={handleAddFileToProject}
              onDeleteFile={handleDeleteFile}
              onGenerate={handleGenerateMaterials}
              onBack={handleBackToProjects}
              onViewMaterials={() => setCurrentView('study')}
              isGenerating={isGenerating}
              generationMessage={loadingMessage}
              isLoadingDocuments={isProjectLoading}
              hasStudyMaterials={hasStudyMaterials}
            />
          );
        }
        return null;

      case 'list':
      default:
        return (
          <ProjectList
            projects={projects}
            onCreateProject={handleCreateProject}
            onSelectProject={handleSelectProject}
            onDeleteProject={handleDeleteProject}
          />
        );
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white p-4 sm:p-8 flex flex-col">
      <header className="text-center mb-12">
        <div className="flex flex-col items-center justify-center gap-3 sm:flex-row sm:gap-4">
          <Logo />
          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight text-white leading-tight">
            <span className="block bg-gradient-to-r from-white to-cyan-400 text-transparent bg-clip-text pb-1">
              Study Buddy AI
            </span>
          </h1>
        </div>
        <p className="mt-4 max-w-2xl mx-auto text-lg text-gray-400">
          Organize your study materials into projects. Generate unified flashcards and exams from all your notes.
        </p>
      </header>
      <main className="flex-grow flex flex-col items-center justify-center">
        {renderContent()}
      </main>

      <footer className="text-center text-gray-500 mt-16 pb-4">
        <p>Developed with ❤️ by Sven Pfiffner - <a href="https://github.com/SvenPfiffner/StudyBuddy" target="_blank" rel="noopener noreferrer" className="hover:text-cyan-400 transition-colors">GitHub</a></p>
      </footer>

      {error && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50">
          <div className="text-center bg-gray-800 border border-red-700 p-6 rounded-lg max-w-md mx-auto shadow-2xl">
            <p className="font-bold text-red-300 text-lg">An Error Occurred</p>
            <p className="text-red-400 mt-2 mb-4">{error}</p>
            <button
              onClick={() => setError(null)}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default App;
