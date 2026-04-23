// ─── Alert dismissal ──────────────────────────────────────────────────────────
document.querySelectorAll('.alert-close').forEach(btn => {
  btn.addEventListener('click', () => btn.closest('.alert').remove());
});

// ─── Sidebar toggle (mobile) ──────────────────────────────────────────────────
const sidebar   = document.querySelector('.sidebar');
const hamburger = document.querySelector('.hamburger');
const overlay   = document.createElement('div');
overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:99;display:none';
document.body.appendChild(overlay);

hamburger?.addEventListener('click', () => {
  sidebar.classList.toggle('open');
  overlay.style.display = sidebar.classList.contains('open') ? 'block' : 'none';
});
overlay.addEventListener('click', () => {
  sidebar.classList.remove('open');
  overlay.style.display = 'none';
});

// ─── Upload drag-and-drop ──────────────────────────────────────────────────────
const zone = document.querySelector('.upload-zone');
const fileInput = document.getElementById('id_file');

zone?.addEventListener('click', () => fileInput?.click());
zone?.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
zone?.addEventListener('dragleave', () => zone.classList.remove('dragover'));
zone?.addEventListener('drop', e => {
  e.preventDefault();
  zone.classList.remove('dragover');
  const dt = new DataTransfer();
  dt.items.add(e.dataTransfer.files[0]);
  fileInput.files = dt.files;
  previewFile(e.dataTransfer.files[0]);
});
fileInput?.addEventListener('change', () => previewFile(fileInput.files[0]));

// Auto-style upload zone file input
if (fileInput && zone) {
  fileInput.style.cssText = 'position:absolute;inset:0;opacity:0;cursor:pointer;width:100%;height:100%';
  zone.style.position = 'relative';
}

function previewFile(file) {
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => {
    let preview = document.getElementById('img-preview');
    if (!preview) {
      preview = document.createElement('div');
      preview.id = 'img-preview';
      preview.className = 'receipt-preview';
      preview.innerHTML = '<img id="preview-img" src="" alt="Receipt preview">';
      zone.after(preview);
    }
    document.getElementById('preview-img').src = e.target.result;
    zone.querySelector('p').textContent = `Selected: ${file.name}`;
  };
  reader.readAsDataURL(file);
}

// ─── Auto-dismiss alerts ──────────────────────────────────────────────────────
setTimeout(() => {
  document.querySelectorAll('.alert').forEach(a => {
    a.style.transition = 'opacity .5s';
    a.style.opacity = '0';
    setTimeout(() => a.remove(), 500);
  });
}, 4000);

// ─── AI Chat ───────────────────────────────────────────────────────────────────
const chatToggle = document.getElementById('chat-toggle');
const chatModal = document.getElementById('ai-chat-modal');
const chatPanel = document.getElementById('ai-chat-modal');
const chatClose = document.getElementById('chat-close');
const chatInput = document.getElementById('chat-input');
const chatSend = document.getElementById('chat-send');
const chatMessages = document.getElementById('chat-messages');
const aiFab = document.getElementById('ai-fab');

let chatTyping = false;
let aiAgentUrl = '/ai-agent/'; // default URL

// Get URL from data attribute
if (chatPanel && chatPanel.dataset.aiAgentUrl) {
  aiAgentUrl = chatPanel.dataset.aiAgentUrl;
  console.log('AI Agent URL from template:', aiAgentUrl);
}

console.log('Initializing chat components...');
console.log('chatToggle:', !!chatToggle);
console.log('chatModal:', !!chatModal);
console.log('chatPanel:', !!chatPanel);
console.log('chatInput:', !!chatInput);
console.log('chatSend:', !!chatSend);
console.log('chatMessages:', !!chatMessages);

