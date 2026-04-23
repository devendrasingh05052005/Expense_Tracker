// ─── Simple Chatbot ─────────────────────────────────────────────────────
const aiFab = document.getElementById('ai-fab');
const chatModal = document.getElementById('ai-chat-modal');
const chatInput = document.getElementById('chat-input');
const chatSend = document.getElementById('chat-send');
const chatMessages = document.getElementById('chat-messages');

let chatTyping = false;
let aiAgentUrl = '/ai-agent/';

// Simple chatbot functions
function toggleAiChat() {
  console.log('🔥 toggleAiChat called');
  
  if (chatModal) {
    chatModal.style.display = chatModal.style.display === 'none' ? 'block' : 'none';
    console.log('🎯 Modal toggled:', chatModal.style.display);
    
    if (chatInput) {
      chatInput.focus();
    }
  }
}

function closeAiChat() {
  if (chatModal) {
    chatModal.style.display = 'none';
    if (chatInput) {
      chatInput.blur();
    }
  }
}

function sendChatMessage() {
  console.log('📤 sendChatMessage called');
  
  if (!chatInput || !chatMessages) {
    console.error('❌ Chat elements not found');
    return;
  }

  const message = chatInput.value.trim();
  if (!message) {
    console.log('⚠️ Empty message');
    return;
  }

  console.log('📝 Sending message:', message);
  
  // Clear input
  chatInput.value = '';
  
  // Add user message
  const userMsgDiv = document.createElement('div');
  userMsgDiv.className = 'message user';
  userMsgDiv.textContent = message;
  chatMessages.appendChild(userMsgDiv);
  
  // Show typing indicator
  const typingDiv = document.createElement('div');
  typingDiv.className = 'message ai typing';
  typingDiv.textContent = '🤖 AI is typing...';
  chatMessages.appendChild(typingDiv);
  
  // Scroll to bottom
  chatMessages.scrollTop = chatMessages.scrollHeight;
  
  // Send to AI agent
  fetch(aiAgentUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCookie('csrftoken')
    },
    body: JSON.stringify({
      message: message,
      session_id: 'session_' + Date.now()
    })
  })
  .then(response => response.json())
  .then(data => {
    // Remove typing indicator
    const typingIndicator = chatMessages.querySelector('.typing');
    if (typingIndicator) {
      typingIndicator.remove();
    }
    
    // Add AI response
    const aiMsgDiv = document.createElement('div');
    aiMsgDiv.className = 'message ai';
    aiMsgDiv.textContent = data.response || 'Sorry, I could not process that.';
    chatMessages.appendChild(aiMsgDiv);
    
    // Scroll to working
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    console.log('✅ AI Response:', data.response);
  })
  .catch(error => {
    console.error('❌ Chat error:', error);
    
    // Remove typing indicator
    const typingIndicator = chatMessages.querySelector('.typing');
    if (typingIndicator) {
      typingIndicator.remove();
    }
    
    // Add error message
    const errorDiv = document.createElement('div');
    errorDiv.className = 'message ai error';
    errorDiv.textContent = '❌ Error: ' + error.message;
    chatMessages.appendChild(errorDiv);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
  });
}

// Helper function to get CSRF token
function getCookie(name) {
  const value = '; ' + document.cookie;
  const parts = value.split('; ' + name + '=');
  return parts.pop().split('=').pop();
}

// Attach event listeners
if (aiFab) {
  aiFab.addEventListener('click', toggleAiChat);
}

if (chatSend) {
  chatSend.addEventListener('click', sendChatMessage);
}

if (chatInput) {
  chatInput.addEventListener('keypress', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      sendChatMessage();
    }
  });
}
