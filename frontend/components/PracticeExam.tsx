
import React, { useState } from 'react';
import type { ExamQuestion } from '../types';

interface PracticeExamProps {
  questions: ExamQuestion[];
}

const CheckIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
    </svg>
);

const XIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
    </svg>
);

const PracticeExam: React.FC<PracticeExamProps> = ({ questions }) => {
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [submitted, setSubmitted] = useState(false);

  const getCorrectOption = (question: ExamQuestion): string => {
    const letterToIndex: Record<string, number> = { A: 0, B: 1, C: 2, D: 3 };
    const letter = question.correctAnswer.toUpperCase();
    const index = letterToIndex[letter] ?? 0;
    return question.options[index];
  };

  const handleAnswerChange = (questionIndex: number, answer: string) => {
    setAnswers({ ...answers, [questionIndex]: answer });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
  };

  const handleReset = () => {
    setAnswers({});
    setSubmitted(false);
  }

  const score = Object.keys(answers).reduce((acc, key) => {
    const qIndex = parseInt(key, 10);
    if (getCorrectOption(questions[qIndex]) === answers[qIndex]) {
      return acc + 1;
    }
    return acc;
  }, 0);

  return (
    <div className="w-full max-w-3xl mx-auto">
      {submitted && (
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-6 mb-8 text-center">
            <h2 className="text-2xl font-bold text-white">Exam Results</h2>
            <p className="text-4xl font-bold text-cyan-400 my-3">{score} / {questions.length}</p>
            <p className="text-lg text-gray-300">You answered {Math.round((score / questions.length) * 100)}% of questions correctly.</p>
        </div>
      )}

      <form onSubmit={handleSubmit}>
        {questions.map((q, qIndex) => (
          <div key={qIndex} className="bg-gray-800 border border-gray-700 rounded-xl p-6 mb-6">
            <p className="text-lg font-semibold text-white mb-4">
              {qIndex + 1}. {q.question}
            </p>
            <div className="space-y-3">
              {q.options.map((option, oIndex) => {
                const isSelected = answers[qIndex] === option;
                const isCorrect = getCorrectOption(q) === option;
                let optionClass = "border-gray-600 hover:bg-gray-700";

                if (submitted) {
                    if(isCorrect) {
                        optionClass = "border-green-500 bg-green-900/50 text-green-300";
                    } else if (isSelected && !isCorrect) {
                        optionClass = "border-red-500 bg-red-900/50 text-red-300";
                    } else {
                        optionClass = "border-gray-700";
                    }
                }

                return (
                    <label key={oIndex} className={`flex items-center p-4 rounded-lg border-2 cursor-pointer transition-all duration-200 ${optionClass}`}>
                        <input
                        type="radio"
                        name={`question-${qIndex}`}
                        value={option}
                        checked={isSelected}
                        onChange={() => handleAnswerChange(qIndex, option)}
                        disabled={submitted}
                        className="h-4 w-4 text-cyan-500 bg-gray-700 border-gray-600 focus:ring-cyan-600 focus:ring-offset-gray-800"
                        />
                        <span className="ml-3 text-white">{option}</span>
                        {submitted && isCorrect && <CheckIcon />}
                        {submitted && isSelected && !isCorrect && <XIcon />}
                    </label>
                )
              })}
            </div>
            {submitted && answers[qIndex] !== getCorrectOption(q) && (
                <div className="mt-4 p-3 bg-green-900/30 rounded-md text-green-300">
                    Correct Answer: {getCorrectOption(q)}
                </div>
            )}
          </div>
        ))}

        {!submitted ? (
            <button
                type="submit"
                className="w-full py-3 px-6 bg-cyan-600 hover:bg-cyan-700 text-white font-semibold rounded-lg shadow-md transition-colors duration-300 disabled:opacity-50"
                disabled={Object.keys(answers).length !== questions.length}
            >
                Check Answers
            </button>
        ) : (
            <button
                type="button"
                onClick={handleReset}
                className="w-full py-3 px-6 bg-gray-600 hover:bg-gray-700 text-white font-semibold rounded-lg shadow-md transition-colors duration-300"
            >
                Try Again
            </button>
        )}
      </form>
    </div>
  );
};

export default PracticeExam;
