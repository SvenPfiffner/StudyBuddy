
import React, { useState } from 'react';
import type { Flashcard } from '../types';

interface FlashcardViewerProps {
  flashcards: Flashcard[];
}

const ChevronLeftIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
);

const ChevronRightIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
);

const FlashcardViewer: React.FC<FlashcardViewerProps> = ({ flashcards }) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);

  const goToPrevious = () => {
    setIsFlipped(false);
    setTimeout(() => {
        const isFirstCard = currentIndex === 0;
        const newIndex = isFirstCard ? flashcards.length - 1 : currentIndex - 1;
        setCurrentIndex(newIndex);
    }, 150);
  };

  const goToNext = () => {
    setIsFlipped(false);
    setTimeout(() => {
        const isLastCard = currentIndex === flashcards.length - 1;
        const newIndex = isLastCard ? 0 : currentIndex + 1;
        setCurrentIndex(newIndex);
    }, 150);
  };

  if (!flashcards || flashcards.length === 0) {
    return <p>No flashcards available.</p>;
  }

  const currentCard = flashcards[currentIndex];

  return (
    <div className="flex flex-col items-center w-full max-w-2xl mx-auto">
        <div className="w-full h-80" style={{ perspective: '1000px' }}>
             <div
                className="relative w-full h-full text-center rounded-2xl shadow-lg cursor-pointer bg-gray-800 border border-gray-700 overflow-hidden"
                onClick={() => setIsFlipped(!isFlipped)}
            >
                <div
                    className="absolute inset-0 w-full h-full transition-transform duration-500"
                    style={{ transformStyle: 'preserve-3d', transform: isFlipped ? 'rotateY(180deg)' : 'rotateY(0deg)' }}
                >
                    <div
                        className="absolute inset-0 w-full h-full p-6 flex items-center justify-center bg-gray-900"
                        style={{ backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden', transform: 'rotateY(0deg)' }}
                    >
                        <div className="space-y-3 text-left sm:text-center">
                            <p className="text-gray-400 text-sm">Question</p>
                            <p className="text-2xl font-semibold text-white">{currentCard.question}</p>
                        </div>
                    </div>
                    <div
                        className="absolute inset-0 w-full h-full p-6 flex items-center justify-center bg-gradient-to-br from-cyan-900 to-gray-900"
                        style={{ backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden', transform: 'rotateY(180deg)' }}
                    >
                        <div className="space-y-3 text-left sm:text-center">
                            <p className="text-cyan-300 text-sm">Answer</p>
                            <p className="text-xl font-medium text-white">{currentCard.answer}</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
      
        <div className="flex items-center justify-between w-full mt-6">
            <button
                onClick={goToPrevious}
                className="p-3 rounded-full bg-gray-700 hover:bg-cyan-500 text-white transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
                <ChevronLeftIcon />
            </button>
            <p className="text-lg font-medium text-gray-300">
                {currentIndex + 1} / {flashcards.length}
            </p>
            <button
                onClick={goToNext}
                className="p-3 rounded-full bg-gray-700 hover:bg-cyan-500 text-white transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
                <ChevronRightIcon />
            </button>
        </div>
    </div>
  );
};

export default FlashcardViewer;
