document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const resumeUpload = document.getElementById('resume');
    const resumeFilename = document.getElementById('resume-filename');
    const recordBtn = document.getElementById('record-btn');
    const stopBtn = document.getElementById('stop-btn');
    const timerDisplay = document.getElementById('timer');
    const recordStatus = document.getElementById('record-status');
    const recordingState = document.querySelector('.recording-state');
    const audioPreview = document.getElementById('audio-preview');
    const recordedAudio = document.getElementById('recorded-audio');
    const retakeBtn = document.getElementById('retake-btn');
    const submitBtn = document.getElementById('submit-btn');
    const loadingState = document.getElementById('loading-state');
    const resultsPanel = document.getElementById('results-panel');
    const newInterviewBtn = document.getElementById('new-interview-btn');

    // State Variables
    let mediaRecorder;
    let audioChunks = [];
    let audioBlob = null;
    let timerInterval;
    let seconds = 0;

    // Handle File Upload Display
    resumeUpload.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            resumeFilename.textContent = e.target.files[0].name;
            resumeFilename.style.color = '#fff';
            document.getElementById('resume-upload-area').style.borderColor = 'var(--primary)';
        } else {
            resumeFilename.textContent = 'Click or drag PDF to upload';
            resumeFilename.style.color = '';
            document.getElementById('resume-upload-area').style.borderColor = '';
        }
    });

    // Audio Recording Logic
    const initAudio = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                }
            };

            mediaRecorder.onstop = () => {
                clearInterval(timerInterval);
                audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                const audioUrl = URL.createObjectURL(audioBlob);
                recordedAudio.src = audioUrl;
                
                // UI Toggle
                recordingState.classList.add('hidden');
                audioPreview.classList.remove('hidden');
            };

        } catch (err) {
            console.error("Microphone access denied: ", err);
            alert("Please allow microphone access to record your answer.");
        }
    };

    const updateTimer = () => {
        seconds++;
        const mins = Math.floor(seconds / 60).toString().padStart(2, '0');
        const secs = (seconds % 60).toString().padStart(2, '0');
        timerDisplay.textContent = `${mins}:${secs}`;
    };

    recordBtn.addEventListener('click', async () => {
        if (!mediaRecorder) await initAudio();
        
        audioChunks = [];
        seconds = 0;
        timerDisplay.textContent = '00:00';
        mediaRecorder.start();
        
        recordBtn.classList.add('recording');
        recordStatus.textContent = 'Recording...';
        stopBtn.classList.remove('hidden');
        recordBtn.style.pointerEvents = 'none'; // Disable start while recording
        
        timerInterval = setInterval(updateTimer, 1000);
    });

    stopBtn.addEventListener('click', () => {
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
            recordBtn.classList.remove('recording');
            recordStatus.textContent = 'Ready to Record';
            stopBtn.classList.add('hidden');
            recordBtn.style.pointerEvents = 'auto'; // Re-enable
        }
    });

    retakeBtn.addEventListener('click', () => {
        audioBlob = null;
        recordedAudio.src = '';
        audioPreview.classList.add('hidden');
        recordingState.classList.remove('hidden');
        seconds = 0;
        timerDisplay.textContent = '00:00';
    });

    // Form Submission & API Call
    submitBtn.addEventListener('click', async () => {
        const companyInput = document.getElementById('company').value;
        const questionInput = document.getElementById('question').value;
        const resumeFile = resumeUpload.files[0];

        if (!resumeFile) {
            alert("Please upload your resume PDF first.");
            document.getElementById('setup-form').scrollIntoView({ behavior: 'smooth' });
            return;
        }

        if (!audioBlob) {
            alert("Please record an answer.");
            return;
        }

        // Prepare FormData
        const formData = new FormData();
        formData.append('resume', resumeFile);
        formData.append('audio', audioBlob, 'recording.webm');
        formData.append('target_company', companyInput);
        formData.append('question', questionInput);

        // UI Changes: Show Loading
        audioPreview.classList.add('hidden');
        document.querySelector('.config-panel').classList.add('hidden');
        loadingState.classList.remove('hidden');

        try {
            const response = await fetch('/api/evaluate', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }

            const data = await response.json();
            
            if (data.success) {
                displayResults(data);
            } else {
                throw new Error(data.error || "Unknown error occurred.");
            }

        } catch (error) {
            console.error(error);
            alert("Evaluation failed: " + error.message);
            loadingState.classList.add('hidden');
            audioPreview.classList.remove('hidden');
            document.querySelector('.config-panel').classList.remove('hidden');
        }
    });

    // Display Results
    const displayResults = (data) => {
        // Hide loading, show results
        loadingState.classList.add('hidden');
        resultsPanel.classList.remove('hidden');
        
        // Populate Stats
        document.getElementById('res-duration').textContent = `${data.stats.duration_seconds}s`;
        document.getElementById('res-wpm').textContent = Math.round(data.stats.words_per_minute);
        document.getElementById('res-wordcount').textContent = data.stats.word_count;

        // Transcript
        document.getElementById('res-transcript').textContent = data.transcript;

        // Feedback
        const feedbackContainer = document.getElementById('res-feedback');
        // Simple markdown parsing for bold and headings
        let formattedFeedback = data.feedback
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/(?:\r\n|\r|\n)/g, '<br>');
            
        feedbackContainer.innerHTML = formattedFeedback;

        // Fillers
        const fillersList = document.getElementById('res-fillers');
        fillersList.innerHTML = '';
        const fillers = data.stats.fillers || {};
        
        if (Object.keys(fillers).length === 0) {
            const li = document.createElement('li');
            li.className = 'filler-tag good';
            li.textContent = 'None detected — great!';
            fillersList.appendChild(li);
        } else {
            for (const [word, count] of Object.entries(fillers)) {
                if(count > 0) {
                    const li = document.createElement('li');
                    li.className = 'filler-tag';
                    li.innerHTML = `<strong>${word}</strong>: ${count}x`;
                    fillersList.appendChild(li);
                }
            }
        }
    };

    // Reset Flow
    newInterviewBtn.addEventListener('click', () => {
        resultsPanel.classList.add('hidden');
        document.querySelector('.config-panel').classList.remove('hidden');
        recordingState.classList.remove('hidden');
        
        // Reset recording
        audioBlob = null;
        recordedAudio.src = '';
        seconds = 0;
        timerDisplay.textContent = '00:00';
    });
});
