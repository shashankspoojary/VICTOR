
const API = (typeof window !== 'undefined' && window.location.origin)
    ? window.location.origin
    : 'http://localhost:8000';

let sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substring(2, 9);
let currentMode = 'victor';
let isStreaming = false;
let isListening = false;
let camStream = null;
let autoListenMode = false;
const SPEECH_ERROR_MAX_RETRIES = 3;
let speechErrorRetryCount = 0;
const SPEECH_SEND_DELAY_MS        = 600;  // ms to wait after final result before sending
const SPEECH_RESTART_DELAY_MS     = 800;  // ms before restarting after recognition ends
const TTS_ECHO_MIN_WORDS          = 1;    // minimum words needed to treat speech as real interrupt
const TTS_POST_STOP_GUARD_MS      = 900;  // ms of silence after TTS ends before normal listening
let speechSendTimeout = null;
let pendingSendTranscript = null;
let latestTranscript = '';
let safariVoiceHintShown = false;
let orb = null;
let recognition = null;
let ttsPlayer = null;
let currentStreamController = null;

const SETTINGS_KEY = 'victor_settings';
const DEFAULT_SETTINGS = { autoOpenActivity: true, autoOpenSearchResults: true, thinkingSounds: true, voiceInterrupt: false, autoOpenNewTabs: false, proactiveBriefings: true };
let latestAiSpeech = '';
let lastTtsEndTime = 0;
let ttsIsSpeaking  = false;  // true while the AI TTS audio element is actively playing
const PRE_STARTER_FILES = ['starter_1', 'starter_2', 'starter_3', 'starter_4', 'starter_5', 'starter_6', 'starter_7', 'starter_8', 'starter_9', 'starter_10'];
let PRE_STARTER_CACHE = {};
let settings = { ...DEFAULT_SETTINGS };
const $ = id => document.getElementById(id);
const chatMessages = $('chat-messages');
const messageInput = $('message-input');
const sendBtn      = $('send-btn');
const micBtn       = $('mic-btn');
const ttsBtn       = $('tts-btn');
const newChatBtn   = $('new-chat-btn');
const charCount    = $('char-count');
const welcomeTitle = $('welcome-title');
const modeSlider   = $('mode-slider');
const btnVictor    = $('btn-victor');
const statusDot    = document.querySelector('.status-dot');
const statusText   = document.querySelector('.status-text');
const orbContainer = $('orb-container');
const searchResultsToggle = $('search-results-toggle');
const searchResultsWidget = $('search-results-widget');
const searchResultsClose  = $('search-results-close');
const searchResultsQuery  = $('search-results-query');
const searchResultsAnswer = $('search-results-answer');
const searchResultsList   = $('search-results-list');
const activityPanel       = $('activity-panel');
const activityToggle      = $('activity-toggle');
const activityClose       = $('activity-close');
const activityList        = $('activity-list');
const panelOverlay        = $('panel-overlay');

/* ================================================================
   ORB CSS CLASS SYNC — Maps orb state to CSS classes
   ================================================================ */
function syncOrbClass(state) {
    if (!orbContainer) return;
    const classes = ['orb-listening', 'orb-thinking', 'orb-speaking', 'orb-responding'];
    classes.forEach(c => orbContainer.classList.remove(c));
    if (state && state !== 'idle') {
        orbContainer.classList.add(`orb-${state}`);
    }
}
const speechWidget        = $('speech-widget');
const speechWidgetText    = $('speech-widget-text');
const settingsBtn         = $('settings-btn');
const camBtn              = $('cam-btn');
const camPanel            = $('cam-panel');
const camVideo            = $('cam-video');
const camCanvas           = $('cam-canvas');
const camVisionModeInput  = $('cam-vision-mode');
const camMinimize         = $('cam-minimize');
const camClose            = $('cam-close');
const camPanelHeader      = $('cam-panel-header');
const camPanelResize      = $('cam-panel-resize');
const settingsPanel       = $('settings-panel');
const settingsClose       = $('settings-close');
const toggleAutoActivity  = $('toggle-auto-activity');
const toggleAutoSearch    = $('toggle-auto-search');
const toggleThinkingSounds = $('toggle-thinking-sounds');
const toggleVoiceInterrupt = $('toggle-voice-interrupt');
const toggleAutoOpenTabs  = $('toggle-auto-open-tabs');
const toggleProactiveBriefings = $('toggle-proactive-briefings');
const toastContainer     = $('toast-container');
const uploadBtn          = $('upload-btn');
const fileInput          = $('file-input');
const filePreviewStrip   = $('file-preview-strip');
const dragOverlay        = $('drag-overlay');
const appEl              = $('app');

let selectedFiles = [];
let dragCounter = 0;


/* ================================================================
   File Upload Helpers
   ================================================================ */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function getFileIconSVG(mime) {
    if (mime && mime.startsWith('image/')) {
        return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>';
    }
    if (mime && mime.includes('pdf')) {
        return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>';
    }
    if (mime && (mime.includes('code') || mime.includes('javascript') || mime.includes('json') || mime.includes('xml') || mime.includes('html'))) {
        return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>';
    }
    if (mime && (mime.includes('text') || mime.includes('markdown'))) {
        return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>';
    }
    return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>';
}

function readFileAsBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
            const base64 = (reader.result || '').split(',')[1] || '';
            resolve(base64);
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

async function handleFileSelect(files) {
    if (!files || files.length === 0) return;
    const maxFiles = 10;
    const remaining = maxFiles - selectedFiles.length;
    if (remaining <= 0) {
        showToast('Maximum 10 files per message.');
        return;
    }
    const toAdd = Array.from(files).slice(0, remaining);
    for (const file of toAdd) {
        const isImage = file.type.startsWith('image/');
        let previewUrl = null;
        if (isImage) {
            previewUrl = URL.createObjectURL(file);
        }
        try {
            const base64 = await readFileAsBase64(file);
            selectedFiles.push({
                file,
                name: file.name,
                type: file.type,
                size: file.size,
                base64,
                previewUrl,
                isImage
            });
        } catch (e) {
            console.warn('Failed to read file:', file.name, e);
            showToast('Failed to read ' + file.name);
        }
    }
    renderFilePreviews();
    if (files.length > remaining) {
        showToast(`Only added ${remaining} of ${files.length} files (max 10).`);
    }
    if (messageInput) messageInput.focus();
}

function renderFilePreviews() {
    if (!filePreviewStrip) return;
    filePreviewStrip.innerHTML = '';
    if (selectedFiles.length === 0) {
        filePreviewStrip.style.display = 'none';
        return;
    }
    filePreviewStrip.style.display = 'flex';
    selectedFiles.forEach((item, index) => {
        const el = document.createElement('div');
        el.className = 'file-preview-item';
        let thumbHTML = '';
        if (item.isImage && item.previewUrl) {
            thumbHTML = `<img src="${item.previewUrl}" alt="" />`;
        } else {
            const ext = item.name.split('.').pop().toUpperCase().slice(0, 4);
            thumbHTML = `<span>${ext}</span>`;
        }
        el.innerHTML = `
            <div class="file-preview-thumb">${thumbHTML}</div>
            <div class="file-preview-info">
                <div class="file-preview-name" title="${escapeAttr(item.name)}">${escapeHtml(item.name)}</div>
                <div class="file-preview-meta">${formatFileSize(item.size)}</div>
            </div>
            <button class="file-preview-remove" title="Remove" aria-label="Remove file">×</button>
        `;
        el.querySelector('.file-preview-remove').addEventListener('click', () => removeFile(index));
        filePreviewStrip.appendChild(el);
    });
}

function removeFile(index) {
    const item = selectedFiles[index];
    if (item && item.previewUrl) URL.revokeObjectURL(item.previewUrl);
    selectedFiles.splice(index, 1);
    renderFilePreviews();
    if (messageInput) messageInput.focus();
}

function clearSelectedFiles() {
    selectedFiles.forEach(item => { if (item.previewUrl) URL.revokeObjectURL(item.previewUrl); });
    selectedFiles = [];
    if (filePreviewStrip) filePreviewStrip.innerHTML = '';
    if (filePreviewStrip) filePreviewStrip.style.display = 'none';
    if (fileInput) fileInput.value = '';
}

function addFileAttachments(contentEl, attachments) {
    if (!attachments || attachments.length === 0) return;
    const wrap = document.createElement('div');
    wrap.className = 'msg-attachments';
    attachments.forEach(att => {
        if (att.isImage && att.previewUrl) {
            const img = document.createElement('img');
            img.src = att.previewUrl;
            img.alt = att.name || 'Attachment';
            img.className = 'msg-attachment-image';
            img.loading = 'lazy';
            img.addEventListener('click', () => {
                window.open(att.previewUrl, '_blank');
            });
            wrap.appendChild(img);
        } else {
            const card = document.createElement('div');
            card.className = 'msg-attachment-file';
            const icon = document.createElement('div');
            icon.className = 'msg-attachment-icon';
            icon.innerHTML = getFileIconSVG(att.type);
            const info = document.createElement('div');
            info.className = 'msg-attachment-info';
            const name = document.createElement('div');
            name.className = 'msg-attachment-name';
            name.textContent = att.name || 'File';
            name.title = att.name || '';
            const meta = document.createElement('div');
            meta.className = 'msg-attachment-meta';
            meta.textContent = (att.type || 'Unknown') + ' · ' + formatFileSize(att.size || 0);
            info.appendChild(name);
            info.appendChild(meta);
            card.appendChild(icon);
            card.appendChild(info);
            wrap.appendChild(card);
        }
    });
    contentEl.appendChild(wrap);
}

class PreStarterPlayer {
    constructor() {
        this.audio = document.createElement('audio');
        this.audio.preload = 'auto';
    }
    play(onComplete) {
        const loaded = PRE_STARTER_FILES.filter(f => PRE_STARTER_CACHE[f]);
        if (loaded.length === 0) {
            if (onComplete) onComplete();
            return;
        }
        const file = loaded[Math.floor(Math.random() * loaded.length)];
        const base64 = PRE_STARTER_CACHE[file];
        if (!base64) {
            if (onComplete) onComplete();
            return;
        }
        this.audio.src = 'data:audio/mp3;base64,' + base64;
        this.audio.currentTime = 0;
        let fired = false;
        const done = () => {
            if (fired) return;
            fired = true;
            this.audio.onended = null;
            this.audio.onerror = null;
            if (onComplete) onComplete();
        };
        this.audio.onended = done;
        this.audio.onerror = done;
        const p = this.audio.play();
        if (p) p.catch(done);
    }
}

let preStarterPlayer = null;

/* ================================================================
   TTSPlayer — Enhanced with Orb audio reactivity
   ================================================================ */
