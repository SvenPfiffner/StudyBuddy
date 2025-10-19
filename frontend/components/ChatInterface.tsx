import React, { useState, useRef, useEffect } from 'react';
import iconPng from '../icons/icon.png';
import type { ChatMessage } from '../types';
import Spinner from './Spinner';

interface ChatInterfaceProps {
    history: ChatMessage[];
    onSendMessage: (message: string) => void;
    isResponding: boolean;
}

const SendIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" viewBox="0 0 20 20" fill="currentColor">
        <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
    </svg>
);

const ChatInterface: React.FC<ChatInterfaceProps> = ({ history, onSendMessage, isResponding }) => {
    const [input, setInput] = useState('');
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [history, isResponding]);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (input.trim() && !isResponding) {
            onSendMessage(input.trim());
            setInput('');
        }
    };

    return (
        <div className="w-full max-w-3xl mx-auto flex flex-col h-[70vh] bg-gray-800 border border-gray-700 rounded-xl">
            <div className="flex-1 p-6 overflow-y-auto">
                <div className="space-y-6">
                    {(history.length === 0) && (
                        <div className="text-center text-gray-400 p-8">
                            <p className="text-lg">Start the conversation!</p>
                            <p>Ask me anything about the content in your project files.</p>
                        </div>
                    )}
                    {history.map((message, index) => (
                        <div key={index} className={`flex items-start gap-4 ${message.role === 'user' ? 'justify-end' : ''}`}>
                            {message.role === 'model' && (
                                <div className="w-8 h-8 rounded-full bg-cyan-900/50 flex items-center justify-center flex-shrink-0 overflow-hidden">
                                    <img src={iconPng} alt="AI" className="w-5 h-5 object-contain" />
                                </div>
                            )}
                            <div className={`p-4 rounded-2xl max-w-lg ${message.role === 'user' ? 'bg-cyan-600 text-white rounded-br-none' : 'bg-gray-700 text-gray-200 rounded-bl-none'}`}>
                                <p className="whitespace-pre-wrap">{message.parts[0].text}</p>
                            </div>
                        </div>
                    ))}
                    {isResponding && (
                         <div className="flex items-start gap-4">
                            <div className="w-8 h-8 rounded-full bg-cyan-900/50 flex items-center justify-center flex-shrink-0">
                                <Spinner />
                            </div>
                            <div className="p-4 rounded-2xl max-w-lg bg-gray-700 text-gray-400 italic rounded-bl-none">
                                AI is typing...
                            </div>
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </div>
            </div>
            <div className="p-4 border-t border-gray-700">
                <form onSubmit={handleSubmit} className="flex items-center gap-4">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Ask a question about your documents..."
                        disabled={isResponding}
                        className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                    />
                    <button
                        type="submit"
                        disabled={!input.trim() || isResponding}
                        className="p-3 bg-cyan-600 text-white rounded-lg hover:bg-cyan-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        aria-label="Send message"
                    >
                        <SendIcon />
                    </button>
                </form>
            </div>
        </div>
    );
};

export default ChatInterface;
