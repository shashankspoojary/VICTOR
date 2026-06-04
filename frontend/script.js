const state = {
    session_id: "test_session_001",
    current_image_base64: null,
    mode: "VICTOR",
    camera_stream: null,
    ttsEnabled: true,
    voiceEnabled: false,
    mediaStream: null,
    silenceTimeout: null,
    isSpeaking: false
};

const SILENCE_THRESHOLD = 15;
const SILENCE_DURATION = 1500;

let mediaRecorder = null;
let audioChunks = [];
let audioContext = null;
let analyser = null;
let monitorInterval = null;

const dom = {
    statusIndicator: document.getElementById('status-indicator'),
    statusText: document.getElementById('status-text'),
    modeBtns: document.querySelectorAll('.mode-btn'),
    chatHistory: document.getElementById('chat-history'),
    queryInput: document.getElementById('query-input'),
    imageInput: document.getElementById('image-input'),
    executeBtn: document.getElementById('execute-btn'),
    imagePreviewPane: document.getElementById('image-preview-pane'),
    imageThumbnail: document.getElementById('image-thumbnail'),
    removeImageBtn: document.getElementById('remove-image-btn'),
    cameraToggleBtn: document.getElementById('camera-toggle-btn'),
    webcamPreview: document.getElementById('webcam-preview'),
    snapshotCanvas: document.getElementById('snapshot-canvas'),
    ttsToggleBtn: document.getElementById('tts-toggle-btn'),
    voiceToggleBtn: document.getElementById('voice-toggle-btn')
};

async function checkStatus() {
    try {
        const res = await fetch('/api/status');
        if (res.ok) {
            const data = await res.json();
            dom.statusIndicator.classList.add('online');
            dom.statusText.textContent = data.message || "Online";
        } else {
            throw new Error('Non-ok response');
        }
    } catch (e) {
        dom.statusIndicator.classList.remove('online');
        dom.statusText.textContent = "Offline";
    }
}

function appendMessage(role, text) {
    const msgDiv = document.createElement('div');
    msgDiv.classList.add('message', role);
    msgDiv.textContent = text;
    dom.chatHistory.appendChild(msgDiv);
    dom.chatHistory.scrollTop = dom.chatHistory.scrollHeight;
}

dom.modeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        dom.modeBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.mode = btn.dataset.mode;
    });
});

function handleFileInput(file) {
    if (file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = (event) => {
            state.current_image_base64 = event.target.result;
            dom.imageThumbnail.src = state.current_image_base64;
            dom.imagePreviewPane.classList.remove('hidden');
        };
        reader.readAsDataURL(file);
    } else {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('session_id', state.session_id);
        fetch('/api/upload', {
            method: 'POST',
            body: formData
        }).then(res => res.json()).then(data => {
            appendMessage('system', data.response || data.message || 'Document uploaded successfully.');
        }).catch(err => {
            console.error(err);
            appendMessage('system', 'Error uploading document.');
        });
    }
}

dom.imageInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        handleFileInput(file);
    }
});

dom.removeImageBtn.addEventListener('click', () => {
    state.current_image_base64 = null;
    dom.imageThumbnail.src = '';
    dom.imagePreviewPane.classList.add('hidden');
    dom.imageInput.value = '';
});

dom.cameraToggleBtn.addEventListener('click', async () => {
    if (state.camera_stream) {
        state.camera_stream.getTracks().forEach(track => track.stop());
        state.camera_stream = null;
        dom.webcamPreview.style.display = 'none';
        dom.webcamPreview.srcObject = null;
    } else {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true });
            state.camera_stream = stream;
            dom.webcamPreview.srcObject = stream;
            dom.webcamPreview.style.display = 'block';
        } catch (err) {
            console.error("Camera access error:", err);
        }
    }
});

dom.ttsToggleBtn.addEventListener('click', () => {
    state.ttsEnabled = !state.ttsEnabled;
    dom.ttsToggleBtn.classList.toggle('active');
});

dom.voiceToggleBtn.addEventListener('click', async () => {
    state.voiceEnabled = !state.voiceEnabled;
    dom.voiceToggleBtn.classList.toggle('active');

    if (state.voiceEnabled) {
        startListeningLoop();
    } else {
        stopVoiceCapture();
    }
});

async function startListeningLoop() {
    try {
        state.mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 512;
        const microphone = audioContext.createMediaStreamSource(state.mediaStream);
        microphone.connect(analyser);

        mediaRecorder = new MediaRecorder(state.mediaStream);
        audioChunks = [];

        mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) {
                audioChunks.push(e.data);
            }
        };

        mediaRecorder.start();
        monitorVolume();
    } catch (err) {
        console.error('Error accessing microphone:', err);
        state.voiceEnabled = false;
        dom.voiceToggleBtn.classList.remove('active');
    }
}

function stopVoiceCapture() {
    if (state.silenceTimeout) {
        clearTimeout(state.silenceTimeout);
        state.silenceTimeout = null;
    }
    if (monitorInterval) {
        cancelAnimationFrame(monitorInterval);
        monitorInterval = null;
    }
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
    }
    if (state.mediaStream) {
        state.mediaStream.getTracks().forEach(track => track.stop());
        state.mediaStream = null;
    }
    if (audioContext && audioContext.state !== 'closed') {
        audioContext.close();
        audioContext = null;
    }
    state.isSpeaking = false;
}

