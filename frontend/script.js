document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatContainer = document.getElementById('chat-container');
    const sendBtn = document.getElementById('send-btn');
    
    // Generate a simple session ID
    const sessionId = 'session_' + Math.random().toString(36).substring(2, 10);

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const message = chatInput.value.trim();
        if (!message) return;
        
        // Append user message
        appendMessage('user', message);
        
        // Clear input & disable button
        chatInput.value = '';
        sendBtn.disabled = true;
        
        // Trigger Orb Processing Mode
        if (window.setOrbState) window.setOrbState('processing');
        
        try {
            // Call FastAPI backend
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: message,
                    session_id: sessionId
                })
            });
            
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}`);
            }
            
            const data = await response.json();
            
            // Append VICTOR response
            appendMessage('victor', data.response);
            
        } catch (error) {
            console.error('Error fetching chat response:', error);
            appendMessage('error', 'Connection error. VICTOR backend might be unreachable.');
        } finally {
            // Re-enable button and focus input
            sendBtn.disabled = false;
            chatInput.focus();
            scrollToBottom();
            
            // Revert Orb State
            if (window.setOrbState) window.setOrbState('default');
        }
    });
    
    function appendMessage(role, text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        // Simple line break replacement
        contentDiv.innerHTML = text.replace(/\n/g, '<br>');
        
        messageDiv.appendChild(contentDiv);
        chatContainer.appendChild(messageDiv);
        
        scrollToBottom();
    }
    
    function scrollToBottom() {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
});
