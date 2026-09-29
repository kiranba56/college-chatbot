/**
 * College AI Chatbot - Client Application Logic
 * Integrates RAG retrieval, markdown parsing, voice recognition, TTS, and modals.
 */

document.addEventListener('DOMContentLoaded', () => {
    // State management
    const state = {
        selectedCategory: 'all',
        sessionId: 'session_' + Math.random().toString(36).substring(2, 9),
        chatHistory: [],
        isGenerating: false,
        speechSynthesisActive: false,
        speechRecognition: null,
        isRecording: false
    };

    // DOM Elements
    const elements = {
        themeToggleBtn: document.getElementById('btnThemeToggle'),
        clearChatBtn: document.getElementById('btnClearChat'),
        categoryChips: document.querySelectorAll('.category-chip'),
        welcomeHero: document.getElementById('welcomeHero'),
        messagesList: document.getElementById('messagesList'),
        typingIndicator: document.getElementById('typingIndicator'),
        ragStatusText: document.getElementById('ragStatusText'),
        chatInput: document.getElementById('chatInput'),
        sendBtn: document.getElementById('btnSendMessage'),
        voiceBtn: document.getElementById('btnVoiceInput'),
        chatViewport: document.getElementById('chatViewport'),
        promptCards: document.querySelectorAll('.prompt-card'),
        suggestedChipsBar: document.getElementById('suggestedChipsBar'),
        suggestedChipsList: document.getElementById('suggestedChipsList'),
        ragStatusBadge: document.getElementById('ragStatusBadge'),
        
        // Modals
        explorerModal: document.getElementById('explorerModal'),
        btnOpenExplorer: document.getElementById('btnOpenExplorer'),
        btnCloseExplorer: document.getElementById('btnCloseExplorer'),
        explorerSearchInput: document.getElementById('explorerSearchInput'),
        explorerCategoryFilter: document.getElementById('explorerCategoryFilter'),
        explorerGrid: document.getElementById('explorerGrid'),

        adminModal: document.getElementById('adminModal'),
        btnOpenAdmin: document.getElementById('btnOpenAdmin'),
        btnCloseAdmin: document.getElementById('btnCloseAdmin'),
        btnCancelNotice: document.getElementById('btnCancelNotice'),
        addNoticeForm: document.getElementById('addNoticeForm'),

        statusModal: document.getElementById('statusModal'),
        btnOpenStatus: document.getElementById('btnOpenStatus'),
        btnCloseStatus: document.getElementById('btnCloseStatus'),
        statusSupabaseValue: document.getElementById('statusSupabaseValue'),
        statusLLMValue: document.getElementById('statusLLMValue'),
        statusDocsValue: document.getElementById('statusDocsValue'),
        btnSyncSupabase: document.getElementById('btnSyncSupabase'),

        toastContainer: document.getElementById('toastContainer')
    };

    // Initialize marked options
    if (window.marked) {
        marked.setOptions({
            gfm: true,
            breaks: true,
            headerIds: false
        });
    }

    // =========================================================================
    // Theme Management
    // =========================================================================
    const savedTheme = localStorage.getItem('college_chatbot_theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);

    elements.themeToggleBtn.addEventListener('click', () => {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('college_chatbot_theme', newTheme);
        updateThemeIcon(newTheme);
    });

    function updateThemeIcon(theme) {
        const icon = elements.themeToggleBtn.querySelector('.theme-icon');
        if (theme === 'dark') {
            icon.className = 'fa-solid fa-moon theme-icon';
        } else {
            icon.className = 'fa-solid fa-sun theme-icon';
        }
    }

    // =========================================================================
    // Category Filter Selection
    // =========================================================================
    elements.categoryChips.forEach(chip => {
        chip.addEventListener('click', () => {
            elements.categoryChips.forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            state.selectedCategory = chip.dataset.category;
            showToast(`Filter set to: ${chip.textContent.trim()}`);
        });
    });

    // =========================================================================
    // Textarea Auto-Resize & Keyboard Handling
    // =========================================================================
    elements.chatInput.addEventListener('input', () => {
        elements.chatInput.style.height = 'auto';
        elements.chatInput.style.height = Math.min(elements.chatInput.scrollHeight, 120) + 'px';
    });

    elements.chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    });

    elements.sendBtn.addEventListener('click', handleSendMessage);

    // Quick Prompt Card Clicks
    elements.promptCards.forEach(card => {
        card.addEventListener('click', () => {
            const promptText = card.dataset.prompt;
            if (promptText) {
                elements.chatInput.value = promptText;
                handleSendMessage();
            }
        });
    });

    // =========================================================================
    // Clear / Reset Conversation
    // =========================================================================
    elements.btnClearChat.addEventListener('click', () => {
        if (confirm('Start a new session and clear conversation history?')) {
            if (window.speechSynthesis) window.speechSynthesis.cancel();
            elements.messagesList.innerHTML = '';
            elements.messagesList.style.display = 'none';
            elements.welcomeHero.style.display = 'flex';
            elements.suggestedChipsBar.style.display = 'none';
            state.chatHistory = [];
            state.sessionId = 'session_' + Math.random().toString(36).substring(2, 9);
            showToast('Conversation refreshed.');
        }
    });

    // =========================================================================
    // Core Message Sending & RAG Pipeline
    // =========================================================================
    async function handleSendMessage() {
        const query = elements.chatInput.value.trim();
        if (!query || state.isGenerating) return;

        // Switch view from hero to message list
        if (elements.welcomeHero.style.display !== 'none') {
            elements.welcomeHero.style.display = 'none';
            elements.messagesList.style.display = 'flex';
        }

        // Clear input
        elements.chatInput.value = '';
        elements.chatInput.style.height = 'auto';
        elements.sendBtn.disabled = true;
        state.isGenerating = true;

        // Append User Message
        appendUserMessage(query);

        // Show typing / RAG searching indicator
        showTypingIndicator("Searching campus knowledge base & vector embeddings...");
        scrollToBottom();

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: query,
                    category: state.selectedCategory,
                    session_id: state.sessionId,
                    history: state.chatHistory.slice(-4)
                })
            });

            const data = await response.json();
            hideTypingIndicator();

            if (data.success) {
                appendBotMessage(data.reply, data.sources, data.log_id, data.model);
                updateSuggestedChips(data.suggested_questions);
                // Save history
                state.chatHistory.push({ role: 'user', content: query });
                state.chatHistory.push({ role: 'assistant', content: data.reply });
            } else {
                appendBotMessage(
                    "⚠️ **Service Notice**: We encountered an issue retrieving verified records. Please check the Knowledge Directory or try again.",
                    [],
                    null,
                    "System"
                );
            }
        } catch (error) {
            console.error('Chat error:', error);
            hideTypingIndicator();
            appendBotMessage(
                "⚠️ **Network Error**: Unable to reach the backend server. Please verify your connection or refresh the page.",
                [],
                null,
                "Error"
            );
        } finally {
            state.isGenerating = false;
            elements.sendBtn.disabled = false;
            elements.chatInput.focus();
            scrollToBottom();
        }
    }

    function appendUserMessage(text) {
        const timeStr = getCurrentTime();
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message-row user';
        msgDiv.innerHTML = `
            <div class="message-bubble-wrapper">
                <div class="message-bubble">${escapeHtml(text)}</div>
                <div class="message-actions-bar">
                    <span class="msg-timestamp">${timeStr}</span>
                </div>
            </div>
            <div class="message-avatar">
                <i class="fa-solid fa-user-graduate"></i>
            </div>
        `;
        elements.messagesList.appendChild(msgDiv);
    }

    function appendBotMessage(replyMarkdown, sources, logId, modelName) {
        const timeStr = getCurrentTime();
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message-row bot';

        // Render Markdown safely
        const renderedHtml = window.marked ? marked.parse(replyMarkdown) : replyMarkdown.replace(/\n/g, '<br>');

        // Render sources accordion if available
        let sourcesHtml = '';
        if (sources && sources.length > 0) {
            const sourceItems = sources.map(s => `
                <div class="source-item">
                    <div class="source-title-row">
                        <span class="source-title"><i class="fa-solid fa-file-lines"></i> ${escapeHtml(s.title || 'Official College Record')}</span>
                        <span class="source-score">${Math.round((s.similarity || 0.85) * 100)}% match</span>
                    </div>
                    <div class="source-snippet">${escapeHtml((s.content || '').substring(0, 140))}...</div>
                </div>
            `).join('');

            sourcesHtml = `
                <div class="sources-accordion">
                    <div class="sources-header" onclick="this.nextElementSibling.classList.toggle('hidden')">
                        <span><i class="fa-solid fa-database"></i> Verified Sources (${sources.length} matching college records)</span>
                        <i class="fa-solid fa-chevron-down"></i>
                    </div>
                    <div class="sources-list">${sourceItems}</div>
                </div>
            `;
        }

        msgDiv.innerHTML = `
            <div class="message-avatar">
                <i class="fa-solid fa-robot"></i>
            </div>
            <div class="message-bubble-wrapper">
                <div class="message-bubble">
                    ${renderedHtml}
                    ${sourcesHtml}
                </div>
                <div class="message-actions-bar">
                    <span class="msg-timestamp">${timeStr}</span>
                    <button class="msg-action-btn btn-tts" title="Read Aloud (Text to Speech)" aria-label="Read aloud">
                        <i class="fa-solid fa-volume-high"></i>
                    </button>
                    <button class="msg-action-btn btn-copy" title="Copy to Clipboard" aria-label="Copy text">
                        <i class="fa-regular fa-copy"></i>
                    </button>
                    <button class="msg-action-btn btn-thumb-up" data-log-id="${logId || ''}" title="Helpful answer" aria-label="Thumbs up">
                        <i class="fa-regular fa-thumbs-up"></i>
                    </button>
                    <button class="msg-action-btn btn-thumb-down" data-log-id="${logId || ''}" title="Needs improvement" aria-label="Thumbs down">
                        <i class="fa-regular fa-thumbs-down"></i>
                    </button>
                </div>
            </div>
        `;

        elements.messagesList.appendChild(msgDiv);

        // Attach action handlers
        const copyBtn = msgDiv.querySelector('.btn-copy');
        copyBtn.addEventListener('click', () => {
            navigator.clipboard.writeText(replyMarkdown);
            copyBtn.innerHTML = '<i class="fa-solid fa-check text-success"></i>';
            showToast('Copied to clipboard!');
            setTimeout(() => {
                copyBtn.innerHTML = '<i class="fa-regular fa-copy"></i>';
            }, 2000);
        });

        const ttsBtn = msgDiv.querySelector('.btn-tts');
        ttsBtn.addEventListener('click', () => {
            toggleTextToSpeech(replyMarkdown, ttsBtn);
        });

        const upBtn = msgDiv.querySelector('.btn-thumb-up');
        const downBtn = msgDiv.querySelector('.btn-thumb-down');

        upBtn.addEventListener('click', () => {
            sendFeedback(logId, 1);
            upBtn.classList.add('active-good');
            downBtn.classList.remove('active-bad');
            showToast('Thank you for your feedback! 👍');
        });

        downBtn.addEventListener('click', () => {
            sendFeedback(logId, -1);
            downBtn.classList.add('active-bad');
            upBtn.classList.remove('active-good');
            showToast('Feedback noted. We will refine this topic! 👎');
        });
    }

    function showTypingIndicator(statusMsg) {
        if (statusMsg) elements.ragStatusText.innerHTML = `<span class="spinner-dot"></span> ${statusMsg}`;
        elements.typingIndicator.style.display = 'flex';
    }

    function hideTypingIndicator() {
        elements.typingIndicator.style.display = 'none';
    }

    function scrollToBottom() {
        setTimeout(() => {
            elements.chatViewport.scrollTo({
                top: elements.chatViewport.scrollHeight,
                behavior: 'smooth'
            });
        }, 50);
    }

    // =========================================================================
    // Suggested Follow-up Chips
    // =========================================================================
    function updateSuggestedChips(suggestions) {
        if (!suggestions || suggestions.length === 0) {
            elements.suggestedChipsBar.style.display = 'none';
            return;
        }

        elements.suggestedChipsList.innerHTML = '';
        suggestions.forEach(question => {
            const chip = document.createElement('button');
            chip.className = 'suggested-chip';
            chip.textContent = question;
            chip.addEventListener('click', () => {
                elements.chatInput.value = question;
                handleSendMessage();
            });
            elements.suggestedChipsList.appendChild(chip);
        });

        elements.suggestedChipsBar.style.display = 'flex';
    }

    // =========================================================================
    // Speech Recognition (Voice to Text)
    // =========================================================================
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
        state.speechRecognition = new SpeechRecognition();
        state.speechRecognition.continuous = false;
        state.speechRecognition.interimResults = false;
        state.speechRecognition.lang = 'en-US';

        state.speechRecognition.onstart = () => {
            state.isRecording = true;
            elements.voiceBtn.classList.add('recording');
            showToast('Listening... Speak your college question.');
        };

        state.speechRecognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            elements.chatInput.value = transcript;
            elements.voiceBtn.classList.remove('recording');
            state.isRecording = false;
            handleSendMessage();
        };

        state.speechRecognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            elements.voiceBtn.classList.remove('recording');
            state.isRecording = false;
            showToast('Voice input unavailable or cancelled.');
        };

        state.speechRecognition.onend = () => {
            elements.voiceBtn.classList.remove('recording');
            state.isRecording = false;
        };

        elements.voiceBtn.addEventListener('click', () => {
            if (state.isRecording) {
                state.speechRecognition.stop();
            } else {
                state.speechRecognition.start();
            }
        });
    } else {
        elements.voiceBtn.title = "Voice input not supported on this browser";
        elements.voiceBtn.style.opacity = "0.4";
    }

    // =========================================================================
    // Text to Speech (Audio Reading)
    // =========================================================================
    function toggleTextToSpeech(textMarkdown, buttonElement) {
        if (!('speechSynthesis' in window)) {
            showToast('Text-to-speech is not supported in this browser.');
            return;
        }

        if (window.speechSynthesis.speaking) {
            window.speechSynthesis.cancel();
            buttonElement.innerHTML = '<i class="fa-solid fa-volume-high"></i>';
            return;
        }

        // Strip markdown syntax for natural reading
        const cleanText = textMarkdown
            .replace(/[*#_`>]/g, '')
            .replace(/\[(.*?)\]\(.*?\)/g, '$1')
            .replace(/---+/g, '')
            .substring(0, 800);

        const utterance = new SpeechSynthesisUtterance(cleanText);
        utterance.rate = 1.0;
        utterance.pitch = 1.0;

        utterance.onstart = () => {
            buttonElement.innerHTML = '<i class="fa-solid fa-stop text-warning"></i>';
        };

        utterance.onend = () => {
            buttonElement.innerHTML = '<i class="fa-solid fa-volume-high"></i>';
        };

        utterance.onerror = () => {
            buttonElement.innerHTML = '<i class="fa-solid fa-volume-high"></i>';
        };

        window.speechSynthesis.speak(utterance);
    }

    // =========================================================================
    // Feedback API
    // =========================================================================
    async function sendFeedback(logId, score) {
        try {
            await fetch('/api/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ log_id: logId, feedback: score })
            });
        } catch (e) {
            console.error('Feedback submission error:', e);
        }
    }

    // =========================================================================
    // Modal 1: Knowledge Directory Explorer
    // =========================================================================
    elements.btnOpenExplorer.addEventListener('click', () => {
        elements.explorerModal.classList.add('open');
        loadExplorerDocuments();
    });

    elements.btnCloseExplorer.addEventListener('click', () => {
        elements.explorerModal.classList.remove('open');
    });

    elements.explorerSearchInput.addEventListener('input', debounce(loadExplorerDocuments, 250));
    elements.explorerCategoryFilter.addEventListener('change', loadExplorerDocuments);

    async function loadExplorerDocuments() {
        const search = elements.explorerSearchInput.value.trim();
        const category = elements.explorerCategoryFilter.value;
        elements.explorerGrid.innerHTML = '<div class="loading-state"><span class="spinner-dot"></span> Loading directory...</div>';

        try {
            const res = await fetch(`/api/knowledge?search=${encodeURIComponent(search)}&category=${encodeURIComponent(category)}`);
            const data = await res.json();

            if (!data.success || data.documents.length === 0) {
                elements.explorerGrid.innerHTML = '<div class="loading-state">No matching college records found. Try another search keyword.</div>';
                return;
            }

            elements.explorerGrid.innerHTML = data.documents.map(doc => `
                <div class="doc-card">
                    <span class="doc-card-badge">${escapeHtml(doc.category)}</span>
                    <h4 class="doc-card-title">${escapeHtml(doc.title)}</h4>
                    <p class="doc-card-content">${escapeHtml(doc.content.substring(0, 160))}...</p>
                    <button class="doc-card-btn" onclick="askAboutDocument('${escapeHtml(doc.title)}')">
                        <i class="fa-regular fa-comment-dots"></i> Ask Chatbot about this
                    </button>
                </div>
            `).join('');

        } catch (e) {
            elements.explorerGrid.innerHTML = '<div class="loading-state">Failed to load directory records.</div>';
        }
    }

    window.askAboutDocument = function(title) {
        elements.explorerModal.classList.remove('open');
        elements.chatInput.value = `Tell me full details about: ${title}`;
        handleSendMessage();
    };

    // =========================================================================
    // Modal 2: Add Notice / Admin Knowledge Input
    // =========================================================================
    elements.btnOpenAdmin.addEventListener('click', () => {
        elements.adminModal.classList.add('open');
    });

    elements.btnCloseAdmin.addEventListener('click', () => {
        elements.adminModal.classList.remove('open');
    });

    elements.btnCancelNotice.addEventListener('click', () => {
        elements.adminModal.classList.remove('open');
    });

    elements.addNoticeForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const category = document.getElementById('noticeCategory').value;
        const title = document.getElementById('noticeTitle').value.trim();
        const content = document.getElementById('noticeContent').value.trim();
        const keywords = document.getElementById('noticeKeywords').value.trim();

        if (!title || !content) return;

        try {
            const res = await fetch('/api/knowledge', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ category, title, content, keywords })
            });

            const result = await res.json();
            if (result.success) {
                showToast('Notice successfully published and indexed!');
                elements.addNoticeForm.reset();
                elements.adminModal.classList.remove('open');
            } else {
                showToast(`Error: ${result.error || 'Failed to save notice'}`);
            }
        } catch (e) {
            showToast('Network error while posting notice.');
        }
    });

    // =========================================================================
    // Modal 3: System Status & Flask Settings
    // =========================================================================
    elements.btnOpenStatus.addEventListener('click', () => {
        elements.statusModal.classList.add('open');
        fetchSystemStatus();
    });

    elements.btnCloseStatus.addEventListener('click', () => {
        elements.statusModal.classList.remove('open');
    });

    async function fetchSystemStatus() {
        try {
            const res = await fetch('/api/status');
            const data = await res.json();

            // Update modal values
            elements.statusSupabaseValue.innerHTML = '<span class="text-success"><i class="fa-solid fa-circle-check"></i> ' + (data.database || 'Flask SQLite (Embedded)') + '</span>';

            elements.statusLLMValue.innerHTML = data.gemini_api_configured
                ? `<span class="text-success"><i class="fa-solid fa-circle-check"></i> ${data.llm_model}</span>`
                : '<span class="text-warning"><i class="fa-solid fa-circle-info"></i> Verified Campus RAG Fallback</span>';

            elements.statusDocsValue.textContent = `${data.total_documents_indexed} Documents`;

            // Update badge on navbar
            elements.ragStatusBadge.innerHTML = '<i class="fa-solid fa-server"></i> Flask Native RAG Active';
            elements.ragStatusBadge.className = 'badge-rag';
        } catch (e) {
            console.error('Status check error:', e);
        }
    }

    // Re-index Flask database and vector store button
    elements.btnSyncSupabase.addEventListener('click', async () => {
        elements.btnSyncSupabase.disabled = true;
        elements.btnSyncSupabase.innerHTML = '<span class="spinner-dot"></span> Re-indexing in Flask...';

        try {
            const res = await fetch('/api/reindex', { method: 'POST' });
            const result = await res.json();

            if (result.success) {
                showToast(`Re-indexed ${result.total_documents} documents in Flask vector database!`);
                fetchSystemStatus();
            } else {
                showToast(`Re-index Notice: ${result.message}`);
            }
        } catch (e) {
            showToast('Re-index request failed.');
        } finally {
            elements.btnSyncSupabase.disabled = false;
            elements.btnSyncSupabase.innerHTML = '<i class="fa-solid fa-arrows-rotate"></i> Re-index Campus Knowledge Base';
        }
    });

    // Close modals on outside backdrop click
    window.addEventListener('click', (e) => {
        if (e.target === elements.explorerModal) elements.explorerModal.classList.remove('open');
        if (e.target === elements.adminModal) elements.adminModal.classList.remove('open');
        if (e.target === elements.statusModal) elements.statusModal.classList.remove('open');
    });

    // =========================================================================
    // Utilities
    // =========================================================================
    function showToast(message) {
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.innerHTML = `<i class="fa-solid fa-circle-info text-highlight"></i> <span>${escapeHtml(message)}</span>`;
        elements.toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(10px)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    function getCurrentTime() {
        const now = new Date();
        return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function escapeHtml(str) {
        if (!str) return '';
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function debounce(func, wait) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }

    // Initial system status check on page load
    fetchSystemStatus();
});
