import React, { useState } from 'react';
import type { ProjectSummary } from '../types';

interface ProjectListProps {
  projects: ProjectSummary[];
  onSelectProject: (id: number) => void;
  onCreateProject: (name: string) => Promise<void> | void;
  onDeleteProject: (id: number) => Promise<void> | void;
}

const TrashIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm4 0a1 1 0 012 0v6a1 1 0 11-2 0V8z" clipRule="evenodd" />
    </svg>
);

const ProjectList: React.FC<ProjectListProps> = ({ projects, onSelectProject, onCreateProject, onDeleteProject }) => {
  const [newProjectName, setNewProjectName] = useState('');

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (newProjectName.trim()) {
      onCreateProject(newProjectName.trim());
      setNewProjectName('');
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto">
      <h2 className="text-2xl font-bold text-white mb-6 text-center">Your Projects</h2>
      
      <form onSubmit={handleCreate} className="flex gap-4 mb-8">
        <input
          type="text"
          value={newProjectName}
          onChange={(e) => setNewProjectName(e.target.value)}
          placeholder="Enter new project name"
          className="flex-grow bg-gray-800 border border-gray-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-cyan-500"
        />
        <button
          type="submit"
          className="px-6 py-2 bg-cyan-600 hover:bg-cyan-700 text-white font-semibold rounded-lg shadow-md transition-colors duration-300 disabled:opacity-50"
          disabled={!newProjectName.trim()}
        >
          Create
        </button>
      </form>

      <div className="space-y-4">
        {projects.length > 0 ? (
          projects.map(project => (
            <div
              key={project.id}
              onClick={() => onSelectProject(project.id)}
              className="bg-gray-800 border border-gray-700 rounded-lg p-4 cursor-pointer hover:border-cyan-500 hover:bg-gray-700 transition-all duration-200 flex justify-between items-center"
            >
              <div>
                <h3 className="text-xl font-semibold text-white">{project.name}</h3>
                <span className="text-sm text-gray-400">{project.documentCount} file(s)</span>
              </div>
              <button
                onClick={(e) => {
                    e.stopPropagation();
                    onDeleteProject(project.id);
                }}
                className="p-2 -m-2 text-gray-500 hover:text-red-500 transition-colors duration-200 rounded-full hover:bg-gray-900/50"
                aria-label={`Delete project ${project.name}`}
              >
                <TrashIcon />
              </button>
            </div>
          ))
        ) : (
          <div className="text-center py-10 px-6 bg-gray-800/50 rounded-lg border border-dashed border-gray-600">
            <p className="text-gray-400">You don't have any projects yet.</p>
            <p className="text-gray-500 mt-1">Create one above to get started!</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default ProjectList;