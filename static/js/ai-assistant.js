// PentraX AI Assistant
document.addEventListener('DOMContentLoaded', function() {
    const hexaToggle = document.getElementById('hexa-toggle');
    const hexaChat = document.getElementById('hexa-chat');
    const hexaClose = document.getElementById('hexa-close');
    const hexaInput = document.getElementById('hexa-input');
    const hexaSend = document.getElementById('hexa-send');
    const hexaMessages = document.getElementById('hexa-messages');
    
    let isOpen = false;
    let conversationHistory = [];
    
    // Load conversation history from localStorage
    loadConversationHistory();
    
    // Toggle AI chat
    if (hexaToggle) {
        hexaToggle.addEventListener('click', function() {
            toggleChat();
        });
    }
    
    // Close AI chat
    if (hexaClose) {
        hexaClose.addEventListener('click', function() {
            closeChat();
        });
    }
    
    // Send message on button click
    if (hexaSend) {
        hexaSend.addEventListener('click', function() {
            sendMessage();
        });
    }
    
    // Send message on Enter key
    if (hexaInput) {
        hexaInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
        
        // Auto-resize input
        hexaInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 100) + 'px';
        });
    }
    
    // Close chat when clicking outside
    document.addEventListener('click', function(e) {
        if (isOpen && !e.target.closest('.hexa-assistant')) {
            closeChat();
        }
    });
    
    function toggleChat() {
        if (isOpen) {
            closeChat();
        } else {
            openChat();
        }
    }
    
    function openChat() {
        if (hexaChat) {
            hexaChat.style.display = 'flex';
            isOpen = true;
            
            // Focus input
            if (hexaInput) {
                setTimeout(() => hexaInput.focus(), 100);
            }
            
            // Show welcome message if first time
            if (conversationHistory.length === 0) {
                addMessage('assistant', 'Hello! I\'m your PentraX AI assistant. How can I help you with cybersecurity today?', false);
            }
        }
    }
    
    function closeChat() {
        if (hexaChat) {
            hexaChat.style.display = 'none';
            isOpen = false;
        }
    }
    
    function sendMessage() {
        const message = hexaInput.value.trim();
        if (!message) return;
        
        // Add user message
        addMessage('user', message);
        
        // Clear input
        hexaInput.value = '';
        hexaInput.style.height = 'auto';
        
        // Show typing indicator
        showTypingIndicator();
        
        // Send to backend
        fetch('/ai_chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: message })
        })
        .then(response => response.json())
        .then(data => {
            hideTypingIndicator();
            
            if (data.error) {
                addMessage('assistant', 'Sorry, I encountered an error: ' + data.error);
            } else {
                addMessage('assistant', data.response);
            }
        })
        .catch(error => {
            hideTypingIndicator();
            console.error('AI Chat Error:', error);
            addMessage('assistant', 'Sorry, I\'m having trouble connecting right now. Please try again later.');
        });
    }
    
    function addMessage(sender, content, save = true) {
        if (!hexaMessages) return;
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `hexa-message ${sender}`;
        
        // Format message content
        const formattedContent = formatMessage(content);
        messageDiv.innerHTML = formattedContent;
        
        hexaMessages.appendChild(messageDiv);
        
        // Scroll to bottom
        hexaMessages.scrollTop = hexaMessages.scrollHeight;
        
        // Save to history
        if (save) {
            conversationHistory.push({ sender, content, timestamp: Date.now() });
            saveConversationHistory();
        }
        
        // Add animation
        messageDiv.classList.add('slide-up');
    }
    
    function formatMessage(content) {
        // Basic markdown-style formatting
        let formatted = content
            // Code blocks
            .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
            // Inline code
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            // Bold
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            // Italic
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            // Line breaks
            .replace(/\n/g, '<br>');
        
        return formatted;
    }
    
    function showTypingIndicator() {
        const typingDiv = document.createElement('div');
        typingDiv.className = 'hexa-message assistant typing-indicator';
        typingDiv.innerHTML = `
            <div class="typing-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
        `;
        typingDiv.id = 'typing-indicator';
        
        hexaMessages.appendChild(typingDiv);
        hexaMessages.scrollTop = hexaMessages.scrollHeight;
        
        // Add CSS for typing animation
        if (!document.getElementById('typing-styles')) {
            const style = document.createElement('style');
            style.id = 'typing-styles';
            style.textContent = `
                .typing-dots {
                    display: flex;
                    gap: 4px;
                }
                
                .typing-dots span {
                    width: 8px;
                    height: 8px;
                    border-radius: 50%;
                    background-color: var(--bs-secondary);
                    animation: typing 1.4s infinite ease-in-out;
                }
                
                .typing-dots span:nth-child(1) { animation-delay: -0.32s; }
                .typing-dots span:nth-child(2) { animation-delay: -0.16s; }
                
                @keyframes typing {
                    0%, 80%, 100% { transform: scale(0.8); opacity: 0.5; }
                    40% { transform: scale(1); opacity: 1; }
                }
            `;
            document.head.appendChild(style);
        }
    }
    
    function hideTypingIndicator() {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) {
            indicator.remove();
        }
    }
    
    function saveConversationHistory() {
        try {
            // Keep only last 20 messages to prevent localStorage bloat
            const recentHistory = conversationHistory.slice(-20);
            localStorage.setItem('ai-conversation', JSON.stringify(recentHistory));
        } catch (e) {
            console.warn('Could not save AI conversation history:', e);
        }
    }
    
    function loadConversationHistory() {
        try {
            const saved = localStorage.getItem('ai-conversation');
            if (saved) {
                conversationHistory = JSON.parse(saved);
                
                // Display saved messages (limit to recent ones)
                conversationHistory.slice(-10).forEach(msg => {
                    addMessage(msg.sender, msg.content, false);
                });
            }
        } catch (e) {
            console.warn('Could not load AI conversation history:', e);
            conversationHistory = [];
        }
    }
    
    function clearHistory() {
        conversationHistory = [];
        localStorage.removeItem('ai-conversation');
        if (hexaMessages) {
            hexaMessages.innerHTML = '';
        }
        addMessage('assistant', 'Conversation history cleared. How can I help you?', false);
    }
    
    // Add clear history button (optional)
    function addClearButton() {
        const hexaHeader = document.querySelector('.hexa-header');
        if (hexaHeader && !document.getElementById('clear-history-btn')) {
            const clearBtn = document.createElement('button');
            clearBtn.id = 'clear-history-btn';
            clearBtn.className = 'btn btn-sm btn-outline-light';
            clearBtn.innerHTML = '<i class="fas fa-trash"></i>';
            clearBtn.title = 'Clear conversation';
            clearBtn.style.marginLeft = 'auto';
            clearBtn.style.marginRight = '10px';
            
            clearBtn.addEventListener('click', function() {
                if (confirm('Clear conversation history?')) {
                    clearHistory();
                }
            });
            
            hexaHeader.insertBefore(clearBtn, hexaClose);
        }
    }
    
    // Initialize clear button
    addClearButton();
    
    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Alt + A to toggle AI assistant
        if (e.altKey && e.key === 'a') {
            e.preventDefault();
            toggleChat();
        }
        
        // Escape to close AI assistant
        if (e.key === 'Escape' && isOpen) {
            closeChat();
        }
    });
    
    // Add help command
    function handleSpecialCommands(message) {
        const lowerMessage = message.toLowerCase().trim();
        
        if (lowerMessage === '/help' || lowerMessage === 'help') {
            return `I'm your PentraX AI assistant! I can help you with:

• **Security Tools** - Explain how tools work, debug scripts
• **Vulnerability Analysis** - Understand CVEs, attack vectors  
• **Code Review** - Identify security issues in code
• **Penetration Testing** - Guide through testing techniques
• **Best Practices** - Security recommendations and standards

Just ask me anything about cybersecurity! You can also use:
• \`/clear\` - Clear conversation history
• \`Alt + A\` - Toggle this chat
• \`Escape\` - Close this chat`;
        }
        
        if (lowerMessage === '/clear') {
            clearHistory();
            return null; // Don't send to API
        }
        
        return false; // Not a special command
    }
    
    // Modify sendMessage to handle special commands
    const originalSendMessage = sendMessage;
    sendMessage = function() {
        const message = hexaInput.value.trim();
        if (!message) return;
        
        // Check for special commands
        const specialResponse = handleSpecialCommands(message);
        if (specialResponse === null) {
            // Command handled, don't send to API
            hexaInput.value = '';
            return;
        } else if (specialResponse) {
            // Show special response
            addMessage('user', message);
            addMessage('assistant', specialResponse);
            hexaInput.value = '';
            return;
        }
        
        // Regular message handling
        originalSendMessage();
    };
});