class TTSPlayer {
    constructor() {
        this.queue = [];
        this.playing = false;
        this.enabled = true;
        this.stopped = false;
        this.audio = document.createElement('audio');
        this.audio.preload = 'auto';
    }
    unlock() {
        const silentWav = 'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA';
        this.audio.src = silentWav;
        const p = this.audio.play();
        if (p) p.catch(() => {});
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const g = ctx.createGain();
            g.gain.value = 0;
            const o = ctx.createOscillator();
            o.connect(g);
            g.connect(ctx.destination);
            o.start(0);
            o.stop(ctx.currentTime + 0.001);
            setTimeout(() => ctx.close(), 200);
        } catch (_) {}
    }
    enqueue(base64Audio) {
        if (!this.enabled || this.stopped) return;
        this.queue.push(base64Audio);
        if (!this.playing) this._playLoop();
    }
    stop() {
        this.stopped = true;
        this.audio.pause();
        this.audio.removeAttribute('src');
        this.audio.load();
        this.queue = [];
        this.playing = false;
        // Record exact stop time for the post-TTS silence guard
        lastTtsEndTime = Date.now();
        ttsIsSpeaking  = false;
        if (ttsBtn) ttsBtn.classList.remove('tts-speaking');
        if (orbContainer) orbContainer.classList.remove('speaking');
        if (orb) {
            orb.setActive(false);
            orb.setTTSSpeaking(false);
            /* Only reset to idle if not streaming */
            if (!isStreaming) {
                orb.setState('idle');
                syncOrbClass('idle');
            }
        }
        if (typeof this.onPlaybackComplete === 'function') this.onPlaybackComplete();
    }
    reset() {
        this.stop();
        this.stopped = false;
        this._loopId = (this._loopId || 0) + 1;
    }
    async _playLoop() {
        if (this.playing) return;
        this.playing = true;
        ttsIsSpeaking = true; // mic guard ON — AI audio is starting
        this._loopId = (this._loopId || 0) + 1;
        const myId = this._loopId;
        if (ttsBtn) ttsBtn.classList.add('tts-speaking');
        if (orbContainer) orbContainer.classList.add('speaking');

        /* ---- Connect orb to TTS audio for reactivity ---- */
        if (orb) {
            orb.connectTTSAudio(this.audio);
            orb.setTTSSpeaking(true);
            orb.setState('speaking');
            syncOrbClass('speaking');
            orb.setActive(true);
        }

        if (!settings.voiceInterrupt && isListening) {
            stopListening();
        }

        /* ---- Open mic for voice interrupt during TTS ---- */
        if (settings.voiceInterrupt && autoListenMode && !isListening && recognition) {
            setTimeout(() => {
                if (settings.voiceInterrupt && autoListenMode && !isListening && recognition) startListening();
            }, SPEECH_RESTART_DELAY_MS);
        }

        while (this.queue.length > 0) {
            if (this.stopped || myId !== this._loopId) break;
            const b64 = this.queue.shift();
            try {
                await this._playB64(b64);
            } catch (e) {
                console.warn('TTS segment error:', e);
            }
        }
        if (myId !== this._loopId) {
            this.playing = false;
            return;
        }
        this.playing = false;

        // Record the exact moment audio finished for the post-TTS silence guard.
        lastTtsEndTime = Date.now();
        ttsIsSpeaking  = false; // mic guard OFF — AI audio has ended

        if (ttsBtn) ttsBtn.classList.remove('tts-speaking');
        if (orbContainer) orbContainer.classList.remove('speaking');

        /* ---- Reset orb TTS state ---- */
        if (orb) {
            orb.setTTSSpeaking(false);
            if (!isStreaming) {
                orb.setState('idle');
                syncOrbClass('idle');
            }
            orb.setActive(false);
        }

        if (typeof this.onPlaybackComplete === 'function') this.onPlaybackComplete();
    }
    _playB64(b64) {
        return new Promise(resolve => {
            this.audio.src = 'data:audio/mp3;base64,' + b64;
            const done = () => { resolve(); };
            this.audio.onended = done;
            this.audio.onerror = done;
            const p = this.audio.play();
            if (p) p.catch(done);
        });
    }
}

/* ================================================================
   Initialization
   ================================================================ */
function init() {
    if (!chatMessages || !messageInput) {
        console.error('[VICTOR] Required DOM elements (chat-messages, message-input) not found.');
        return;
    }
    loadSettings();
    ttsPlayer = new TTSPlayer();
    ttsPlayer.onPlaybackComplete = maybeRestartListening;
    if (ttsBtn) ttsBtn.classList.add('tts-active');
    setGreeting();
    console.log('[init] Creating orb...');
    initOrb();
    /* ---- Set orb to idle after initialization ---- */
    if (typeof orb !== 'undefined' && orb) {
        console.log('[init] Setting orb to idle state');
        orb.setState('idle');
        syncOrbClass('idle');
    } else {
        console.warn('[init] Orb not available');
    }
    initSpeech();
    preloadStarterAudio();
    preStarterPlayer = new PreStarterPlayer();
    checkHealth();
    bindEvents();
    setMode(currentMode);
    autoResizeInput();
    if (messageInput) messageInput.focus();
    
    // Trigger autonomous startup sequence on connection initialization
    sendMessage("INIT_AUTONOMOUS_STARTUP_SEQUENCE");
    initProactiveCheck();
}


async function preloadStarterAudio() {
    const base = (typeof window !== 'undefined' && window.location.origin) ? window.location.origin : '';
    for (const file of PRE_STARTER_FILES) {
        try {
            const r = await fetch(`${base}/app/audio/${file}.mp3`);
            const contentType = r.headers.get('content-type') || '';
            if (!r.ok || contentType.includes('application/json')) continue;
            const blob = await r.blob();
            const base64 = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onloadend = () => resolve((reader.result || '').split(',')[1] || '');
                reader.onerror = reject;
                reader.readAsDataURL(blob);
            });
            if (base64) PRE_STARTER_CACHE[file] = base64;
        } catch (_) {}
    }
}

function loadSettings() {
    try {
        const s = localStorage.getItem(SETTINGS_KEY);
        if (s) {
            const parsed = JSON.parse(s);
            settings = { ...DEFAULT_SETTINGS, ...parsed };
        }
        if (toggleAutoActivity) toggleAutoActivity.checked = settings.autoOpenActivity;
        if (toggleAutoSearch) toggleAutoSearch.checked = settings.autoOpenSearchResults;
        if (toggleThinkingSounds) toggleThinkingSounds.checked = settings.thinkingSounds;
        if (toggleVoiceInterrupt) toggleVoiceInterrupt.checked = settings.voiceInterrupt;
        if (toggleAutoOpenTabs) toggleAutoOpenTabs.checked = settings.autoOpenNewTabs;
        if (toggleProactiveBriefings) toggleProactiveBriefings.checked = settings.proactiveBriefings;
    } catch (_) {}
}

function saveSettings() {
    try {
        localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
    } catch (_) {}
}


function setGreeting() {
    const h = new Date().getHours();
    let g = 'Good evening.';
    if (h < 12) g = 'Good morning.';
    else if (h < 17) g = 'Good afternoon.';
    else if (h >= 22) g = 'Burning the midnight oil?';
    if (welcomeTitle) welcomeTitle.textContent = g;
}

function initOrb() {
    if (typeof OrbRenderer === 'undefined') { console.warn('[initOrb] OrbRenderer not defined'); return; }
    if (!orbContainer) { console.warn('[initOrb] orbContainer not found'); return; }
    try {
        orb = new OrbRenderer(orbContainer, {
            hue: 0,
            hoverIntensity: 0.3,
            backgroundColor: [0.02, 0.02, 0.06]
        });
        console.log('[initOrb] Orb initialized:', !!orb.gl ? 'WebGL' : 'CSS fallback');
    } catch (e) { console.warn('[initOrb] Orb init failed:', e); }
}

function isSafariOrIOS() {
    if (typeof navigator === 'undefined') return false;
    const ua = navigator.userAgent || '';
    return /iPad|iPhone|iPod/.test(ua) ||
        (navigator.vendor && navigator.vendor.indexOf('Apple') > -1) ||
        (/Safari/.test(ua) && !/Chrome|Chromium|CriOS/.test(ua));
}

/* ================================================================
   Speech Recognition (Voice Input)
   ================================================================ */
function isEcho(transcript, isFinal) {
    if (!transcript) return true;

    const msSinceTts = Date.now() - lastTtsEndTime;
    const inGuardWindow = ttsIsSpeaking || (msSinceTts < TTS_POST_STOP_GUARD_MS);

    if (!inGuardWindow) {
        return false; // No echo check if TTS is not active and post-TTS guard window has passed
    }

    // Word count gate (require at least TTS_ECHO_MIN_WORDS)
    const wordCount = transcript.split(/\s+/).filter(Boolean).length;
    if (wordCount < TTS_ECHO_MIN_WORDS) return true;

    // Similarity check against AI speech
    if (latestAiSpeech) {
        const normT  = transcript.toLowerCase().replace(/[^\w\s]/g, '').trim();
        const normAi = latestAiSpeech.toLowerCase().replace(/[^\w\s]/g, '').trim();
        if (normT && normAi && normAi.length > 10 && normT.length >= 2) {
            // Exact substring match
            if (normAi.includes(normT)) return true;

            // Space-insensitive exact match (e.g. "discussPerhaps" vs "discuss perhaps")
            const normTNoSpace = normT.replace(/\s+/g, '');
            const normAiNoSpace = normAi.replace(/\s+/g, '');
            if (normAiNoSpace.includes(normTNoSpace)) return true;

            // Bigram similarity check for longer segments
            if (normT.length >= 6) {
                const bigrams = str => {
                    const bg = [];
                    for (let i = 0; i < str.length - 1; i++) bg.push(str.slice(i, i + 2));
                    return bg;
                };
                const tBg = bigrams(normT);
                const sBg = new Set(bigrams(normAi));
                let match = 0;
                for (const b of tBg) if (sBg.has(b)) match++;
                if (tBg.length > 0 && match / tBg.length > 0.70) return true;
            }
        }
    }
    return false;
}