// FAB toggle + modal support
function toggleAiChat() {
  console.log('🔥 toggleAiChat() called');
  
  if (chatModal) {
    const isHidden = !chatModal.classList.contains('open');
    console.log('📍 Modal found, current state:', isHidden ? 'hidden' : 'visible');
    console.log('🎯 Modal element:', chatModal);
    console.log('🎯 Modal classes:', chatModal.className);
    
    if (isHidden) {
      console.log('🔥 Opening modal...');
      chatModal.classList.add('open');
      document.addEventListener('keydown', onKeyDown);
      if (chatInput) setTimeout(() => chatInput.focus(), 150);
      console.log('✅ Modal opened successfully');
    } else {
      console.log('🔥 Closing modal...');
      closeAiChat();
      console.log('✅ Modal closed successfully');
    }
  } else {
    console.error('❌ Chat modal not found!');
    console.error('❌ Looking for element with ID: ai-chat-modal');
    
    // Try to find modal with any method
    const modalTest = document.getElementById('ai-chat-modal');
    const modalTest2 = document.querySelector('.ai-chat-modal');
    const modalTest3 = document.querySelector('#ai-chat-modal');
    
    console.log('🧪 Alternative modal tests:');
    console.log('  - ID selector:', !!modalTest);
    console.log('  - Class selector:', !!modalTest2);
    console.log('  - Hash selector:', !!modalTest3);
    
    // Try manual modal creation if needed
    if (!modalTest && !modalTest2 && !modalTest3) {
      console.log('⚠️ Creating fallback modal...');
      const fallbackModal = document.createElement('div');
      fallbackModal.id = 'ai-chat-modal';
      fallbackModal.className = 'ai-chat-modal';
      fallbackModal.innerHTML = '<div class="modal-backdrop"></div><div class="ai-chat-container"><div class="ai-chat-header"><div>🤖 Expense AI Agent</div><button id="chat-close" class="chat-close">&times;</button></div><div id="chat-messages" class="ai-chat-messages"><div class="message ai">Chatbot loaded!</div></div><div class="ai-chat-input"><input id="chat-input" type="text" placeholder="Type message..." autocomplete="off"><button id="chat-send" class="btn btn-primary btn-sm">Send</button></div></div></div>';
      document.body.appendChild(fallbackModal);
      console.log('✅ Fallback modal created and attached');
    }
  }
}

function closeAiChat() {
  chatModal?.classList.remove('open');
  document.removeEventListener('keydown', onKeyDown);
  chatInput?.blur();
}

function onKeyDown(e) {
  if (e.key === 'Escape') closeAiChat();
}

if (aiFab) {
  console.log('✅ FAB found, attaching toggle');
  console.log('📍 FAB element:', aiFab);
  console.log('🎯 FAB ID:', aiFab.id);
  console.log('🎯 FAB Class:', aiFab.className);
  
  aiFab.addEventListener('click', (e) => {
    console.log('🔥 FAB CLICKED!', e);
    console.log('🎯 Click target:', e.target);
    console.log('🎯 Current event phase:', e.eventPhase);
    e.stopPropagation();
    toggleAiChat();
  });
  
  // Test if button is actually visible
  const rect = aiFab.getBoundingClientRect();
  console.log('📏 FAB Position:', rect);
  console.log('📏 FAB Visible:', rect.width > 0 && rect.height > 0);
  
} else {
  console.error('❌ FAB element not found!');
  console.error('❌ Looking for element with ID: ai-fab');
  
  // Check if element exists with different selector
  const altFab = document.querySelector('[id="ai-fab"]');
  if (altFab) {
    console.log('✅ Found FAB with alternative selector:', altFab);
  } else {
    console.error('❌ No FAB element found anywhere!');
  }
}

if (chatClose2) {
  chatClose2.addEventListener('click', closeAiChat);
}

if (chatSend) {
  console.log('✅ Send button found, attaching handler');
  console.log('📍 Send button element:', chatSend);
  console.log('🎯 Send button ID:', chatSend.id);
  console.log('🎯 Send button classes:', chatSend.className);
  
  chatSend.addEventListener('click', function(e) {
    console.log('🔥 SEND BUTTON CLICKED!', e);
    console.log('🎯 Click target:', e.target);
    console.log('🎯 Current event phase:', e.eventPhase);
    console.log('🎯 Button disabled state:', chatSend.disabled);
    
    e.preventDefault();
    e.stopPropagation();
    console.log('📤 Calling sendChatMessage()...');
    
    // Simple test to verify function is called
    alert('🧪 SEND BUTTON CLICKED! Function is working!');
    
    sendChatMessage();
  });
  
  // Test if button is actually visible and clickable
  const sendRect = chatSend.getBoundingClientRect();
  console.log('📏 Send button position:', sendRect);
  console.log('📏 Send button visible:', sendRect.width > 0 && sendRect.height > 0);
  
} else {
  console.error('❌ Send button not found!');
  console.error('❌ Looking for element with ID: chat-send');
}

if (chatInput) {
  chatInput.addEventListener('keypress', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      console.log('Enter key pressed in input');
      sendChatMessage();
    }
    if (e.key === 'Escape') {
      if (chatPanel) {
        chatPanel.style.display = 'none';
        console.log('Escape key - closing chat panel');
      }
    }
  });
}

// Add test button for debugging
function addTestButton() {
  const testBtn = document.createElement('button');
  testBtn.textContent = '🧪 Test AI Agent';
  testBtn.style.cssText = 'position:fixed;top:10px;right:10px;z-index:9999;background:#ff6b6b;color:white;padding:10px;border:none;border-radius:5px;cursor:pointer;';
  testBtn.onclick = () => {
    console.log('🧪 TEST BUTTON CLICKED');
    fetch('/ai-agent/', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        message: 'test message',
        session_id: 'test_session'
      })
    }).then(response => response.json())
    .then(data => console.log('🎯 TEST RESPONSE:', data))
    .catch(error => console.error('❌ TEST ERROR:', error));
  };
  document.body.appendChild(testBtn);
}