// Add draggable logic for Hexa
function makeHexaDraggable() {
    const hexa = document.querySelector('.hexa-assistant');
    if (!hexa) return;
    let offsetX = 0, offsetY = 0, startX = 0, startY = 0, dragging = false;

    // Restore position from localStorage
    const saved = localStorage.getItem('hexa-position');
    if (saved) {
        const pos = JSON.parse(saved);
        hexa.style.left = pos.left;
        hexa.style.top = pos.top;
        hexa.style.position = 'fixed';
    }

    function onMouseDown(e) {
        dragging = true;
        startX = e.type.startsWith('touch') ? e.touches[0].clientX : e.clientX;
        startY = e.type.startsWith('touch') ? e.touches[0].clientY : e.clientY;
        const rect = hexa.getBoundingClientRect();
        offsetX = startX - rect.left;
        offsetY = startY - rect.top;
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
        document.addEventListener('touchmove', onMouseMove);
        document.addEventListener('touchend', onMouseUp);
    }
    function onMouseMove(e) {
        if (!dragging) return;
        let x = e.type.startsWith('touch') ? e.touches[0].clientX : e.clientX;
        let y = e.type.startsWith('touch') ? e.touches[0].clientY : e.clientY;
        let left = x - offsetX;
        let top = y - offsetY;
        // Clamp to viewport
        left = Math.max(0, Math.min(window.innerWidth - hexa.offsetWidth, left));
        top = Math.max(0, Math.min(window.innerHeight - hexa.offsetHeight, top));
        hexa.style.left = left + 'px';
        hexa.style.top = top + 'px';
        hexa.style.position = 'fixed';
    }
    function onMouseUp() {
        dragging = false;
        localStorage.setItem('hexa-position', JSON.stringify({ left: hexa.style.left, top: hexa.style.top }));
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
        document.removeEventListener('touchmove', onMouseMove);
        document.removeEventListener('touchend', onMouseUp);
    }
    // Drag handle: whole header or the widget itself
    const dragHandle = hexa.querySelector('.hexa-header') || hexa;
    dragHandle.style.cursor = 'move';
    dragHandle.addEventListener('mousedown', onMouseDown);
    dragHandle.addEventListener('touchstart', onMouseDown);
}

// Call after DOM is ready
setTimeout(makeHexaDraggable, 500);
