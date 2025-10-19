import React, { useState, useCallback, useEffect } from 'react';
import ProjectList from './components/ProjectList';
import ProjectDetail from './components/ProjectDetail';
import FlashcardViewer from './components/FlashcardViewer';
import PracticeExam from './components/PracticeExam';
import SummaryViewer from './components/SummaryViewer';
import ChatInterface from './components/ChatInterface';
import Spinner from './components/Spinner';
import { generateFlashcards, generatePracticeExam, generateSummary, continueChat } from './services/geminiService';
import {
  loadProjects,
  createProject,
  deleteProject,
  addFileToProject,
  deleteFileFromProject,
  saveGeneratedMaterials,
  saveProject
} from './services/fileSystemService';
import type { Project, ChatMessage } from './types';
import type { StudyMode } from './types';

import iconPng from './icons/icon.png';

const Logo = () => (
  <img src={iconPng} alt="Study Buddy icon" className="w-10 h-10 object-contain" />
);

type View = 'list' | 'detail' | 'study';

const App: React.FC = () => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [currentProjectId, setCurrentProjectId] = useState<string | null>(null);
  const [currentView, setCurrentView] = useState<View>('list');
  const [studyMode, setStudyMode] = useState<StudyMode>('summary');
  const [isLoading, setIsLoading] = useState(true); // For project loading and material generation
  const [isChatResponding, setIsChatResponding] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Load projects from storage on initial render.
  useEffect(() => {
    const initializeApp = async () => {
      try {
        const loadedProjects = await loadProjects();
        setProjects(loadedProjects);
      } catch (e: any) {
        console.error("Initialization failed:", e);
        setError(e.message || "Could not load your projects. Your browser's storage might be disabled or full.");
      } finally {
        setIsLoading(false);
      }
    };

    initializeApp();
  }, []);
  
  // Effect to handle view transitions safely if data is missing
  useEffect(() => {
    const currentProject = projects.find(p => p.id === currentProjectId);
    if (currentView === 'detail' && !currentProject) {
        setCurrentView('list');
    }
    if (currentView === 'study') {
        const hasMaterials = currentProject?.flashcards && currentProject?.examQuestions && currentProject?.summary;
        if (!hasMaterials) {
            setCurrentView('detail');
        }
    }
  }, [currentView, currentProjectId, projects]);

  const handleCreateProject = useCallback(async (name: string) => {
    try {
      const newProject = await createProject(name);
      setProjects(prev => [...prev, newProject]);
    } catch (e) {
      console.error("Error creating project:", e);
      setError("Failed to create the project.");
    }
  }, []);

  const handleDeleteProject = useCallback(async (idToDelete: string) => {
    if (window.confirm("Are you sure you want to delete this project and all its files? This action cannot be undone.")) {
      try {
        await deleteProject(idToDelete);
        setProjects(prev => prev.filter(p => p.id !== idToDelete));
        if (currentProjectId === idToDelete) {
          setCurrentProjectId(null);
          setCurrentView('list');
        }
      } catch (e) {
        console.error("Error deleting project:", e);
        setError("Failed to delete the project.");
      }
    }
  }, [currentProjectId]);

  const handleSelectProject = useCallback((id: string) => {
    setCurrentProjectId(id);
    setCurrentView('detail');
    setError(null);
  }, []);

  const handleBackToProjects = useCallback(() => {
    setCurrentProjectId(null);
    setCurrentView('list');
  }, []);

  const handleAddFileToProject = useCallback(async (fileName: string, content: string) => {
    if (!currentProjectId) return;
    const currentProject = projects.find(p => p.id === currentProjectId);
    if (currentProject?.files.some(f => f.name === fileName)) {
      alert(`A file named "${fileName}" already exists in this project.`);
      return;
    }
    
    try {
      await addFileToProject(currentProjectId, fileName, content);
      setProjects(prev => prev.map(p => {
        if (p.id === currentProjectId) {
          const updatedProject = { ...p, files: [...p.files, { name: fileName, content }] };
          // Clear all generated data since context has changed
          delete updatedProject.flashcards;
          delete updatedProject.examQuestions;
          delete updatedProject.summary;
          delete updatedProject.history;
          return updatedProject;
        }
        return p;
      }));
    } catch (e) {
      console.error("Error adding file:", e);
      setError("Failed to add the file to your project.");
    }
  }, [currentProjectId, projects]);

  const handleDeleteFile = useCallback(async (fileName: string) => {
    if (!currentProjectId) return;
    if (window.confirm(`Are you sure you want to delete the file "${fileName}"?`)) {
      try {
        await deleteFileFromProject(currentProjectId, fileName);
        setProjects(prev => prev.map(p => {
          if (p.id === currentProjectId) {
            const updatedProject = { ...p, files: p.files.filter(f => f.name !== fileName) };
            // Clear all generated data since context has changed
            delete updatedProject.flashcards;
            delete updatedProject.examQuestions;
            delete updatedProject.summary;
            delete updatedProject.history;
            return updatedProject;
          }
          return p;
        }));
      } catch (e) {
        console.error("Error deleting file:", e);
        setError("Failed to delete the file.");
      }
    }
  }, [currentProjectId, projects]);

  const handleGenerateMaterials = useCallback(async () => {
    if (!currentProjectId) return;
    const currentProject = projects.find(p => p.id === currentProjectId);
    if (!currentProject || currentProject.files.length === 0) return;

    setIsLoading(true);
    setLoadingMessage("Waking up the AI study buddy...");
    setError(null);

    const combinedContent = currentProject.files.map(f => `--- Start of file: ${f.name} ---\n${f.content}\n--- End of file: ${f.name} ---`).join('\n\n');

    try {
      setLoadingMessage("Crafting some killer flashcards...");
      const fCards = await generateFlashcards(combinedContent);
      setLoadingMessage("Devising a delightfully tricky exam...");
      const eQuestions = await generatePracticeExam(combinedContent);
      const summary = await generateSummary(combinedContent, setLoadingMessage);
      setLoadingMessage("Assembling your study package...");
      
      const materials = { flashcards: fCards, examQuestions: eQuestions, summary };
      await saveGeneratedMaterials(currentProjectId, materials);
      
      setProjects(prev => prev.map(p => p.id === currentProjectId ? { ...p, ...materials } : p));
      setStudyMode('summary');
      setCurrentView('study');
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred.');
    } finally {
      setIsLoading(false);
      setLoadingMessage(null);
    }
  }, [currentProjectId, projects]);

  const handleSendMessage = useCallback(async (message: string) => {
    if (!currentProjectId) return;
    const currentProject = projects.find(p => p.id === currentProjectId);
    if (!currentProject) return;

    setIsChatResponding(true);

    const userMessage: ChatMessage = { role: 'user', parts: [{ text: message }] };
    const currentHistory = currentProject.history || [];
    const updatedHistory = [...currentHistory, userMessage];
    
    // Optimistically update the UI with the user's message
    const updatedProject = { ...currentProject, history: updatedHistory };
    setProjects(prev => prev.map(p => p.id === currentProjectId ? updatedProject : p));

    try {
        const systemInstruction = `You are a helpful tutor. The user has provided the following study material, split into one or more files. Answer their questions based ONLY on this content. If the answer cannot be found in the content, say that you don't have enough information from the provided documents.
        ---
        CONTENT START
        ${currentProject.files.map(f => `--- Start of file: ${f.name} ---\n${f.content}\n--- End of file: ${f.name} ---`).join('\n\n')}
        CONTENT END
        ---`;

        const aiResponseText = await continueChat(currentHistory, systemInstruction, message);
        const aiMessage: ChatMessage = { role: 'model', parts: [{ text: aiResponseText }] };
        
        const finalProject = { ...updatedProject, history: [...updatedHistory, aiMessage] };
        setProjects(prev => prev.map(p => p.id === currentProjectId ? finalProject : p));
        await saveProject(finalProject);

    } catch(err: any) {
        setError(err.message || 'An error occurred while chatting.');
        // Revert optimistic update on error
        setProjects(prev => prev.map(p => p.id === currentProjectId ? { ...currentProject, history: currentHistory } : p));
    } finally {
        setIsChatResponding(false);
    }
  }, [currentProjectId, projects]);

  const currentProject = projects.find(p => p.id === currentProjectId);

  const renderContent = () => {
    if (isLoading && !loadingMessage) {
        return (
            <div className="flex flex-col items-center justify-center text-center">
                <Spinner />
                <p className="mt-4 text-gray-400">Loading your projects...</p>
            </div>
        )
    }

    switch (currentView) {
        case 'study':
            if (currentProject?.flashcards && currentProject?.examQuestions && currentProject?.summary) {
              return (
                <div className="w-full">
                  <div className="flex items-center justify-between mb-8">
                    <div>
                      <h2 className="text-2xl font-bold text-white">{currentProject.name}</h2>
                      <p className="text-md text-gray-400">Generated from {currentProject.files.length} file(s)</p>
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
        
                  {studyMode === 'flashcards' && <FlashcardViewer flashcards={currentProject.flashcards} />}
                  {studyMode === 'exam' && <PracticeExam questions={currentProject.examQuestions} />}
                  {studyMode === 'summary' && <SummaryViewer summary={currentProject.summary} />}
                  {studyMode === 'chat' && <ChatInterface history={currentProject.history || []} onSendMessage={handleSendMessage} isResponding={isChatResponding} />}
                </div>
              );
            }
            return null;

        case 'detail':
            if (currentProject) {
                return <ProjectDetail 
                    project={currentProject}
                    onAddFile={handleAddFileToProject}
                    onDeleteFile={handleDeleteFile}
                    onGenerate={handleGenerateMaterials}
                    onBack={handleBackToProjects}
                    onViewMaterials={() => setCurrentView('study')}
                    isGenerating={isLoading}
                    generationMessage={loadingMessage}
                />
            }
            return null;

        case 'list':
        default:
            return <ProjectList 
                projects={projects}
                onCreateProject={handleCreateProject}
                onSelectProject={handleSelectProject}
                onDeleteProject={handleDeleteProject}
            />
    }
  }

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