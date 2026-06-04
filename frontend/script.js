const state = {
    session_id: "test_session_001",
    current_image_base64: null,
    mode: "VICTOR",
    camera_stream: null,
    ttsEnabled: true,
    voiceEnabled: false
};

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

dom.imageInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = (event) => {
            state.current_image_base64 = event.target.result;
            dom.imageThumbnail.src = state.current_image_base64;
            dom.imagePreviewPane.classList.remove('hidden');
        };
        reader.readAsDataURL(file);
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

dom.voiceToggleBtn.addEventListener('click', () => {
    state.voiceEnabled = !state.voiceEnabled;
    dom.voiceToggleBtn.classList.toggle('active');
});

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
                new Audio(data.audio_url).play();
            }
        } else {
            appendMessage('system', "Error: Could not reach backend.");
        }
    } catch (e) {
        appendMessage('system', "Error: Request failed.");
    }
}

dom.executeBtn.addEventListener('click', executeCommand);
dom.queryInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        executeCommand();
    }
});

// Init
checkStatus();