function initSpeech() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { micBtn.title = 'Speech not supported in this browser'; return; }
    recognition = new SR();
    const safariMode = isSafariOrIOS();

    // Use non-continuous mode: browser gives us clean sentence segments.
    // We restart automatically via onend → maybeRestartListening so the user
    // never notices the brief gap between sessions.
    recognition.continuous     = false;
    recognition.interimResults = !safariMode;
    recognition.maxAlternatives = 1;
    recognition.lang = 'en-US';

    recognition.onresult = e => {
        if (!e.results || e.results.length === 0) return;

        // Concatenate all results in the list to build the full transcript
        let fullTranscript = '';
        for (let i = 0; i < e.results.length; i++) {
            if (e.results[i][0]) {
                fullTranscript += e.results[i][0].transcript;
            }
        }
        const transcript = fullTranscript.trim();
        const last       = e.results[e.results.length - 1];
        const isFinal    = !!(last && last.isFinal);

        if (!transcript) return;

        // Run the echo check. If it is an echo, ignore this result completely.
        if (isEcho(transcript, isFinal)) return;

        // ── VOICE INTERRUPT ───────────────────────────────────────────────────
        // User spoke while AI was playing — stop TTS and answer the new question.
        const ttsActive = ttsPlayer && (ttsPlayer.playing || ttsPlayer.queue.length > 0);
        if (ttsActive && settings.voiceInterrupt && transcript.length > 0) {
            ttsPlayer.stop();
            ttsPlayer.stopped = false;
            ttsIsSpeaking = false;
            lastTtsEndTime = Date.now();
        }

        // ── UPDATE LIVE TRANSCRIPT WIDGET ────────────────────────────────────
        if (speechWidgetText) speechWidgetText.textContent = transcript;
        if (speechWidget) speechWidget.classList.add('visible');

        latestTranscript = transcript;

        // ── SEND ON FINAL ─────────────────────────────────────────────────────
        if (isFinal && transcript) {
            pendingSendTranscript = transcript;
            clearTimeout(speechSendTimeout);
            speechSendTimeout = setTimeout(() => {
                if (pendingSendTranscript) {
                    sendMessage(pendingSendTranscript);
                    pendingSendTranscript = null;
                }
                latestTranscript = '';
                speechSendTimeout = null;
                stopListening(); // recognition ends; onend will restart if needed
            }, SPEECH_SEND_DELAY_MS);
        }
    };

    recognition.onstart = () => {
        isListening = true;
        speechErrorRetryCount = 0;
        if (micBtn) micBtn.classList.add('listening');
        if (speechWidget) speechWidget.classList.add('visible');
        if (speechWidgetText) speechWidgetText.textContent = '';
        /* ---- Set orb to listening state ---- */
        if (orb) { orb.setState('listening'); syncOrbClass('listening'); }
    };

    recognition.onerror = e => {
        const msg = (e && e.error) ? String(e.error) : '';
        const isPermissionDenied = /denied|not-allowed|permission/i.test(msg);
        if (isPermissionDenied && micBtn) {
            micBtn.title = 'Microphone access denied. Allow in browser settings.';
            speechErrorRetryCount = SPEECH_ERROR_MAX_RETRIES;
        } else if (msg && !/no-speech/i.test(msg)) {
            // Only increment retry count for non-silence actual errors
            speechErrorRetryCount++;
        }
        if (speechErrorRetryCount >= SPEECH_ERROR_MAX_RETRIES && micBtn) {
            micBtn.title = 'Voice input — click to try again';
        }
    };

    recognition.onend = () => {
        isListening = false;
        if (micBtn) micBtn.classList.remove('listening');
        if (speechWidget) speechWidget.classList.remove('visible');
        if (speechWidgetText) speechWidgetText.textContent = '';
        /* ---- Reset orb to idle (only if currently in listening state) ---- */
        if (orb && orb.state === 'listening') {
            orb.setState('idle');
            syncOrbClass('idle');
        }

        // If we have a buffered transcript (e.g. recognition ended before the
        // send-timeout fired), flush it now.
        if (pendingSendTranscript) {
            clearTimeout(speechSendTimeout);
            speechSendTimeout = null;
            if (!isEcho(pendingSendTranscript, true)) {
                sendMessage(pendingSendTranscript);
            }
            pendingSendTranscript = null;
            latestTranscript = '';
        } else if (latestTranscript) {
            clearTimeout(speechSendTimeout);
            speechSendTimeout = null;
            if (!isEcho(latestTranscript, false)) {
                sendMessage(latestTranscript);
            }
            latestTranscript = '';
        } else {
            clearTimeout(speechSendTimeout);
            speechSendTimeout = null;
        }
        // Restart automatically in auto-listen mode.
        maybeRestartListening();
    };
}

function startListening() {
    if (!recognition || isListening) return;



    if (isSafariOrIOS() && !safariVoiceHintShown) {
        showToast('Voice works best in Chrome. Safari has limited support.');
        safariVoiceHintShown = true;
    }

    pendingSendTranscript = null;
    latestTranscript = '';
    clearTimeout(speechSendTimeout);
    speechSendTimeout = null;

    try {
        recognition.start();
    } catch (err) {
        console.warn('[startListening] recognition.start failed:', err);
    }
}

function stopListening() {
    clearTimeout(speechSendTimeout);
    speechSendTimeout = null;
    pendingSendTranscript = null;
    try {
        recognition.stop();
    } catch (_) {}
}

function maybeRestartListening() {
    if (!autoListenMode || !recognition) return;
    if (speechErrorRetryCount >= SPEECH_ERROR_MAX_RETRIES) return;

    const ttsActive = ttsPlayer && (ttsPlayer.playing || ttsPlayer.queue.length > 0);

    if (ttsActive || ttsIsSpeaking) {
        if (settings.voiceInterrupt) {
            // TTS is playing — keep the mic OPEN so the user can interrupt mid-speech.
            if (!isListening) {
                setTimeout(() => {
                    if (!autoListenMode || isListening || speechErrorRetryCount >= SPEECH_ERROR_MAX_RETRIES) return;
                    if (ttsIsSpeaking || (ttsPlayer && (ttsPlayer.playing || ttsPlayer.queue.length > 0))) {
                        if (!settings.voiceInterrupt) return;
                    }
                    startListening();
                }, SPEECH_RESTART_DELAY_MS);
            }
        }
        return;
    }

    // Not during TTS — don't restart while a response is streaming.
    // sendMessage's finally block calls us again once streaming ends.
    if (isStreaming) return;

    // Give a short breathing room after TTS finishes so any speaker reverb
    // dies out before we open the mic again.
    const msSinceTts = Date.now() - lastTtsEndTime;
    const guardRemaining = Math.max(0, TTS_POST_STOP_GUARD_MS - msSinceTts);
    const delay = Math.max(SPEECH_RESTART_DELAY_MS, guardRemaining);

    setTimeout(() => {
        if (!autoListenMode || isStreaming || isListening || !recognition || speechErrorRetryCount >= SPEECH_ERROR_MAX_RETRIES) return;
        // Re-check TTS state — it may have started again during the wait.
        if (ttsIsSpeaking || (ttsPlayer && (ttsPlayer.playing || ttsPlayer.queue.length > 0))) return;
        startListening();
    }, delay);
}


/* ================================================================
   Camera
   ================================================================ */
const CAM_BYPASS_TOKEN = 'TTCAMTOKENTT';
const CAMERA_QUERY_PATTERNS = [
    /what\s+(can|do)\s+you\s+see/i,
    /can\s+you\s+see/i,
    /describe\s+(what\s+you\s+see|this|the\s+image)/i,
    /what('s|s)\s+in\s+(this\s+)?(picture|image)/i,
    /what\s+do\s+i\s+look\s+like/i,
    /what\s+(am\s+i\s+)?holding/i,
    /show\s+me\s+what\s+you\s+see/i,
    /do\s+you\s+see\s+me/i,
    /look\s+at\s+(me|this|the\s+screen)/i,
];
function isCameraQuery(text) {
    if (!text || typeof text !== 'string') return false;
    const t = text.trim().toLowerCase();
    return CAMERA_QUERY_PATTERNS.some(r => r.test(t)) ||
        (t.includes('see') && (t.includes('what') || t.includes('describe') || t.includes('can')));
}

function startCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        showToast('Camera not supported in this browser.');
        return Promise.reject(new Error('Camera not supported'));
    }
    if (camStream) return Promise.resolve();
    return navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false })
        .then(stream => {
            camStream = stream;
            if (camVideo) camVideo.srcObject = stream;
            if (camPanel) { camPanel.classList.add('visible'); camPanel.setAttribute('aria-hidden', 'false'); }
            if (camBtn) {
                camBtn.classList.add('cam-active');
                camBtn.title = 'Camera on — click to turn off';
                const icon = camBtn.querySelector('.cam-icon');
                const iconActive = camBtn.querySelector('.cam-icon-active');
                if (icon) icon.style.display = 'none';
                if (iconActive) iconActive.style.display = '';
            }
        })
        .catch(err => {
            showToast('Camera access denied. ' + (err.message || ''));
            throw err;
        });
}

function stopCamera() {
    if (camStream) {
        camStream.getTracks().forEach(t => t.stop());
        camStream = null;
    }
    if (camVideo) camVideo.srcObject = null;
    if (camPanel) { camPanel.classList.remove('visible'); camPanel.setAttribute('aria-hidden', 'true'); }
    if (camVisionModeInput) camVisionModeInput.checked = false;
    if (camBtn) {
        camBtn.classList.remove('cam-active');
        camBtn.title = 'Camera — capture and send for vision';
        const icon = camBtn.querySelector('.cam-icon');
        const iconActive = camBtn.querySelector('.cam-icon-active');
        if (icon) icon.style.display = '';
        if (iconActive) iconActive.style.display = 'none';
    }
}

function initCameraPanel() {
    if (!camPanel) return;
    let dragStart = { x: 0, y: 0, left: 0, top: 0 };
    let resizeStart = { x: 0, y: 0, w: 0, h: 0 };
    if (camClose) camClose.addEventListener('click', () => stopCamera());
    if (camMinimize) camMinimize.addEventListener('click', () => {
        camPanel.classList.toggle('minimized');
    });
    if (camPanelHeader) {
        camPanelHeader.addEventListener('mousedown', (e) => {
            if (e.target.closest('.cam-panel-btn, .cam-panel-vision-mode')) return;
            e.preventDefault();
            const r = camPanel.getBoundingClientRect();
            dragStart = { x: e.clientX, y: e.clientY, left: r.left, top: r.top };
            const onMove = (ev) => {
                const dx = ev.clientX - dragStart.x;
                const dy = ev.clientY - dragStart.y;
                camPanel.style.left = (dragStart.left + dx) + 'px';
                camPanel.style.top = (dragStart.top + dy) + 'px';
                camPanel.style.right = 'auto';
                camPanel.style.bottom = 'auto';
            };
            const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); };
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        });
    }
    if (camPanelResize) {
        camPanelResize.addEventListener('mousedown', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const r = camPanel.getBoundingClientRect();
            resizeStart = { x: e.clientX, y: e.clientY, w: r.width, h: r.height };
            const onMove = (ev) => {
                const dw = ev.clientX - resizeStart.x;
                const dh = ev.clientY - resizeStart.y;
                const nw = Math.max(200, Math.min(window.innerWidth, resizeStart.w + dw));
                const nh = Math.max(150, Math.min(window.innerHeight * 0.7, resizeStart.h + dh));
                camPanel.style.width = nw + 'px';
                camPanel.style.height = nh + 'px';
            };
            const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); };
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        });
    }
    camPanel.addEventListener('dblclick', (e) => {
        if (e.target.closest('.cam-panel-header') && !e.target.closest('.cam-panel-btn, .cam-panel-vision-mode')) {
            camPanel.classList.toggle('minimized');
        }
    });
    camPanel.querySelector('.cam-panel-body')?.addEventListener('click', (e) => {
        if (camPanel.classList.contains('minimized')) camPanel.classList.remove('minimized');
    });
}

/* ================================================================
   Action Handlers — Enhanced with Activity Panel Logging
   ================================================================ */