function monitorVolume() {
    if (!analyser || !state.voiceEnabled) return;
    
    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(dataArray);
    
    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i];
    }
    const average = sum / dataArray.length;
    
    if (average > SILENCE_THRESHOLD) {
        state.isSpeaking = true;
        if (state.silenceTimeout) {
            clearTimeout(state.silenceTimeout);
            state.silenceTimeout = null;
        }
    } else {
        if (state.isSpeaking && !state.silenceTimeout) {
            state.silenceTimeout = setTimeout(() => {
                stopAndProcessAudioSegment();
            }, SILENCE_DURATION);
        }
    }
    
    monitorInterval = requestAnimationFrame(monitorVolume);
}

function stopAndProcessAudioSegment() {
    state.isSpeaking = false;
    if (state.silenceTimeout) {
        clearTimeout(state.silenceTimeout);
        state.silenceTimeout = null;
    }
    if (monitorInterval) {
        cancelAnimationFrame(monitorInterval);
        monitorInterval = null;
    }

    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            audioChunks = [];
            
            if (state.mediaStream) {
                state.mediaStream.getTracks().forEach(track => track.stop());
                state.mediaStream = null;
            }
            if (audioContext && audioContext.state !== 'closed') {
                audioContext.close();
                audioContext = null;
            }

            const formData = new FormData();
            formData.append('file', audioBlob, 'audio.wav');
            
            try {
                const res = await fetch('/api/transcribe', {
                    method: 'POST',
                    body: formData
                });
                if (res.ok) {
                    const data = await res.json();
                    if (data.transcript && data.transcript.trim() !== '') {
                        dom.queryInput.value = data.transcript;
                        executeCommand();
                    } else {
                        if (state.voiceEnabled) startListeningLoop();
                    }
                } else {
                    console.error('Transcription failed:', await res.text());
                    if (state.voiceEnabled) startListeningLoop();
                }
            } catch (err) {
                console.error('Error sending audio for transcription:', err);
                if (state.voiceEnabled) startListeningLoop();
            }
        };
        mediaRecorder.stop();
    }
}

async function executeCommand() {
    let text = dom.queryInput.value.trim();

    if (!text && !state.current_image_base64 && !state.camera_stream) return;
    
    let uiText = text;
    if (state.camera_stream) {
        const video = dom.webcamPreview;
        const canvas = dom.snapshotCanvas;
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        state.current_image_base64 = canvas.toDataURL('image/jpeg');
        uiText = text || "[Camera Snapshot]";
        text = "TTCAMTOKENTT " + text;
        
        state.camera_stream.getTracks().forEach(track => track.stop());
        state.camera_stream = null;
        dom.webcamPreview.style.display = 'none';
        dom.webcamPreview.srcObject = null;
    }
    
    dom.queryInput.value = '';
    appendMessage('user', uiText || "[Image Attached]");

    const payload = {
        message: text || "Analyze this image",
        session_id: state.session_id,
        ttsEnabled: state.ttsEnabled
    };

    let endpoint = '/api/chat';
    
    if (state.current_image_base64) {
        endpoint = '/api/vision';
        // The API schema uses `image: str` for the base64 string
        const base64Data = state.current_image_base64.split(',')[1] || state.current_image_base64;
        payload.image = base64Data;
        
        // Clear image state after sending
        state.current_image_base64 = null;
        dom.imageThumbnail.src = '';
        dom.imagePreviewPane.classList.add('hidden');
        dom.imageInput.value = '';
    } else {
        payload.mode = state.mode;
    }

    try {
        const res = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (res.ok) {
            const data = await res.json();
            appendMessage('system', data.response);
            if (data.audio_url) {
                const responseVoice = new Audio(data.audio_url);
                responseVoice.onended = () => {
                    if (state.voiceEnabled) {
                        startListeningLoop(); // Seamlessly resume listening for the next command!
                    }
                };
                responseVoice.play();
            } else {
                if (state.voiceEnabled) {
                    startListeningLoop();
                }
            }
        } else {
            appendMessage('system', "Error: Could not reach backend.");
            if (state.voiceEnabled) startListeningLoop();
        }
    } catch (e) {
        appendMessage('system', "Error: Request failed.");
        if (state.voiceEnabled) startListeningLoop();
    }
}

dom.executeBtn.addEventListener('click', executeCommand);
dom.queryInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        executeCommand();
    }
});

// Drag and Drop Overlay
const overlay = document.createElement('div');
overlay.className = 'drag-overlay';
document.body.appendChild(overlay);

['dragenter', 'dragover'].forEach(eventName => {
    document.addEventListener(eventName, e => {
        e.preventDefault();
        document.body.classList.add('drag-active');
    }, false);
});

['dragleave', 'drop'].forEach(eventName => {
    document.addEventListener(eventName, e => {
        e.preventDefault();
        document.body.classList.remove('drag-active');
    }, false);
});

document.addEventListener('drop', e => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFileInput(files[0]);
    }
});

// Init
checkStatus();
