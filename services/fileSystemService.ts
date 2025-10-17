import type { Project, Flashcard, ExamQuestion } from '../types';

// Note: This service has been refactored to use localStorage instead of a file system API
// to ensure compatibility across all browser environments and fix initialization errors.
const PROJECTS_KEY = 'study-buddy-projects';

/**
 * Helper to read all projects from localStorage.
 */
const getProjects = (): Project[] => {
    try {
        const rawData = localStorage.getItem(PROJECTS_KEY);
        if (!rawData) return [];
        const projects = JSON.parse(rawData) as Project[];
        // Basic validation and data migration (e.g., ensuring files array exists)
        if (Array.isArray(projects)) {
            return projects.map(p => ({
                ...p,
                files: p.files || [],
            }));
        }
        return [];
    } catch (error) {
        console.error("Failed to load or parse projects from localStorage", error);
        return [];
    }
};

/**
 * Helper to write all projects to localStorage.
 */
const saveProjects = (projects: Project[]): void => {
    try {
        // Fix: Corrected typo from PROJECT_KEY to PROJECTS_KEY
        localStorage.setItem(PROJECTS_KEY, JSON.stringify(projects));
    } catch (error) {
        console.error("Failed to save projects to localStorage", error);
    }
};


/**
 * Loads all projects from localStorage.
 * @returns A promise that resolves to an array of Project objects.
 */
export const loadProjects = async (): Promise<Project[]> => {
    // Functions are async to maintain the same interface, making the change seamless for App.tsx.
    return Promise.resolve(getProjects());
};

/**
 * Creates a new project and saves it to localStorage.
 * @param name The name of the new project.
 * @returns The newly created Project object.
 */
export const createProject = async (name: string): Promise<Project> => {
    const projects = getProjects();
    const newProject: Project = { id: Date.now().toString(), name, files: [] };
    saveProjects([...projects, newProject]);
    return Promise.resolve(newProject);
};

/**
 * Deletes a project from localStorage.
 * @param id The ID of the project to delete.
 */
export const deleteProject = async (id: string): Promise<void> => {
    const projects = getProjects();
    saveProjects(projects.filter(p => p.id !== id));
    return Promise.resolve();
};

/**
 * Internal function to clear generated materials from a project object.
 */
const clearGeneratedData = (project: Project): Project => {
    const { flashcards, examQuestions, summary, history, ...rest } = project;
    return rest;
};

/**
 * Adds a file to a project and updates localStorage.
 * @param projectId The ID of the project.
 * @param fileName The name of the file to add.
 * @param content The content of the file.
 */
export const addFileToProject = async (projectId: string, fileName: string, content: string): Promise<void> => {
    const projects = getProjects();
    const updatedProjects = projects.map(p => {
        if (p.id === projectId) {
            // Add the new file and clear any old generated data
            const updatedProject = {
                ...p,
                files: [...p.files, { name: fileName, content }]
            };
            return clearGeneratedData(updatedProject);
        }
        return p;
    });
    saveProjects(updatedProjects);
    return Promise.resolve();
};

/**
 * Deletes a file from a project and updates localStorage.
 * @param projectId The ID of the project.
 * @param fileName The name of the file to delete.
 */
export const deleteFileFromProject = async (projectId: string, fileName:string): Promise<void> => {
    const projects = getProjects();
    const updatedProjects = projects.map(p => {
        if (p.id === projectId) {
            // Remove the file and clear any old generated data
            const updatedProject = {
                ...p,
                files: p.files.filter(f => f.name !== fileName)
            };
            return clearGeneratedData(updatedProject);
        }
        return p;
    });
    saveProjects(updatedProjects);
    return Promise.resolve();
};

/**
 * Saves generated study materials to a project in localStorage.
 * @param projectId The ID of the project.
 * @param materials An object containing the flashcards, exam questions, and summary.
 */
export const saveGeneratedMaterials = async (
    projectId: string, 
    materials: { flashcards: Flashcard[], examQuestions: ExamQuestion[], summary: string }
): Promise<void> => {
    const projects = getProjects();
    const updatedProjects = projects.map(p => {
        if (p.id === projectId) {
            return { ...p, ...materials };
        }
        return p;
    });
    saveProjects(updatedProjects);
    return Promise.resolve();
};

/**
 * Saves a project to localStorage. Used for updating history.
 * @param projectToSave The entire project object to save.
 */
export const saveProject = async (projectToSave: Project): Promise<void> => {
    const projects = getProjects();
    const updatedProjects = projects.map(p => (p.id === projectToSave.id ? projectToSave : p));
    saveProjects(updatedProjects);
    return Promise.resolve();
};