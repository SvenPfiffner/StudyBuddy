
import React from 'react';
import type { DocumentMetadata, ProjectSummary } from '../types';
import FileUpload from './FileUpload';
import Spinner from './Spinner';

interface ProjectDetailProps {
  project: ProjectSummary;
  documents: DocumentMetadata[];
  onAddFile: (fileName: string, content: string) => Promise<void> | void;
  onDeleteFile: (documentId: number) => Promise<void> | void;
  onGenerate: () => void;
  onBack: () => void;
  onViewMaterials: () => void;
  isGenerating: boolean;
  generationMessage: string | null;
  isLoadingDocuments: boolean;
  hasStudyMaterials: boolean;
}

interface FileListItemProps {
    name: string;
    onDelete: () => void;
}

const TrashIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm4 0a1 1 0 012 0v6a1 1 0 11-2 0V8z" clipRule="evenodd" />
    </svg>
);

const FileListItem: React.FC<FileListItemProps> = ({ name, onDelete }) => (
    <div className="bg-gray-700 p-3 rounded-lg flex items-center justify-between group">
        <div className="flex items-center truncate min-w-0">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-3 text-gray-400 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z" clipRule="evenodd" />
            </svg>
            <span className="text-gray-200 truncate">{name}</span>
        </div>
        <button 
            onClick={onDelete} 
            className="p-1 -m-1 text-gray-500 hover:text-red-500 transition-colors duration-200 rounded-full hover:bg-gray-800"
            aria-label={`Delete file ${name}`}
        >
            <TrashIcon/>
        </button>
    </div>
);


const ProjectDetail: React.FC<ProjectDetailProps> = ({
  project,
  documents,
  onAddFile,
  onDeleteFile,
  onGenerate,
  onBack,
  onViewMaterials,
  isGenerating,
  generationMessage,
  isLoadingDocuments,
  hasStudyMaterials,
}) => {
  
  return (
    <div className="w-full max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <button onClick={onBack} className="text-sm text-cyan-400 hover:underline mb-2">&larr; Back to Projects</button>
          <h2 className="text-3xl font-bold text-white">{project.name}</h2>
        </div>
        <div className="flex items-center gap-4">
          {hasStudyMaterials && !isGenerating && (
             <button
                onClick={onViewMaterials}
                className="px-6 py-3 border border-gray-600 hover:bg-gray-700 text-gray-300 font-semibold rounded-lg transition-colors"
             >
                View Study Materials
            </button>
          )}
          <button
              onClick={onGenerate}
              disabled={documents.length === 0 || isGenerating}
              className="flex items-center justify-center px-6 py-3 bg-cyan-600 hover:bg-cyan-700 text-white font-semibold rounded-lg shadow-md transition-colors duration-300 disabled:opacity-50 disabled:cursor-not-allowed min-w-[220px]"
          >
              {isGenerating ? (
                <>
                    <Spinner />
                    <span className="ml-3">{generationMessage || 'Generating...'}</span>
                </>
              ) : (hasMaterials ? 'Regenerate Materials' : 'Generate Study Materials')}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div>
          <h3 className="text-xl font-semibold text-white mb-4">Project Files ({documents.length})</h3>
          <div className="space-y-3 max-h-96 overflow-y-auto pr-2">
            {isLoadingDocuments ? (
              <div className="flex items-center justify-center py-10">
                <Spinner />
              </div>
            ) : documents.length > 0 ? (
              documents.map((file) => (
                <FileListItem key={file.id} name={file.title} onDelete={() => onDeleteFile(file.id)} />
              ))
            ) : (
              <div className="text-center py-10 px-6 bg-gray-800/50 rounded-lg border border-dashed border-gray-600">
                  <p className="text-gray-400">This project is empty.</p>
                  <p className="text-gray-500 mt-1">Upload a file to get started!</p>
              </div>
            )}
          </div>
        </div>

        <div>
           <h3 className="text-xl font-semibold text-white mb-4">Add New File</h3>
           <FileUpload onFileUpload={onAddFile} isLoading={isGenerating || isLoadingDocuments} />
        </div>
      </div>
    </div>
  );
};

export default ProjectDetail;