function handleActions(actions, contentEl) {
    if (!actions) return;
    if (!contentEl) return;

    /* ---- Activity panel logging helper ---- */
    const logAction = (event, message) => {
        appendActivity({ event, message });
        if (activityToggle) activityToggle.style.display = '';
        if (activityPanel && settings.autoOpenActivity) {
            activityPanel.classList.add('open');
            updatePanelOverlay();
        }
    };

    /* ---- Show initial toast for immediate feedback ---- */
    const totalActions = (actions.wopens?.length || 0) + (actions.plays?.length || 0) +
                         (actions.googlesearches?.length || 0) + (actions.youtubesearches?.length || 0) +
                         (actions.images?.length || 0) + (actions.contents?.length || 0) +
                         (actions.cam ? 1 : 0);
    if (totalActions > 0) {
        logAction('executing_action', `Starting ${totalActions} action${totalActions > 1 ? 's' : ''}...`);
        showToast(`Executing ${totalActions} action${totalActions > 1 ? 's' : ''}...`, 3000);
    }

    /* ---- Collect actions for summary display ---- */
    const performedActions = [];

    const safeOpen = (url, context) => {
        if (url && (url.startsWith('http://') || url.startsWith('https://'))) {
            try {
                if (settings.autoOpenNewTabs) {
                    const w = window.open(url, '_blank', 'noopener,noreferrer');
                    if (!w) {
                        showToast('Pop-up blocked. Please allow pop-ups for VICTOR.');
                        performedActions.push({ type: 'blocked', label: `Blocked: ${context || friendlyUrlLabel(url)}`, url });
                    } else {
                        performedActions.push({ type: 'opened', label: context || friendlyUrlLabel(url), url });
                    }
                } else {
                    // Note: Background opening is handled securely by the backend to prevent focus stealing.
                    performedActions.push({ type: 'opened', label: context || friendlyUrlLabel(url), url });
                }
            } catch (_) {
                showToast('Could not open link. Please try again.');
                performedActions.push({ type: 'error', label: `Failed: ${context || friendlyUrlLabel(url)}`, url });
            }
        }
    };

    /* ---- Web opens (YouTube, websites, etc.) ---- */
    (actions.wopens || []).forEach(url => {
        logAction('opening_url', `Opening ${friendlyUrlLabel(url)} — ${url}`);
        safeOpen(url, `Open ${friendlyUrlLabel(url)}`);
    });

    /* ---- Media playback ---- */
    (actions.plays || []).forEach(url => {
        logAction('playing_media', `Playing media from ${friendlyUrlLabel(url)} — ${url}`);
        safeOpen(url, `Play ${friendlyUrlLabel(url)}`);
    });

    /* ---- Google searches ---- */
    (actions.googlesearches || []).forEach(q => {
        const url = (typeof q === 'string' && (q.startsWith('http://') || q.startsWith('https://')))
            ? q
            : `https://www.google.com/search?q=${encodeURIComponent(q)}`;
        logAction('google_search', `Google search: "${q}"`);
        safeOpen(url, `Google: "${q}"`);
    });

    /* ---- YouTube searches ---- */
    (actions.youtubesearches || []).forEach(q => {
        const url = (typeof q === 'string' && (q.startsWith('http://') || q.startsWith('https://')))
            ? q
            : `https://www.youtube.com/results?search_query=${encodeURIComponent(q)}`;
        logAction('youtube_search', `YouTube search: "${q}"`);
        safeOpen(url, `YouTube: "${q}"`);
    });

    /* ---- Generated images ---- */
    if (actions.images && actions.images.length > 0) {
        logAction('executing_action', `Displaying ${actions.images.length} generated image(s)`);
        const wrap = document.createElement('div');
        wrap.className = 'msg-actions-images';
        actions.images.forEach(url => {
            const img = document.createElement('img');
            img.src = url;
            img.alt = 'Generated image';
            img.className = 'msg-action-image';
            img.loading = 'lazy';
            img.onerror = () => {
                img.style.display = 'none';
                const fallback = document.createElement('div');
                fallback.className = 'msg-action-image-fallback';
                fallback.textContent = 'Image failed to load.';
                wrap.appendChild(fallback);
            };
            wrap.appendChild(img);
        });
        contentEl.appendChild(wrap);
        performedActions.push({ type: 'image', label: `Generated ${actions.images.length} image(s)` });
    }

    /* ---- Generated content ---- */
    if (actions.contents && actions.contents.length > 0) {
        logAction('executing_action', `Displaying ${actions.contents.length} content snippet(s)`);
        const wrap = document.createElement('div');
        wrap.className = 'msg-actions-contents';
        actions.contents.forEach(t => {
            const p = document.createElement('div');
            p.className = 'msg-action-content';
            p.textContent = t;
            wrap.appendChild(p);
        });
        contentEl.appendChild(wrap);
        performedActions.push({ type: 'content', label: `Generated ${actions.contents.length} content snippet(s)` });
    }

    /* ---- Camera actions ---- */
    if (actions.cam) {
        if (actions.cam.action === 'open') {
            logAction('executing_action', 'Activating camera');
            performedActions.push({ type: 'camera', label: 'Camera activated' });
            startCamera();
        } else if (actions.cam.action === 'close') {
            logAction('executing_action', 'Deactivating camera');
            performedActions.push({ type: 'camera', label: 'Camera deactivated' });
            stopCamera();
        } else if (actions.cam.action === 'open_and_capture') {
            logAction('executing_action', 'Opening camera and capturing frame');
            const resendMsg = actions.cam.resend_message || 'What do you see?';
            performedActions.push({ type: 'camera', label: 'Camera capture & vision analysis' });
            (async () => {
                try {
                    await startCamera();
                    await new Promise((resolve) => {
                        if (!camVideo) { resolve(); return; }
                        if (camVideo.readyState >= 2 && camVideo.videoWidth > 0) {
                            setTimeout(resolve, 500);
                            return;
                        }
                        const onReady = () => {
                            camVideo.removeEventListener('loadeddata', onReady);
                            clearTimeout(t);
                            setTimeout(resolve, 600);
                        };
                        const t = setTimeout(() => {
                            camVideo.removeEventListener('loadeddata', onReady);
                            resolve();
                        }, 4000);
                        camVideo.addEventListener('loadeddata', onReady);
                    });
                    const frame = await captureFrameAsBase64Safe();
                    if (frame) {
                        sendMessageWithImage(resendMsg, frame);
                    } else {
                        showToast('Could not capture camera frame. Please try again.');
                    }
                } catch (err) {
                    showToast('Camera access denied.');
                }
            })();
        }
    }

    /* ---- Render action execution summary in message ---- */
    if (performedActions.length > 0) {
        renderActionSummary(contentEl, performedActions);
        logAction('action_complete', `Completed ${performedActions.length} action(s)`);
    }
}

/* ================================================================
   Action Execution Summary — Shows what actions were performed
   ================================================================ */
function renderActionSummary(contentEl, actions) {
    if (!contentEl || !actions || actions.length === 0) return;

    const summaryWrap = document.createElement('div');
    summaryWrap.className = 'action-summary';

    const header = document.createElement('div');
    header.className = 'action-summary-header';

    /* Icon based on action types */
    const hasOpen = actions.some(a => a.type === 'opened');
    const hasMedia = actions.some(a => a.type === 'play');
    const hasSearch = actions.some(a => a.type === 'google_search' || a.type === 'youtube_search');

    let iconSvg = '';
    if (hasMedia) {
        iconSvg = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>';
    } else if (hasSearch) {
        iconSvg = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>';
    } else {
        iconSvg = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>';
    }

    header.innerHTML = `${iconSvg} <span>Executed ${actions.length} action${actions.length > 1 ? 's' : ''}</span>`;
    summaryWrap.appendChild(header);

    const list = document.createElement('div');
    list.className = 'action-summary-list';

    actions.forEach(action => {
        const item = document.createElement('div');
        item.className = 'action-summary-item';

        let icon = '';
        if (action.type === 'opened' || action.type === 'open') {
            icon = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>';
        } else if (action.type === 'play' || action.type === 'playing_media') {
            icon = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>';
        } else if (action.type === 'google_search' || action.type === 'youtube_search' || action.type === 'search') {
            icon = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>';
        } else if (action.type === 'image') {
            icon = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>';
        } else if (action.type === 'content') {
            icon = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>';
        } else if (action.type === 'camera') {
            icon = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>';
        } else if (action.type === 'blocked') {
            icon = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
        } else if (action.type === 'error') {
            icon = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>';
        } else {
            icon = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
        }

        if (action.url) {
            item.classList.add('has-link');
            
            const leftContainer = document.createElement('div');
            leftContainer.className = 'action-summary-left';
            leftContainer.innerHTML = `${icon} <span class="action-summary-label">${escapeHtml(action.label)}</span>`;
            item.appendChild(leftContainer);

            const link = document.createElement('a');
            link.href = '#';
            link.className = 'action-summary-link-btn';
            link.textContent = 'Open';
            link.addEventListener('click', (e) => {
                e.preventDefault();
                fetch('/api/focus_tab', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: action.url })
                }).then(res => res.json()).then(resData => {
                    if (resData.status !== 'success') {
                        window.open(action.url, '_blank');
                    }
                }).catch(() => {
                    window.open(action.url, '_blank');
                });
            });
            item.appendChild(link);
        } else {
            const labelSpan = document.createElement('span');
            labelSpan.className = 'action-summary-label';
            labelSpan.textContent = action.label;
            item.innerHTML = `${icon} `;
            item.appendChild(labelSpan);
        }

        list.appendChild(item);
    });

    summaryWrap.appendChild(list);
    contentEl.appendChild(summaryWrap);
    scrollToBottom();
}

function handleBackgroundTasks(tasks, contentEl) {
    if (!tasks || !tasks.length || !contentEl) return;
    tasks.forEach(task => {
        const card = document.createElement('div');
        card.className = 'bg-task-card';
        card.dataset.taskId = task.task_id;
        const label = task.type === 'generate image' ? 'Image Generation' : task.type === 'content' ? 'Content Writing' : task.type;
        const promptText = task.label ? `"${task.label}"` : '';
        card.innerHTML =
            '<div class="bg-task-header">' +
                '<div class="bg-task-spinner"></div>' +
                '<span class="bg-task-label">' + label + '</span>' +
                '<span class="bg-task-status">Working...</span>' +
            '</div>' +
            (promptText ? '<div class="bg-task-prompt">' + promptText + '</div>' : '');
        contentEl.appendChild(card);
        scrollToBottom();
        pollBackgroundTask(task.task_id, card);
    });
}

function pollBackgroundTask(taskId, cardEl) {
    let pollCount = 0;
    let errorCount = 0;
    const maxPolls = 120;
    const maxErrors = 5;
    const interval = setInterval(() => {
        pollCount++;
        if (pollCount > maxPolls) {
            clearInterval(interval);
            updateTaskCard(cardEl, 'failed', 'Timed out');
            return;
        }
        fetch(`${API}/tasks/${encodeURIComponent(taskId)}`)
            .then(r => {
                if (!r.ok) throw new Error(`HTTP ${r.status}`);
                return r.json();
            })
            .then(data => {
                errorCount = 0;
                if (data.status === 'completed') {
                    clearInterval(interval);
                    updateTaskCard(cardEl, 'completed', data);
                } else if (data.status === 'failed') {
                    clearInterval(interval);
                    updateTaskCard(cardEl, 'failed', data.error || 'Task failed');
                }
            })
            .catch(() => {
                errorCount++;
                if (errorCount >= maxErrors) {
                    clearInterval(interval);
                    updateTaskCard(cardEl, 'failed', 'Connection error');
                }
            });
    }, 1500);
}

