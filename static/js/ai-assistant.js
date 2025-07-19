// Hexa
document.addEventListener('DOMContentLoaded', function() {
    const aiToggle = document.getElementById('ai-toggle');
    const aiChat = document.getElementById('ai-chat');
    const aiClose = document.getElementById('ai-close');
    const aiInput = document.getElementById('ai-input');
    const aiSend = document.getElementById('ai-send');
    const aiMessages = document.getElementById('ai-messages');
    
    let isOpen = false;
    let conversationHistory = [];
    
    // Load conversation history from localStorage
    loadConversationHistory();
    
    // Toggle AI chat
    if (aiToggle) {
        aiToggle.addEventListener('click', function() {
            toggleChat();
        });
    }
    
    // Close AI chat
    if (aiClose) {
        aiClose.addEventListener('click', function() {
            closeChat();
        });
    }
    
    // Send message on button click
    if (aiSend) {
        aiSend.addEventListener('click', function() {
            sendMessage();
        });
    }
    
    // Send message on Enter key
    if (aiInput) {
        aiInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
        
        // Auto-resize input
        aiInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 100) + 'px';
        });
    }
    
    // Close chat when clicking outside
    document.addEventListener('click', function(e) {
        if (isOpen && !e.target.closest('.ai-assistant')) {
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
        if (aiChat) {
            aiChat.style.display = 'flex';
            isOpen = true;
            
            // Focus input
            if (aiInput) {
                setTimeout(() => aiInput.focus(), 100);
            }
            
            // Show welcome message if first time
            if (conversationHistory.length === 0) {
                addMessage('assistant', 'Hello! I\'m your Hexa. How can I help you with cybersecurity today?', false);
            }
        }
    }
    
    function closeChat() {
        if (aiChat) {
            aiChat.style.display = 'none';
            isOpen = false;
        }
    }
    
    function sendMessage() {
        const message = aiInput.value.trim();
        if (!message) return;
        
        // Add user message
        addMessage('user', message);
        
        // Clear input
        aiInput.value = '';
        aiInput.style.height = 'auto';
        
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
        if (!aiMessages) return;
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `ai-message ${sender}`;
        
        // Format message content
        const formattedContent = formatMessage(content);
        messageDiv.innerHTML = formattedContent;
        
        aiMessages.appendChild(messageDiv);
        
        // Scroll to bottom
        aiMessages.scrollTop = aiMessages.scrollHeight;
        
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
        typingDiv.className = 'ai-message assistant typing-indicator';
        typingDiv.innerHTML = `
            <div class="typing-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
        `;
        typingDiv.id = 'typing-indicator';
        
        aiMessages.appendChild(typingDiv);
        aiMessages.scrollTop = aiMessages.scrollHeight;
        
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
        if (aiMessages) {
            aiMessages.innerHTML = '';
        }
        addMessage('assistant', 'Conversation history cleared. How can I help you?', false);
    }
    
    // Add clear history button (optional)
    function addClearButton() {
        const aiHeader = document.querySelector('.ai-header');
        if (aiHeader && !document.getElementById('clear-history-btn')) {
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
            
            aiHeader.insertBefore(clearBtn, aiClose);
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
            return `I'm your Hexa! I can help you with:

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
        const message = aiInput.value.trim();
        if (!message) return;
        
        // Check for special commands
        const specialResponse = handleSpecialCommands(message);
        if (specialResponse === null) {
            // Command handled, don't send to API
            aiInput.value = '';
            return;
        } else if (specialResponse) {
            // Show special response
            addMessage('user', message);
            addMessage('assistant', specialResponse);
            aiInput.value = '';
            return;
        }
        
        // Regular message handling
        originalSendMessage();
    };
});