// Add test button when page loads
setTimeout(() => {
  console.log('🧪 Adding test button...');
  addTestButton();
}, 2000);

// Debug chat window visibility
function checkChatWindow() {
  console.log('🔍 Checking chat window visibility...');
  console.log('📏 Chat modal exists:', !!chatModal);
  console.log('📏 Chat modal display style:', chatModal ? chatModal.style.display : 'not found');
  console.log('📏 Chat modal classes:', chatModal ? chatModal.className : 'not found');
  console.log('📏 Chat modal visibility:', chatModal ? (chatModal.offsetWidth > 0 && chatModal.offsetHeight > 0) : 'not found');
  
  if (chatModal) {
    const modalRect = chatModal.getBoundingClientRect();
    console.log('📐 Modal position:', modalRect);
    console.log('📐 Modal z-index:', window.getComputedStyle(chatModal).zIndex);
  }
}

// Check chat window every 5 seconds
setInterval(checkChatWindow, 5000);

async function sendChatMessage() {
  console.log('🔥 sendChatMessage() called');
  
  // Check all required elements first
  if (!chatInput || !chatMessages) {
    console.error('❌ Chat elements not found:');
    console.error('  - chatInput:', !!chatInput);
    console.error('  - chatMessages:', !!chatMessages);
    console.error('  - aiAgentUrl:', aiAgentUrl);
    return;
  }

  const msg = chatInput.value.trim();
  console.log('📝 Message to send:', msg);
  console.log('🎯 Message length:', msg.length);
  console.log('🌐 AI Agent URL:', aiAgentUrl);

  if (!msg || chatTyping) {
    if (chatTyping) console.log('⚠️ Already typing, ignoring request');
    if (!msg) console.log('⚠️ Empty message, ignoring');
    return;
  }

  console.log('📤 Preparing to send message...');
  chatTyping = true;
  chatInput.value = '';
  chatSend.disabled = true;
  chatSend.textContent = '...';

  // Add user message
  console.log('➕ Adding user message to chat');
  addUserMessage(msg);

  // Show typing indicator
  addTypingIndicator();

  // Generate session ID for context tracking
  const sessionId = 'session_' + Date.now();

  fetch(aiAgentUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCookie('csrftoken')
    },
    body: JSON.stringify({
      message: msg,
      session_id: sessionId
    })
  })
  .then(response => {
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return response.json();
  })
  .then(data => {
    console.log('Multi-Agent Response:', data);
    removeTypingIndicator();
    
    if (data.error) {
      addAiMessage(`❌ Error: ${data.error}`);
    } else {
      // Add AI response
      addAiMessage(data.response || 'Sorry, I couldn\'t process that.');
      
      // Show options if available (for update/delete operations)
      if (data.options && data.options.length > 0) {
        setTimeout(() => {
          addOptionsMessage(data.options, data.intent);
        }, 500);
      }
      
      // Show confidence and intent info in console for debugging
      console.log(`Intent: ${data.intent}, Confidence: ${data.confidence}`);
      if (data.entities && Object.keys(data.entities).length > 0) {
        console.log('Extracted entities:', data.entities);
      }
    }
  })
  .catch(error => {
    console.error('Multi-Agent Chat error:', error);
    removeTypingIndicator();
    addAiMessage('❌ Sorry, I encountered an error. Please try again.');
  })
  .finally(() => {
    chatTyping = false;
    console.log('Message send complete');
  }).catch(error => {
    console.error('Fetch failed:', error);
    appendMessage('ai', `❌ Connection failed: ${error.message}`);
  });
}

function appendMessage(sender, text) {
  console.log('appendMessage:', sender, text);
  if (!chatMessages) {
    console.error('chatMessages not found');
    return;
  }
  const div = document.createElement('div');
  div.className = `message ${sender}`;
  div.textContent = text;
  
  if (sender === 'user') {
    div.style.background = 'var(--whatsapp-green)';
    div.style.color = 'white';
    div.style.marginLeft = 'auto';
    div.style.marginRight = '0';
    div.style.borderRadius = '12px';
    div.style.borderBottomRightRadius = '4px';
    div.style.maxWidth = '85%';
    div.style.wordWrap = 'break-word';
  } else {
    div.style.background = 'var(--bg3)';
    div.style.color = 'var(--text)';
    div.style.marginRight = 'auto';
    div.style.marginLeft = '0';
    div.style.borderRadius = '12px';
    div.style.borderBottomLeftRadius = '4px';
    div.style.maxWidth = '85%';
    div.style.wordWrap = 'break-word';
  }
  
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}
