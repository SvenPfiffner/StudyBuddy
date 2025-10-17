import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';

interface SummaryViewerProps {
  summary: string;
}

const SummaryViewer: React.FC<SummaryViewerProps> = ({ summary }) => {
  // By default, react-markdown sanitizes URLs and blocks `data:` URIs.
  // We need to provide a custom transform function to explicitly allow them,
  // as our AI-generated images are embedded as base64 data URIs.
  const urlTransform = (uri: string) => {
    return uri;
  };

  return (
    <div className="w-full max-w-3xl mx-auto bg-gray-800 border border-gray-700 rounded-xl p-6 sm:p-8">
      <article className="prose prose-invert prose-cyan max-w-none">
        <ReactMarkdown 
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeRaw]}
          urlTransform={urlTransform}
        >
          {summary}
        </ReactMarkdown>
      </article>
    </div>
  );
};

export default SummaryViewer;