function updateTaskCard(cardEl, status, data) {
    if (!cardEl) return;
    const spinner = cardEl.querySelector('.bg-task-spinner');
    const statusEl = cardEl.querySelector('.bg-task-status');
    if (status === 'completed') {
        if (spinner) spinner.className = 'bg-task-done-icon';
        if (statusEl) statusEl.textContent = 'Ready!';
        cardEl.classList.add('bg-task-done');
        const viewBtn = document.createElement('button');
        viewBtn.className = 'bg-task-view-btn';
        viewBtn.textContent = 'Open in new tab';
        viewBtn.addEventListener('click', () => {
            const taskId = cardEl.dataset.taskId;
            window.open(`${window.location.origin}/viewer.html?task_id=${taskId}`, '_blank');
        });
        cardEl.appendChild(viewBtn);
        try {
            const taskId = cardEl.dataset.taskId;
            const url = `${window.location.origin}/viewer.html?task_id=${taskId}`;
            if (settings.autoOpenNewTabs) {
                const w = window.open(url, '_blank');
                if (!w) {
                    showToast('Result ready! Click "Open in new tab" to view.');
                }
            } else {
                showToast('Result ready! Click "Open in new tab" to view.');
            }
        } catch (_) {  }
    } else if (status === 'failed') {
        if (spinner) spinner.className = 'bg-task-fail-icon';
        if (statusEl) statusEl.textContent = typeof data === 'string' ? data : 'Failed';
        cardEl.classList.add('bg-task-failed');
    }
    scrollToBottom();
}

function openUrlInBackground(url) {
    if (!url) return;
    try {
        const a = document.createElement('a');
        a.href = url;
        a.target = '_blank';
        a.rel = 'noopener,noreferrer';
        const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
        const eventOptions = isMac ? { metaKey: true } : { ctrlKey: true };
        const evt = new MouseEvent('click', {
            bubbles: true,
            cancelable: true,
            view: window,
            ...eventOptions
        });
        a.dispatchEvent(evt);
    } catch (err) {
        console.error('[openUrlInBackground] failed:', err);
    }
}

function captureFrameAsBase64() {
    if (!camVideo || !camStream || camVideo.readyState < 2) return null;
    if (!camCanvas) return null;
    const w = camVideo.videoWidth;
    const h = camVideo.videoHeight;
    if (!w || !h || w < 64 || h < 64) return null;
    camCanvas.width = w;
    camCanvas.height = h;
    const ctx = camCanvas.getContext('2d');
    if (!ctx) return null;
    ctx.drawImage(camVideo, 0, 0, w, h);
    try {
        return camCanvas.toDataURL('image/jpeg', 0.85).split(',')[1];
    } catch (_) {
        return null;
    }
}

async function captureFrameAsBase64Safe() {
    if (!camVideo || !camStream || !camCanvas) return null;

    // Use ImageCapture API if available — most reliable method
    if (typeof ImageCapture !== 'undefined') {
        try {
            const track = camStream.getVideoTracks()[0];
            if (track && track.readyState === 'live') {
                const imageCapture = new ImageCapture(track);
                const blob = await imageCapture.takePhoto();
                return await new Promise((resolve) => {
                    const reader = new FileReader();
                    reader.onload = () => resolve(reader.result.split(',')[1]);
                    reader.onerror = () => resolve(null);
                    reader.readAsDataURL(blob);
                });
            }
        } catch (_) { /* fall through to canvas method */ }
    }

    // Canvas fallback
    return new Promise((resolve) => {
        const doCapture = () => {
            const w = camVideo.videoWidth;
            const h = camVideo.videoHeight;
            if (!w || !h || w < 64 || h < 64) { resolve(null); return; }
            camCanvas.width = w;
            camCanvas.height = h;
            const ctx = camCanvas.getContext('2d');
            if (!ctx) { resolve(null); return; }
            ctx.drawImage(camVideo, 0, 0, w, h);
            try {
                const b64 = camCanvas.toDataURL('image/jpeg', 0.9).split(',')[1];
                resolve(b64 || null);
            } catch (_) { resolve(null); }
        };

        if (camVideo.readyState < 2) {
            const onReady = () => { camVideo.removeEventListener('loadeddata', onReady); clearTimeout(t); setTimeout(doCapture, 200); };
            const t = setTimeout(() => { camVideo.removeEventListener('loadeddata', onReady); doCapture(); }, 4000);
            camVideo.addEventListener('loadeddata', onReady);
            return;
        }

        if (camVideo.videoWidth >= 64 && camVideo.videoHeight >= 64) {
            if (typeof camVideo.requestVideoFrameCallback === 'function') {
                camVideo.requestVideoFrameCallback(() => doCapture());
            } else {
                setTimeout(doCapture, 150);
            }
        } else {
            setTimeout(() => {
                if (camVideo.videoWidth >= 64 && camVideo.videoHeight >= 64) doCapture();
                else resolve(null);
            }, 500);
        }
    });
}

