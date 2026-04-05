import whisper
import json

def transcribe_answer(audio_file: str) -> dict:
    print("Loading model...")
    model = whisper.load_model("base")
    
    print("Transcribing...")
    result = model.transcribe(audio_file, verbose=False)
    
    text = result["text"].strip()
    words = text.split()
    duration_seconds = result["segments"][-1]["end"] if result["segments"] else 0
    duration_minutes = duration_seconds / 60
    words_per_minute = len(words) / duration_minutes if duration_minutes > 0 else 0
    
    output = {
        "transcript": text,
        "word_count": len(words),
        "duration_seconds": round(duration_seconds, 1),
        "words_per_minute": round(words_per_minute, 1),
        "segments": result["segments"]
    }
    
    return output
def analyze_fillers(transcript: str) -> dict:
    filler_words = ["um", "uh", "like", "basically", "literally", 
                    "you know", "kind of", "sort of", "right", "actually"]
    
    transcript_lower = transcript.lower()
    found = {}
    
    for filler in filler_words:
        count = transcript_lower.split().count(filler)
        if count > 0:
            found[filler] = count
    
    return found

if __name__ == "__main__":
    data = transcribe_answer("vasudha.mp3")
    
    print("\n=== TRANSCRIPT ===")
    print(data["transcript"])
    print(f"\n=== STATS ===")
    print(f"Words: {data['word_count']}")
    print(f"Duration: {data['duration_seconds']}s")
    print(f"Pace: {data['words_per_minute']} words/min")
    print(f"\n(Ideal interview pace: 130-150 wpm)")

    fillers = analyze_fillers(data["transcript"])
    print(f"\n=== FILLER WORDS ===")
    if fillers:
        for word, count in sorted(fillers.items(), key=lambda x: -x[1]):
            print(f"  '{word}': {count}x")
    else:
        print("  None detected — great!")
      
    with open("transcription_result.json", "w") as f:
        data["fillers"] = fillers
        json.dump(data, f, indent=2)
        
    print("\n Saved to transcription_result.json")