#!/usr/bin/env python3
"""
Quick test script to verify structured output generation works correctly.
Run this from the backend directory: python ../test_structured_output.py
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from backend.service import StudyBuddyService

# Sample study material
SAMPLE_MATERIAL = """
Photosynthesis is the process by which plants convert light energy into chemical energy.
It occurs in the chloroplasts and involves two main stages:

1. Light-dependent reactions: These occur in the thylakoid membranes and produce ATP and NADPH.
2. Light-independent reactions (Calvin cycle): These occur in the stroma and use ATP and NADPH to fix CO2 into glucose.

The overall equation is: 6CO2 + 6H2O + light energy → C6H12O6 + 6O2

Key factors affecting photosynthesis:
- Light intensity: Higher light increases the rate up to a saturation point
- CO2 concentration: More CO2 increases the rate until other factors become limiting
- Temperature: Affects enzyme activity; optimal range is 25-35°C
"""

def test_flashcards():
    print("=" * 70)
    print("Testing Flashcard Generation")
    print("=" * 70)
    
    service = StudyBuddyService()
    
    try:
        flashcards = service.generate_flashcards(SAMPLE_MATERIAL)
        print(f"✅ Successfully generated {len(flashcards)} flashcards\n")
        
        for i, card in enumerate(flashcards, 1):
            print(f"Flashcard {i}:")
            print(f"  Q: {card.question}")
            print(f"  A: {card.answer}")
            print()
        
        return True
    except Exception as e:
        print(f"❌ Flashcard generation failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False

def test_exam():
    print("=" * 70)
    print("Testing Practice Exam Generation")
    print("=" * 70)
    
    service = StudyBuddyService()
    
    try:
        questions = service.generate_practice_exam(SAMPLE_MATERIAL)
        print(f"✅ Successfully generated {len(questions)} exam questions\n")
        
        for i, q in enumerate(questions, 1):
            print(f"Question {i}: {q.question}")
            print(f"  Options:")
            for j, opt in enumerate(q.options, 1):
                marker = "✓" if opt == q.correctAnswer else " "
                print(f"    {j}. [{marker}] {opt}")
            print(f"  Correct: {q.correctAnswer}")
            print()
        
        # Validate all questions
        all_valid = True
        for i, q in enumerate(questions, 1):
            if len(q.options) != 4:
                print(f"❌ Question {i} has {len(q.options)} options instead of 4")
                all_valid = False
            if q.correctAnswer not in q.options:
                print(f"❌ Question {i} correct answer not in options")
                all_valid = False
        
        if all_valid:
            print("✅ All questions validated successfully")
        
        return all_valid
    except Exception as e:
        print(f"❌ Exam generation failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\nStarting structured output tests...")
    print("This may take a minute as the model loads...\n")
    
    flashcard_ok = test_flashcards()
    print()
    exam_ok = test_exam()
    
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    print(f"Flashcards: {'✅ PASS' if flashcard_ok else '❌ FAIL'}")
    print(f"Exam:       {'✅ PASS' if exam_ok else '❌ FAIL'}")
    print()
    
    sys.exit(0 if (flashcard_ok and exam_ok) else 1)
