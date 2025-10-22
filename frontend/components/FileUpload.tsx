import React, { useState, useCallback, useRef } from 'react';

interface FileUploadProps {
  onFileUpload: (content: string, fileName: string) => Promise<void> | void;
  isLoading: boolean;
}

// pdf.js is loaded from a script tag in index.html, so we declare it here to satisfy TypeScript
declare const pdfjsLib: any;

const FileIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
    </svg>
);


const FileUpload: React.FC<FileUploadProps> = ({ onFileUpload, isLoading }) => {
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(async (file: File) => {
    if (!file) return;

    if (file.type.startsWith('text/')) {
        const reader = new FileReader();
        reader.onload = (e) => {
            const content = e.target?.result as string;
            Promise.resolve(onFileUpload(content, file.name));
        };
        reader.readAsText(file);
    } else if (file.type === 'application/pdf') {
        const reader = new FileReader();
        reader.onload = async (e) => {
            const arrayBuffer = e.target?.result as ArrayBuffer;
            if (arrayBuffer) {
                try {
                    const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
                    let fullText = '';
                    const pagePromises = [];

                    for (let i = 1; i <= pdf.numPages; i++) {
                        pagePromises.push(pdf.getPage(i).then((page: any) => page.getTextContent()));
                    }

                    const pagesTextContent = await Promise.all(pagePromises);

                    pagesTextContent.forEach((textContent: any) => {
                        fullText += textContent.items.map((item: any) => item.str).join(' ') + '\n';
                    });

                    await Promise.resolve(onFileUpload(fullText.trim(), file.name));

                } catch (error) {
                    console.error("Error parsing PDF:", error);
                    alert("Failed to parse the PDF file. It might be corrupted or protected.");
                }
            }
        };
        reader.readAsArrayBuffer(file);
    } else {
        alert("Please upload a valid file (.txt, .md, .pdf).");
    }
  }, [onFileUpload]);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  }, [handleFile]);
  
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const onButtonClick = () => {
    inputRef.current?.click();
  };

  return (
    <div 
        className="w-full max-w-2xl mx-auto"
        onDragEnter={handleDrag}
    >
        <form 
            className={`p-8 border-2 border-dashed rounded-2xl transition-colors duration-300 ${dragActive ? "border-cyan-400 bg-gray-800" : "border-gray-600 hover:border-cyan-500"} `}
            onSubmit={(e) => e.preventDefault()}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
        >
            <input
                ref={inputRef}
                type="file"
                className="hidden"
                accept=".txt,.md,.text,.pdf"
                onChange={handleChange}
                disabled={isLoading}
            />
            <div className="flex flex-col items-center justify-center text-center">
                <FileIcon />
                <p className="mt-4 text-lg text-gray-300">
                  Drag & drop your script here, or
                  <button 
                    type="button"
                    onClick={onButtonClick}
                    disabled={isLoading}
                    className="font-semibold text-cyan-400 hover:text-cyan-300 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500 focus:ring-offset-gray-900 rounded-md ml-1"
                  >
                     browse
                  </button>
                </p>
                <p className="mt-1 text-sm text-gray-500">Supports .txt, .md, .pdf files</p>
            </div>
        </form>
    </div>
  );
};

export default FileUpload;