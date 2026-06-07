// WebGL Orb Initialization
let isVoiceEnabled = true;

const canvas = document.getElementById('webgl-orb');
const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, canvas.clientWidth / canvas.clientHeight, 0.1, 100);
camera.position.z = 5;

const geometry = new THREE.IcosahedronGeometry(1.5, 2);
const material = new THREE.MeshStandardMaterial({ 
    color: 0x7c6aef, 
    wireframe: true, 
    transparent: true,
    opacity: 0.6
});
const sphere = new THREE.Mesh(geometry, material);
scene.add(sphere);

const light = new THREE.PointLight(0xffffff, 1, 100);
light.position.set(10, 10, 10);
scene.add(light);

function animateOrb() {
    requestAnimationFrame(animateOrb);
    sphere.rotation.x += 0.003;
    sphere.rotation.y += 0.003;
    renderer.render(scene, camera);
}

function resizeOrb() {
    const container = canvas.parentElement;
    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight, false);
}

window.addEventListener('resize', resizeOrb);
resizeOrb();
animateOrb();

// Streaming Logic
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const chatHistory = document.getElementById('chat-history');
const taskList = document.getElementById('task-list');
const voiceToggle = document.getElementById('voice-toggle');

voiceToggle.addEventListener('click', () => {
    isVoiceEnabled = !isVoiceEnabled;
    if (isVoiceEnabled) {
        voiceToggle.classList.add('voice-active');
        voiceToggle.textContent = 'VOICE: ON';
    } else {
        voiceToggle.classList.remove('voice-active');
        voiceToggle.textContent = 'VOICE: OFF';
    }
});

let currentSystemMessageText = null;
const ttsAudioPlayer = new Audio();