async function sendMessageWithImage(text, imgBase64) {
    if (!text && !imgBase64) return;
    if (isStreaming) {
        if (currentStreamController) {
            currentStreamController.abort();
            currentStreamController = null;
        }
        if (ttsPlayer) ttsPlayer.stop();
        isStreaming = false;
    }
    const messageToSend = text ? (text + ' ' + CAM_BYPASS_TOKEN) : CAM_BYPASS_TOKEN;
    const userAttachments = selectedFiles.map(f => ({
        name: f.name,
        type: f.type,
        size: f.size,
        previewUrl: f.previewUrl,
        isImage: f.isImage
    }));
    const payloadFiles = selectedFiles.map(f => ({
        name: f.name,
        type: f.type,
        size: f.size,
        data: f.base64
    }));
    addMessage('user', text || '(Image upload)', userAttachments);
    clearSelectedFiles();
    addTypingIndicator();
    isStreaming = true;
    if (sendBtn) sendBtn.disabled = true;
    if (messageInput) messageInput.disabled = true;
    if (orbContainer) orbContainer.classList.add('active');
    if (orb) {
        orb.setState('thinking');
        syncOrbClass('thinking');
        orb.setQueryType(null);
    }
    if (ttsPlayer) { ttsPlayer.reset(); ttsPlayer.unlock(); }
    let timeoutId = null;
    const controller = new AbortController();
    currentStreamController = controller;
    try {
        timeoutId = setTimeout(() => controller.abort(), 300000);
        // Upload the webcam frame to disk before calling the stream
        if (imgBase64) {
            try {
                const byteStr = atob(imgBase64);
                const arr = new Uint8Array(byteStr.length);
                for (let i = 0; i < byteStr.length; i++) arr[i] = byteStr.charCodeAt(i);
                const blob = new Blob([arr], { type: 'image/jpeg' });
                const formData = new FormData();
                formData.append('file', blob, 'webcam.jpg');
                await fetch(`${API}/api/upload`, { method: 'POST', body: formData });
            } catch (_) { /* non-fatal */ }
        }
        const res = await fetch(`${API}/chat/victor/stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: messageToSend,
                session_id: sessionId,
                tts: !!(ttsPlayer && ttsPlayer.enabled),
                imgbase64: imgBase64,
                files: payloadFiles.length > 0 ? payloadFiles : undefined,
                auto_open_tabs: !!settings.autoOpenNewTabs
            }),
            signal: controller.signal,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        removeTypingIndicator();
        const contentEl = addMessage('assistant', '');
        contentEl.innerHTML = '<span class="msg-stream-text">...</span>';
        scrollToBottom();
        if (!res.body) throw new Error('No response body');
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let sseBuffer = '';
        let fullResponse = '';
        let cursorEl = null;
        let streamDone = false;
        while (!streamDone) {
            const { done, value } = await reader.read();
            if (done) break;
            sseBuffer += decoder.decode(value, { stream: true });
            const lines = sseBuffer.split('\n\n');
            sseBuffer = lines.pop();
            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                try {
                    const data = JSON.parse(line.slice(6));
                    if (data.session_id) sessionId = data.session_id;
                    if (data.activity) {
                        appendActivity(data.activity);
                        if (activityToggle) activityToggle.style.display = '';
                        if (activityPanel && settings.autoOpenActivity) { activityPanel.classList.add('open'); updatePanelOverlay(); }
                    }
                    if (data.actions) handleActions(data.actions, contentEl);
                    if (data.background_tasks) handleBackgroundTasks(data.background_tasks, contentEl);
                    if ('chunk' in data) {
                        const chunkText = data.chunk || '';
                        fullResponse += chunkText;
                        const textSpan = contentEl.querySelector('.msg-stream-text');
                        if (textSpan) {
                            textSpan.textContent = fullResponse;
                            textSpan.classList.remove('stream-placeholder');
                        }
                        if (!cursorEl) {
                            cursorEl = document.createElement('span');
                            cursorEl.className = 'stream-cursor';
                            cursorEl.textContent = '|';
                            contentEl.appendChild(cursorEl);
                        }
                        scrollToBottom();
                    }
                    if (data.audio && ttsPlayer) ttsPlayer.enqueue(data.audio);
                    if (data.error) throw new Error(data.error);
                    if (data.done) { streamDone = true; break; }
                } catch (parseErr) {
                    if (parseErr.message && !parseErr.message.includes('JSON')) throw parseErr;
                }
            }
            if (streamDone) break;
        }
        if (cursorEl) cursorEl.remove();
        const textSpan = contentEl.querySelector('.msg-stream-text');
        if (textSpan && !fullResponse) textSpan.textContent = '(No response)';
    } catch (err) {
        clearTimeout(timeoutId);
        if (err.name === 'AbortError' && currentStreamController !== controller) return;
        removeTypingIndicator();
        addMessage('assistant', 'Something went wrong analyzing the image. Please try again.');
    } finally {
        clearTimeout(timeoutId);
        if (currentStreamController === controller) {
            currentStreamController = null;
            isStreaming = false;
            if (sendBtn) sendBtn.disabled = false;
            if (messageInput) {
                messageInput.disabled = false;
                messageInput.focus();
            }
            if (orbContainer) orbContainer.classList.remove('active');
            if (orb && !(ttsPlayer && ttsPlayer.playing)) orb.setState('idle');
        }
    }
}

async function checkHealth() {
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);
        const r = await fetch(`${API}/health`, { signal: controller.signal });
        clearTimeout(timeoutId);
        const d = await r.json().catch(() => null);
        const ok = d && (d.status === 'healthy' || d.status === 'degraded');
        if (statusDot) statusDot.classList.toggle('offline', !ok);
        if (statusText) statusText.textContent = ok ? 'Online' : 'Offline';
    } catch (e) {
        if (statusDot) statusDot.classList.add('offline');
        if (statusText) statusText.textContent = 'Offline';
        if (typeof console !== 'undefined' && console.warn) console.warn('[Health] Check failed:', e);
    }
}

function showToast(msg, durationMs = 5000) {
    if (!toastContainer || !msg) return;
    const el = document.createElement('div');
    el.className = 'toast';
    el.textContent = msg;
    toastContainer.appendChild(el);
    el.offsetHeight;
    el.classList.add('toast-visible');
    const t = setTimeout(() => {
        el.classList.remove('toast-visible');
        setTimeout(() => el.remove(), 300);
    }, durationMs);
    el.addEventListener('click', () => { clearTimeout(t); el.classList.remove('toast-visible'); setTimeout(() => el.remove(), 300); });
}

/* ================================================================
   Event Bindings
   ================================================================ */
function bindEvents() {
    if (sendBtn) sendBtn.addEventListener('click', () => { if (!isStreaming) sendMessage(); });
    if (messageInput) messageInput.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (!isStreaming) sendMessage(); }
    });
    if (messageInput) messageInput.addEventListener('input', () => {
        autoResizeInput();
        const len = messageInput.value.length;
        if (charCount) charCount.textContent = len > 100 ? `${len.toLocaleString()} / 32,000` : '';
    });
    if (camBtn) camBtn.addEventListener('click', () => {
        if (camStream) stopCamera();
        else startCamera();
    });
    initCameraPanel();
    if (micBtn) micBtn.addEventListener('click', () => {
        if (isListening) {
            autoListenMode = false;
            stopListening();
            if (micBtn) micBtn.classList.remove('auto-listen');
        } else {
            autoListenMode = true;
            speechErrorRetryCount = 0;
            if (micBtn) {
                micBtn.classList.add('auto-listen');
                micBtn.title = 'Voice input — click to stop auto-listen';
            }
            startListening();
        }
    });
    if (ttsBtn) ttsBtn.addEventListener('click', () => {
        if (ttsPlayer) ttsPlayer.enabled = !ttsPlayer.enabled;
        ttsBtn.classList.toggle('tts-active', ttsPlayer && ttsPlayer.enabled);
        if (ttsPlayer && !ttsPlayer.enabled) ttsPlayer.stop();
    });
    if (newChatBtn) newChatBtn.addEventListener('click', newChat);
    if (btnVictor) btnVictor.addEventListener('click', () => setMode('victor'));
    document.querySelectorAll('.chip').forEach(c => {
        c.addEventListener('click', () => { if (!isStreaming) sendMessage(c.dataset.msg); });
    });
    if (searchResultsToggle) {
        searchResultsToggle.addEventListener('click', () => {
            if (searchResultsWidget) { searchResultsWidget.classList.toggle('open'); updatePanelOverlay(); }
        });
    }
    if (searchResultsClose && searchResultsWidget) {
        searchResultsClose.addEventListener('click', () => { searchResultsWidget.classList.remove('open'); updatePanelOverlay(); });
    }
    if (activityToggle) {
        activityToggle.addEventListener('click', () => {
            if (activityPanel) { activityPanel.classList.toggle('open'); updatePanelOverlay(); }
        });
    }
    if (activityClose && activityPanel) {
        activityClose.addEventListener('click', () => { activityPanel.classList.remove('open'); updatePanelOverlay(); });
    }
    if (settingsBtn && settingsPanel) {
        settingsBtn.addEventListener('click', () => {
            settingsPanel.classList.toggle('open');
            updatePanelOverlay();
        });
    }
    if (settingsClose && settingsPanel) {
        settingsClose.addEventListener('click', () => {
            settingsPanel.classList.remove('open');
            updatePanelOverlay();
        });
    }
    if (toggleAutoActivity) {
        toggleAutoActivity.addEventListener('change', () => {
            settings.autoOpenActivity = toggleAutoActivity.checked;
            saveSettings();
        });
    }
    if (toggleAutoSearch) {
        toggleAutoSearch.addEventListener('change', () => {
            settings.autoOpenSearchResults = toggleAutoSearch.checked;
            saveSettings();
        });
    }
    if (toggleThinkingSounds) {
        toggleThinkingSounds.addEventListener('change', () => {
            settings.thinkingSounds = toggleThinkingSounds.checked;
            saveSettings();
        });
    }
    if (toggleVoiceInterrupt) {
        toggleVoiceInterrupt.addEventListener('change', () => {
            settings.voiceInterrupt = toggleVoiceInterrupt.checked;
            saveSettings();
        });
    }
    if (toggleAutoOpenTabs) {
        toggleAutoOpenTabs.addEventListener('change', () => {
            settings.autoOpenNewTabs = toggleAutoOpenTabs.checked;
            saveSettings();
        });
    }
    if (toggleProactiveBriefings) {
        toggleProactiveBriefings.addEventListener('change', () => {
            settings.proactiveBriefings = toggleProactiveBriefings.checked;
            saveSettings();
        });
    }
    if (panelOverlay) {
        panelOverlay.addEventListener('click', () => {
            if (activityPanel) activityPanel.classList.remove('open');
            if (searchResultsWidget) searchResultsWidget.classList.remove('open');
            if (settingsPanel) settingsPanel.classList.remove('open');
            updatePanelOverlay();
        });
    }

    /* ---- Upload button ---- */
    if (uploadBtn && fileInput) {
        uploadBtn.addEventListener('click', () => {
            if (!isStreaming) fileInput.click();
        });
    }
    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files.length > 0) {
                handleFileSelect(e.target.files);
                fileInput.value = '';
            }
        });
    }

    /* ---- Drag & Drop ---- */
    if (appEl) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            document.body.addEventListener(eventName, preventDefaults, false);
        });
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }
        document.body.addEventListener('dragenter', (e) => {
            dragCounter++;
            if (e.dataTransfer && e.dataTransfer.types && e.dataTransfer.types.includes('Files')) {
                if (dragOverlay) dragOverlay.classList.add('visible');
            }
        });
        document.body.addEventListener('dragleave', (e) => {
            dragCounter--;
            if (dragCounter <= 0) {
                dragCounter = 0;
                if (dragOverlay) dragOverlay.classList.remove('visible');
            }
        });
        document.body.addEventListener('drop', (e) => {
            dragCounter = 0;
            if (dragOverlay) dragOverlay.classList.remove('visible');
            if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                handleFileSelect(e.dataTransfer.files);
            }
        });
    }

    /* ---- Keyboard shortcut: Ctrl+U to upload ---- */
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'u' && !isStreaming) {
            e.preventDefault();
            if (fileInput) fileInput.click();
        }
    });
}

function autoResizeInput() {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
}

function updatePanelOverlay() {
    if (!panelOverlay) return;
    // Only engage the screen blocking mask for the centered configuration settings modal
    const modalOpen = (settingsPanel && settingsPanel.classList.contains('open'));
    panelOverlay.classList.toggle('visible', !!modalOpen);
}

function setMode(mode) {
    currentMode = mode || 'victor';
    if (btnVictor) btnVictor.classList.add('active');
    if (modeSlider) modeSlider.classList.remove('center', 'right');
    if (activityToggle) activityToggle.style.display = '';
}

/* ================================================================
   newChat — Reset everything including orb state
   ================================================================ */
function newChat() {
    if (ttsPlayer) ttsPlayer.stop();
    if (camStream) stopCamera();
    /* ---- Reset orb to idle and clear query type ---- */
    if (orb) {
        orb.setState('idle');
        syncOrbClass('idle');
        orb.setQueryType(null);
    }
    sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substring(2, 9);
    if (chatMessages) chatMessages.innerHTML = '';
    chatMessages.appendChild(createWelcome());
    messageInput.value = '';
    autoResizeInput();
    setGreeting();
    if (searchResultsWidget) searchResultsWidget.classList.remove('open');
    if (searchResultsToggle) searchResultsToggle.style.display = 'none';
    if (activityPanel) activityPanel.classList.remove('open');
    if (settingsPanel) settingsPanel.classList.remove('open');
    if (activityToggle) activityToggle.style.display = 'none';
    if (activityList) {
        activityList.innerHTML = '<div class="activity-empty" id="activity-empty">Send a message to see the flow here.</div>';
    }
    updatePanelOverlay();
}

function createWelcome() {
    const h = new Date().getHours();
    let g = 'Good evening.';
    if (h < 12) g = 'Good morning.';
    else if (h < 17) g = 'Good afternoon.';
    else if (h >= 22) g = 'Burning the midnight oil?';
    const div = document.createElement('div');
    div.className = 'welcome-screen';
    div.id = 'welcome-screen';
    div.innerHTML = `
        <div class="welcome-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
        </div>
        <h2 class="welcome-title">${g}</h2>
        <p class="welcome-sub">How may I assist you today?</p>
        <div class="welcome-chips">
            <button class="chip" data-msg="What can you do?">What can you do?</button>
            <button class="chip" data-msg="Open YouTube for me">Open YouTube</button>
            <button class="chip" data-msg="Tell me a fun fact">Fun fact</button>
            <button class="chip" data-msg="Play some music">Play music</button>
        </div>`;
    div.querySelectorAll('.chip').forEach(c => {
        c.addEventListener('click', () => { if (!isStreaming) sendMessage(c.dataset.msg); });
    });
    return div;
}

function isUrlLike(str) {
    if (!str || typeof str !== 'string') return false;
    const s = str.trim();
    return s.length > 40 && (/^https?:\/\//i.test(s));
}

function friendlyUrlLabel(url) {
    if (!url || typeof url !== 'string') return 'View source';
    try {
        const u = new URL(url.startsWith('http') ? url : 'https://' + url);
        const host = u.hostname.replace(/^www\./, '');
        const path = u.pathname !== '/' ? u.pathname.slice(0, 20) + (u.pathname.length > 20 ? '\u2026' : '') : '';
        return path ? host + path : host;
    } catch (_) {
        return url.length > 40 ? url.slice(0, 37) + '\u2026' : url;
    }
}

function truncateSnippet(text, maxLen) {
    if (!text || typeof text !== 'string') return '';
    const t = text.trim();
    if (t.length <= maxLen) return t;
    return t.slice(0, maxLen).trim() + '\u2026';
}

function renderSearchResults(payload) {
    if (!payload) return;
    if (searchResultsQuery) searchResultsQuery.textContent = (payload.query || '').trim() || 'Search';
    if (searchResultsAnswer) searchResultsAnswer.textContent = (payload.answer || '').trim() || '';
    if (!searchResultsList) return;
    searchResultsList.innerHTML = '';
    const results = payload.results || [];
    const maxContentLen = 220;
    for (const r of results) {
        let title = (r.title || '').trim();
        let content = (r.content || '').trim();
        const url = (r.url || '').trim();
        if (isUrlLike(title)) title = friendlyUrlLabel(url) || 'Source';
        if (!title) title = friendlyUrlLabel(url) || 'Source';
        if (isUrlLike(content)) content = '';
        content = truncateSnippet(content, maxContentLen);
        const score = r.score != null ? Math.round((r.score || 0) * 100) : null;
        const card = document.createElement('div');
        card.className = 'search-result-card';
        const urlDisplay = url ? escapeHtml(friendlyUrlLabel(url)) : '';
        const hrefSafe = safeUrlForHref(url);
        const urlMarkup = urlDisplay
            ? (hrefSafe ? `<a href="${hrefSafe}" target="_blank" rel="noopener" class="card-url" title="${escapeAttr(url)}">${urlDisplay}</a>` : `<span class="card-url">${urlDisplay}</span>`)
            : '';
        card.innerHTML = `
            <div class="card-title">${escapeHtml(title)}</div>
            ${content ? `<div class="card-content">${escapeHtml(content)}</div>` : ''}
            ${urlMarkup}
            ${score != null ? `<div class="card-score">Relevance: ${escapeHtml(String(score))}%</div>` : ''}`;
        searchResultsList.appendChild(card);
    }
}

function safeUrlForHref(url) {
    if (!url || typeof url !== 'string') return '';
    const u = url.trim();
    if (u.startsWith('https://') || u.startsWith('http://')) return escapeAttr(u);
    return '';
}

function escapeAttr(str) {
    if (typeof str !== 'string') return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

/* ================================================================
   ACTIVITY TRACKING — with orb query type integration
   ================================================================ */
const ACTIVITY_STEPS = {
    query_detected:      { step: 1, label: 'Query detected' },
    decision:            { step: 2, label: 'Primary Brain' },
    intent_classified:   { step: 3, label: 'Task Brain' },
    routing:             { step: 4, label: 'Route selected' },
    tasks_executing:     { step: 0, label: 'Executing tasks' },
    tasks_completed:     { step: 0, label: 'Tasks completed' },
    actions_emitted:     { step: 0, label: 'Actions sent' },
    vision_analyzing:    { step: 0, label: 'Analyzing image' },
    streaming_started:   { step: 5, label: 'Streaming response' },
    extracting_query:    { step: 0, label: 'Extracting query' },
    searching_web:       { step: 0, label: 'Searching web' },
    search_completed:    { step: 0, label: 'Search completed' },
    context_retrieved:   { step: 0, label: 'Context retrieved' },
    background_dispatched: { step: 0, label: 'Background tasks' },
    first_chunk:         { step: 6, label: 'Core responded' },
    /* ---- Frontend action logging ---- */
    opening_url:         { step: 0, label: 'Opening page' },
    playing_media:       { step: 0, label: 'Playing media' },
    google_search:       { step: 0, label: 'Google search' },
    youtube_search:      { step: 0, label: 'YouTube search' },
    executing_action:    { step: 0, label: 'Executing action' },
    action_complete:     { step: 0, label: 'Action complete' },
};

function appendActivity(activity) {
    if (!activityList || !activity) return;
    const item = document.createElement('div');
    item.className = 'activity-item';
    item.setAttribute('data-event', activity.event || '');
    const stepInfo = ACTIVITY_STEPS[activity.event] || { step: 0, label: activity.event || 'Activity', icon: 'dot' };
    let detail = '';
    const addRouteClass = (route) => {
        if (route === 'general') item.classList.add('route-general');
        else if (route === 'realtime') item.classList.add('route-realtime');
        else if (route === 'vision' || route === 'camera') item.classList.add('route-vision');
        else if (route === 'task') item.classList.add('route-task');
        else if (route === 'mixed') item.classList.add('route-task');
        else if (route === 'chat') item.classList.add('route-chat');
    };

    /* ---- Drive orb behavior from activity events ---- */
    if (activity.event === 'decision' && activity.query_type) {
        /* Set orb query type for color theming */
        if (orb) orb.setQueryType(activity.query_type);
    } else if (activity.event === 'streaming_started') {
        /* Transition from thinking to responding */
        if (orb) { orb.setState('responding'); syncOrbClass('responding'); }
    }

    if (activity.event === 'query_detected') {
        detail = activity.message || '';
    } else if (activity.event === 'decision') {
        const ms = activity.elapsed_ms;
        const timing = ms != null ? ` (${ms < 1000 ? ms + ' ms' : (ms / 1000).toFixed(2) + ' s'})` : '';
        const cat = (activity.query_type || '?').charAt(0).toUpperCase() + (activity.query_type || '').slice(1);
        detail = `${cat} — ${activity.reasoning || ''}${timing}`;
        addRouteClass(activity.query_type);
    } else if (activity.event === 'intent_classified') {
        detail = (activity.intent || '?').charAt(0).toUpperCase() + (activity.intent || '').slice(1);
        item.classList.add('activity-sub', 'route-task');
    } else if (activity.event === 'routing') {
        detail = `\u2192 ${(activity.route || '?').charAt(0).toUpperCase() + (activity.route || '').slice(1)}`;
        addRouteClass(activity.route);
    } else if (activity.event === 'tasks_executing') {
        detail = activity.message || 'Running tasks...';
        item.classList.add('activity-sub', 'route-task');
    } else if (activity.event === 'tasks_completed') {
        detail = activity.message || 'Completed';
        item.classList.add('activity-sub', 'route-task');
    } else if (activity.event === 'actions_emitted') {
        detail = activity.message || 'Actions sent';
        item.classList.add('activity-sub');
    } else if (activity.event === 'vision_analyzing') {
        detail = activity.message || 'Analyzing image...';
        item.classList.add('activity-sub', 'route-vision');
    } else if (activity.event === 'streaming_started') {
        detail = `Generating via ${(activity.route || '?').charAt(0).toUpperCase() + (activity.route || '').slice(1)}`;
        addRouteClass(activity.route);
    } else if (activity.event === 'first_chunk') {
        const ms = activity.elapsed_ms;
        detail = ms != null ? `Core responded in ${ms < 1000 ? ms + ' ms' : (ms / 1000).toFixed(2) + ' s'}` : 'Response started';
        addRouteClass(activity.route);
    } else if (activity.event === 'extracting_query') {
        detail = activity.message || 'Parsing your question for search...';
        item.classList.add('activity-sub');
    } else if (activity.event === 'searching_web') {
        detail = activity.message || (activity.query ? `Query: "${activity.query}"` : 'Scanning Pulse...');
        item.classList.add('activity-sub', 'route-realtime');
    } else if (activity.event === 'search_completed') {
        detail = activity.message || 'Search completed';
        item.classList.add('activity-sub', 'route-realtime');
    } else if (activity.event === 'context_retrieved') {
        detail = activity.message || 'Knowledge base ready';
        item.classList.add('activity-sub', 'route-general');
    } else if (activity.event === 'opening_url') {
        detail = activity.message || 'Opening page...';
        item.classList.add('activity-sub', 'route-action');
    } else if (activity.event === 'playing_media') {
        detail = activity.message || 'Playing media...';
        item.classList.add('activity-sub', 'route-action');
    } else if (activity.event === 'google_search') {
        detail = activity.message || 'Google search...';
        item.classList.add('activity-sub', 'route-realtime');
    } else if (activity.event === 'youtube_search') {
        detail = activity.message || 'YouTube search...';
        item.classList.add('activity-sub', 'route-realtime');
    } else if (activity.event === 'executing_action') {
        detail = activity.message || 'Executing action...';
        item.classList.add('activity-sub', 'route-task');
    } else if (activity.event === 'action_complete') {
        detail = activity.message || 'Action complete';
        item.classList.add('route-success');
    } else {
        detail = activity.message || (typeof activity === 'object' ? JSON.stringify(activity) : String(activity));
    }
    const stepNum = stepInfo.step ? `<span class="activity-step">${stepInfo.step}</span>` : '';
    item.innerHTML = `
        <div class="activity-event">${stepNum}${escapeHtml(stepInfo.label)}</div>
        <div class="activity-detail">${escapeHtml(detail || '')}</div>`;
    const emptyEl = activityList.querySelector('.activity-empty');
    if (emptyEl) emptyEl.style.display = 'none';
    activityList.appendChild(item);
    activityList.scrollTop = activityList.scrollHeight;
}

function escapeHtml(str) {
    if (typeof str !== 'string') return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function hideWelcome() {
    const w = document.getElementById('welcome-screen');
    if (w) w.remove();
}

const AVATAR_ICON_USER = '<svg class="msg-avatar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>';
const AVATAR_ICON_ASSISTANT = '<svg class="msg-avatar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><circle cx="9" cy="16" r="1" fill="currentColor"/><circle cx="15" cy="16" r="1" fill="currentColor"/></svg>';

function addMessage(role, text, attachments) {
    hideWelcome();
    const msg = document.createElement('div');
    msg.className = `message ${role}`;
    const avatar = document.createElement('div');
    avatar.className = 'msg-avatar';
    avatar.innerHTML = role === 'assistant' ? AVATAR_ICON_ASSISTANT : AVATAR_ICON_USER;
    const body = document.createElement('div');
    body.className = 'msg-body';
    const label = document.createElement('div');
    label.className = 'msg-label';
    label.textContent = role === 'assistant'
        ? `VICTOR  (${currentMode === 'victor' ? 'VICTOR' : currentMode === 'realtime' ? 'Realtime' : 'General'})`
        : 'You';
    const content = document.createElement('div');
    content.className = 'msg-content';
    content.textContent = text;
    body.appendChild(label);
    body.appendChild(content);
    if (attachments && attachments.length > 0) {
        addFileAttachments(body, attachments);
    }
    msg.appendChild(avatar);
    msg.appendChild(body);
    chatMessages.appendChild(msg);
    scrollToBottom();
    return content;
}

function addTypingIndicator() {
    hideWelcome();
    const msg = document.createElement('div');
    msg.className = 'message assistant';
    msg.id = 'typing-msg';
    const avatar = document.createElement('div');
    avatar.className = 'msg-avatar';
    avatar.innerHTML = AVATAR_ICON_ASSISTANT;
    const body = document.createElement('div');
    body.className = 'msg-body';
    const label = document.createElement('div');
    label.className = 'msg-label';
    label.textContent = `VICTOR  (${currentMode === 'victor' ? 'VICTOR' : currentMode === 'realtime' ? 'Realtime' : 'General'})`;
    const content = document.createElement('div');
    content.className = 'msg-content';
    // Animated pulsing dots — visible immediately on Enter
    content.innerHTML = '<span class="msg-stream-text"><span class="victor-thinking-dots"><span></span><span></span><span></span></span></span>';
    body.appendChild(label);
    body.appendChild(content);
    msg.appendChild(avatar);
    msg.appendChild(body);
    chatMessages.appendChild(msg);
    scrollToBottom();
    return content;
}

function removeTypingIndicator() {
    const t = document.getElementById('typing-msg');
    if (t) t.remove();
}

function scrollToBottom() {
    requestAnimationFrame(() => {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    });
}

/* ================================================================
   sendMessage — Main message flow with orb state management
   ================================================================ */
async function sendMessage(textOverride) {
    let text = (textOverride || messageInput.value).trim();
    const visionModeOn = camVisionModeInput && camVisionModeInput.checked;
    const wantsCamera = visionModeOn || isCameraQuery(text);
    const hasFiles = selectedFiles.length > 0;
    if (wantsCamera && !text) text = 'What do you see?';
    if (isStreaming) {
        if (!text && !hasFiles) return;
        if (currentStreamController) {
            currentStreamController.abort();
            currentStreamController = null;
        }
        if (ttsPlayer) ttsPlayer.stop();
        isStreaming = false;
    } else if (!text && !hasFiles) {
        return;
    }
    if (isListening) {
        pendingSendTranscript = null;
        latestTranscript = '';
        clearTimeout(speechSendTimeout);
        speechSendTimeout = null;
        stopListening();
    }
    if ((isCameraQuery(text) || visionModeOn) && !camStream) {
        try {
            await startCamera();
            // Wait until video dimensions are valid
            await new Promise((resolve) => {
                if (!camVideo) { resolve(); return; }
                if (camVideo.readyState >= 2 && camVideo.videoWidth > 0 && camVideo.videoHeight > 0) {
                    resolve(); return;
                }
                const onReady = () => { camVideo.removeEventListener('loadeddata', onReady); clearTimeout(t); resolve(); };
                const t = setTimeout(() => { camVideo.removeEventListener('loadeddata', onReady); resolve(); }, 5000);
                camVideo.addEventListener('loadeddata', onReady);
            });
            // Camera sensor warmup
            await new Promise(r => setTimeout(r, 800));
        } catch (_) {}
    } else if (camStream && wantsCamera) {
        // Camera already running — still give a brief moment for the frame to be fresh
        await new Promise(r => setTimeout(r, 200));
    }

    let imgBase64 = null;
    let uploadedSuccessfully = false;
    if (camStream && wantsCamera) {
        // Try capture up to 4 times
        for (let attempt = 0; attempt < 4; attempt++) {
            imgBase64 = await captureFrameAsBase64Safe();
            if (imgBase64) break;
            await new Promise(r => setTimeout(r, 500));
        }
        if (imgBase64) {
            // Upload image to disk immediately — if this succeeds, token will be in the message
            try {
                const byteStr = atob(imgBase64);
                const arr = new Uint8Array(byteStr.length);
                for (let i = 0; i < byteStr.length; i++) arr[i] = byteStr.charCodeAt(i);
                const blob = new Blob([arr], { type: 'image/jpeg' });
                const formData = new FormData();
                formData.append('file', blob, 'webcam.jpg');
                const upRes = await fetch(`${API}/api/upload`, { method: 'POST', body: formData });
                uploadedSuccessfully = upRes.ok;
            } catch (_) {}
            if (!uploadedSuccessfully) {
                imgBase64 = null; // Don't send token if upload failed
                showToast('Camera upload failed. Please try again.');
            }
        } else {
            showToast('Camera frame not ready. Please try again.');
        }
    }

    // Build user-visible attachments for rendering
    const userAttachments = selectedFiles.map(f => ({
        name: f.name,
        type: f.type,
        size: f.size,
        previewUrl: f.previewUrl,
        isImage: f.isImage
    }));
    // Build payload files (base64 stripped)
    const payloadFiles = selectedFiles.map(f => ({
        name: f.name,
        type: f.type,
        size: f.size,
        data: f.base64
    }));
    messageInput.value = '';
    autoResizeInput();
    charCount.textContent = '';
    if (text !== "INIT_AUTONOMOUS_STARTUP_SEQUENCE") {
        addMessage('user', text || '(File upload)', userAttachments);
    }
    clearSelectedFiles();
    addTypingIndicator();
    isStreaming = true;
    if (sendBtn) sendBtn.disabled = true;
    if (messageInput) messageInput.disabled = true;
    if (orbContainer) orbContainer.classList.add('active');
    /* ---- Set orb to thinking state ---- */
    if (orb) {
        orb.setState('thinking');
        syncOrbClass('thinking');
        orb.setQueryType(null);
    }
    if (ttsPlayer) { ttsPlayer.reset(); ttsPlayer.unlock(); }
    const messageToSend = imgBase64 ? (text + ' ' + CAM_BYPASS_TOKEN) : text;
    const endpoint = '/chat/victor/stream';
    if (activityList) {
        activityList.innerHTML = '<div class="activity-empty" id="activity-empty">Processing...</div>';
        if (activityToggle) activityToggle.style.display = '';
        if (activityPanel && settings.autoOpenActivity) { activityPanel.classList.add('open'); updatePanelOverlay(); }
    }
    let firstChunkReceived = false;
    let timeoutId = null;
    const controller = new AbortController();
    currentStreamController = controller;
    try {
        if (ttsPlayer?.enabled && settings.thinkingSounds && preStarterPlayer) {
            preStarterPlayer.play(() => {});
        }


        timeoutId = setTimeout(() => controller.abort(), 300000);

        const res = await fetch(`${API}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: messageToSend,
                user_input: messageToSend === "INIT_AUTONOMOUS_STARTUP_SEQUENCE" ? "INIT_AUTONOMOUS_STARTUP_SEQUENCE" : undefined,
                session_id: sessionId,
                tts: !!(ttsPlayer && ttsPlayer.enabled),
                imgbase64: imgBase64 || null,
                files: payloadFiles.length > 0 ? payloadFiles : undefined,
                auto_open_tabs: !!settings.autoOpenNewTabs
            }),
            signal: controller.signal,
        });
        if (!res.ok) {
            let errMsg = `HTTP ${res.status}`;
            try {
                const err = await res.json();
                errMsg = err.detail || (Array.isArray(err.detail) ? err.detail.map(d => d.msg || d.loc?.join('.')).join('; ') : err.message) || errMsg;
            } catch (_) {}
            throw new Error(errMsg);
        }
        // Reuse the typing bubble in-place as the reply bubble — zero flicker, zero gap
        const typingMsg = document.getElementById('typing-msg');
        let contentEl;
        if (typingMsg) {
            typingMsg.removeAttribute('id'); // detach so removeTypingIndicator won't kill it later
            contentEl = typingMsg.querySelector('.msg-content');
        } else {
            contentEl = addMessage('assistant', '');
            contentEl.innerHTML = '<span class="msg-stream-text"><span class="victor-thinking-dots"><span></span><span></span><span></span></span></span>';
        }
        scrollToBottom();
        if (!res.body) throw new Error('No response body');

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let sseBuffer = '';
        let fullResponse = '';
        latestAiSpeech = '';
        let cursorEl = null;
        let streamDone = false;
        while (!streamDone) {
            const { done, value } = await reader.read();
            if (done) break;
            sseBuffer += decoder.decode(value, { stream: true });
            const lines = sseBuffer.split('\n\n');
            sseBuffer = lines.pop();
            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                try {
                    const data = JSON.parse(line.slice(6));
                    if (data.session_id) sessionId = data.session_id;
                    if (data.activity) {
                        appendActivity(data.activity);
                        if (activityToggle) activityToggle.style.display = '';
                        if (activityPanel && settings.autoOpenActivity) { activityPanel.classList.add('open'); updatePanelOverlay(); }
                    }
                    if (data.search_results) {
                        renderSearchResults(data.search_results);
                        if (searchResultsToggle) searchResultsToggle.style.display = '';
                        if (searchResultsWidget && settings.autoOpenSearchResults) { searchResultsWidget.classList.add('open'); updatePanelOverlay(); }
                    }
                    if (data.actions) {
                        handleActions(data.actions, contentEl);
                    }
                    if (data.background_tasks) {
                        handleBackgroundTasks(data.background_tasks, contentEl);
                    }
                    if ('chunk' in data) {
                        const chunkText = data.chunk || '';
                        if (chunkText && !firstChunkReceived) {
                            firstChunkReceived = true;
                            if (ttsPlayer) ttsPlayer.reset();
                        }
                        fullResponse += chunkText;
                        latestAiSpeech = fullResponse;
                        const textSpan = contentEl.querySelector('.msg-stream-text');
                        if (textSpan) {
                            // First chunk: clear pulsing dots and start real streamed content
                            if (!firstChunkReceived) {
                                textSpan.innerHTML = '';
                            }
                            firstChunkReceived = true;
                            textSpan.textContent = fullResponse;
                            textSpan.classList.remove('stream-placeholder');
                        }
                        if (!cursorEl) {
                            cursorEl = document.createElement('span');
                            cursorEl.className = 'stream-cursor';
                            cursorEl.textContent = '|';
                            contentEl.appendChild(cursorEl);
                        }
                        scrollToBottom();
                    }
                    if (data.audio && ttsPlayer) {
                        ttsPlayer.enqueue(data.audio);
                    }
                    if (data.error) throw new Error(data.error);
                    if (data.done) { streamDone = true; break; }
                } catch (parseErr) {
                    if (parseErr.message && !parseErr.message.includes('JSON'))
                        throw parseErr;
                }
            }
            if (streamDone) break;
        }
        if (cursorEl) cursorEl.remove();
        const textSpan = contentEl.querySelector('.msg-stream-text');
        if (textSpan && !fullResponse) textSpan.textContent = '(No response)';
    } catch (err) {
        clearTimeout(timeoutId);
        if (err.name === 'AbortError' && currentStreamController !== controller) return;
        removeTypingIndicator();
        let msg = 'Something went wrong. Please try again.';
        if (err.name === 'AbortError') {
            msg = 'Request timed out. Please try again.';
        } else if (err.message && err.message.includes('503')) {
            msg = 'Service temporarily unavailable. Please try again in a moment.';
        } else if (err.message && err.message.includes('429')) {
            msg = 'Rate limit reached. Please wait a moment before trying again.';
        } else if (err.message && err.message.length > 0) {
            msg = err.message.length > 100 ? err.message.slice(0, 97) + '...' : err.message;
        }
        addMessage('assistant', msg);
        showToast(msg, 6000);
    } finally {
        clearTimeout(timeoutId);
        if (currentStreamController === controller) {
            currentStreamController = null;
            isStreaming = false;
            if (sendBtn) sendBtn.disabled = false;
            if (messageInput) {
                messageInput.disabled = false;
                messageInput.focus();
            }
            if (orbContainer) orbContainer.classList.remove('active');
            /* ---- Reset orb to idle (only if TTS is not still playing) ---- */
            if (orb && !(ttsPlayer && ttsPlayer.playing)) {
                orb.setState('idle');
                syncOrbClass('idle');
            }
            maybeRestartListening();
        }
    }
}

let lastProactiveTime = Date.now();
function initProactiveCheck() {
    setInterval(async () => {
        if (!settings.proactiveBriefings) return;
        if (isStreaming || (ttsPlayer && ttsPlayer.playing)) {
            return;
        }
        const now = Date.now();
        if (now - lastProactiveTime < 180000) {
            return;
        }
        try {
            const res = await fetch(`${API}/chat/victor/proactive`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: sessionId,
                    tts: !!(ttsPlayer && ttsPlayer.enabled)
                })
            });
            if (res.ok) {
                const data = await res.json();
                if (data && data.should_activate) {
                    lastProactiveTime = Date.now();
                    sendMessage(`TRIGGER_PROACTIVE_BRIEFING: ${data.reason}`);
                }
            }
        } catch (e) {
            console.error("Proactive check failed:", e);
        }
    }, 60000);
}

document.addEventListener('DOMContentLoaded', init);
