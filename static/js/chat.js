async function sendMessage(event) {
    event.preventDefault();

    const input = document.getElementById('messageInput');
    const message = input.value.trim();

    if (!message) return;

    // Hide welcome banner
    const banner = document.getElementById('welcomeBanner');
    if (banner) {
        banner.style.display = 'none';
    }

    // Disable input
    input.disabled = true;
    document.getElementById('sendBtn').disabled = true;
    document.getElementById('loading').style.display = 'block';

    // Add user message to UI
    addMessageToUI('user', message);
    input.value = '';

    try {
        const response = await fetch('/api/send_message', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });

        const data = await response.json();

        // Add assistant response with separate references
        addMessageToUI('assistant', data.answer, data.references);

    } catch (error) {
        console.error('Error:', error);
        addMessageToUI('assistant', 'Sorry, something went wrong. Please try again.');
    }

    // Re-enable input
    input.disabled = false;
    document.getElementById('sendBtn').disabled = false;
    document.getElementById('loading').style.display = 'none';
    input.focus();
}

function addMessageToUI(role, content, references = null) {
    const messagesDiv = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    if (role === 'assistant') {
        // Render content as markdown
        contentDiv.innerHTML = marked.parse(content);
        
        // Add references if provided
        if (references) {
            const referencesDiv = document.createElement('div');
            referencesDiv.className = 'references';
            referencesDiv.innerHTML = marked.parse(references);
            contentDiv.appendChild(referencesDiv);
        }
    } else {
        contentDiv.textContent = content;
    }

    messageDiv.appendChild(contentDiv);
    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

async function createNewChat() {
    const response = await fetch('/api/new_chat', { method: 'POST' });
    const data = await response.json();
    location.reload();
}

async function loadSession(sessionId) {
    await fetch(`/api/load_session/${sessionId}`, { method: 'GET' });
    location.reload();
}

async function deleteSession(event, sessionId) {
    event.stopPropagation();

    if (!confirm('Are you sure you want to delete this chat?')) return;

    await fetch(`/api/delete_session/${sessionId}`, { method: 'DELETE' });
    location.reload();
}

// Auto-scroll to bottom on load
document.getElementById('chatMessages').scrollTop = document.getElementById('chatMessages').scrollHeight;

// Hide welcome banner if there are any messages
const messagesDiv = document.getElementById('chatMessages');
const hasMessages = messagesDiv.querySelectorAll('.message').length > 0;
const banner = document.getElementById('welcomeBanner');
if (banner && hasMessages) {
    banner.style.display = 'none';
}

// Render historical messages with markdown
document.querySelectorAll('.message[data-content]').forEach(msgDiv => {
    const role = msgDiv.dataset.role;
    const content = msgDiv.dataset.content;
    const contentDiv = msgDiv.querySelector('.message-content');
    
    if (role === 'assistant') {
        // Split by References if it exists
        const parts = content.split('\n\nReferences:');
        contentDiv.innerHTML = marked.parse(parts[0]);
        
        if (parts.length > 1) {
            const referencesDiv = document.createElement('div');
            referencesDiv.className = 'references';
            referencesDiv.innerHTML = marked.parse('References:' + parts[1]);
            contentDiv.appendChild(referencesDiv);
        }
    } else {
        contentDiv.textContent = content;
    }
});