async function playTTS(text) {
    if (!text) return;
    
    // Scrub code snippets and markdown
    let scrubbed = text.replace(/```[\s\S]*?```/g, ''); // Remove code blocks
    scrubbed = scrubbed.replace(/\[Research Results\][\s\S]*?(?:\[\/Research Results\]|$)/gi, '');
    scrubbed = scrubbed.replace(/[*_#`~>]/g, ''); // Remove markdown characters
    scrubbed = scrubbed.trim().slice(0, 1000);
    
    if (!scrubbed) return;
    
    if (isVoiceEnabled) {
        try {
            const response = await fetch('/api/tts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: scrubbed })
            });
            if (!response.ok) throw new Error('TTS network response was not ok');
            
            const blob = await response.blob();
            const audioUrl = URL.createObjectURL(blob);
            ttsAudioPlayer.src = audioUrl;
            ttsAudioPlayer.play().catch(e => console.error("Audio play error:", e));
        } catch (e) {
            console.error("TTS playback failed:", e);
        }
    }
}

function appendMessage(role, text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}-msg`;
    
    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.textContent = role === 'system' ? 'V' : 'U';
    
    const textDiv = document.createElement('div');
    textDiv.className = 'text';
    textDiv.textContent = text;
    
    msgDiv.appendChild(avatar);
    msgDiv.appendChild(textDiv);
    chatHistory.appendChild(msgDiv);
    
    chatHistory.scrollTop = chatHistory.scrollHeight;
    
    if (role === 'system') {
        currentSystemMessageText = textDiv;
    }
}

function addTaskToWidget(plan) {
    const placeholder = taskList.querySelector('.task-placeholder');
    if (placeholder) {
        placeholder.remove();
    }
    
    plan.forEach((step, index) => {
        const taskDiv = document.createElement('div');
        taskDiv.className = 'task-item';
        taskDiv.setAttribute('data-step', step);
        
        const statusDiv = document.createElement('div');
        statusDiv.className = 'status';
        statusDiv.textContent = 'PENDING';
        
        const contentDiv = document.createElement('div');
        contentDiv.textContent = step;
        
        taskDiv.appendChild(statusDiv);
        taskDiv.appendChild(contentDiv);
        
        taskList.appendChild(taskDiv);
    });
}

function sendMessage() {
    const text = chatInput.value.trim();
    if (!text) return;
    
    chatInput.value = '';
    appendMessage('user', text);
    currentSystemMessageText = null;
    
    // Animate the orb faster when thinking
    sphere.material.opacity = 0.9;
    sphere.material.color.setHex(0x9d8df0);
    let fastSpin = setInterval(() => {
        sphere.rotation.y += 0.02;
    }, 16);
    
    const eventSource = new EventSource(`/api/stream?prompt=${encodeURIComponent(text)}`);
    
    eventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            
            if (data.type === 'token') {
                if (!currentSystemMessageText) {
                    appendMessage('system', '');
                }
                currentSystemMessageText.textContent += data.text;
                chatHistory.scrollTop = chatHistory.scrollHeight;
            } 
            else if (data.type === 'task') {
                addTaskToWidget(data.plan);
            }
            else if (data.type === 'task_status') {
                const items = taskList.querySelectorAll('.task-item');
                let targetItem = null;
                for (let item of items) {
                    if (item.getAttribute('data-step') === data.step) {
                        targetItem = item;
                        break;
                    }
                }
                
                if (targetItem) {
                    const statusDiv = targetItem.querySelector('.status');
                    if (data.status === 'running') {
                        targetItem.classList.add('running');
                        statusDiv.textContent = 'RUNNING';
                    } else if (data.status === 'completed') {
                        targetItem.classList.remove('running');
                        targetItem.classList.add('completed');
                        statusDiv.textContent = 'COMPLETED';
                    }
                }
            }
            else if (data.type === 'done') {
                eventSource.close();
                clearInterval(fastSpin);
                sphere.material.opacity = 0.6;
                sphere.material.color.setHex(0x7c6aef);
                
                if (currentSystemMessageText && currentSystemMessageText.textContent) {
                    playTTS(currentSystemMessageText.textContent);
                }
            }
            else if (data.type === 'error') {
                if (!currentSystemMessageText) appendMessage('system', '');
                currentSystemMessageText.textContent += `\n[Error: ${data.text}]`;
                currentSystemMessageText.style.color = '#ef4444';
                eventSource.close();
                clearInterval(fastSpin);
                sphere.material.opacity = 0.6;
                sphere.material.color.setHex(0x7c6aef);
            }
        } catch (e) {
            console.error("Error parsing SSE data", e);
        }
    };
    
    eventSource.onerror = function() {
        console.error("EventSource failed");
        eventSource.close();
        clearInterval(fastSpin);
        sphere.material.opacity = 0.6;
        sphere.material.color.setHex(0x7c6aef);
        if (!currentSystemMessageText) appendMessage('system', 'Connection to Brain Service lost.');
    };
}

sendBtn.addEventListener('click', sendMessage);
chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

const cameraTrigger = document.getElementById('camera-trigger');
if (cameraTrigger) {
    cameraTrigger.addEventListener('click', async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true });
            const video = document.createElement('video');
            video.srcObject = stream;
            
            video.onloadedmetadata = async () => {
                await video.play();
                
                const canvas = document.createElement('canvas');
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                
                // Stop all tracks immediately to turn off physical LED
                stream.getTracks().forEach(track => track.stop());
                video.srcObject = null;
                
                // Create shutter flash effect
                const flash = document.createElement('div');
                flash.className = 'camera-flash';
                document.body.appendChild(flash);
                setTimeout(() => flash.remove(), 300);
                
                // Convert frame to blob and send POST to /api/upload
                canvas.toBlob(async (blob) => {
                    const formData = new FormData();
                    formData.append('file', blob, 'webcam.jpg');
                    
                    try {
                        const response = await fetch('/api/upload', {
                            method: 'POST',
                            body: formData
                        });
                        
                        if (response.ok) {
                            chatInput.value = "TTCAMTOKENTT Visual analysis request. Describe this operational scene.";
                            sendMessage();
                        } else {
                            console.error('Upload failed with status:', response.status);
                        }
                    } catch (e) {
                        console.error('Upload error:', e);
                    }
                }, 'image/jpeg');
            };
        } catch (e) {
            console.error('Camera access error:', e);
        }
    });
}
