document.addEventListener("DOMContentLoaded", () => {
    let activeSessionId = null;
    let ws = null;
    let sessions = [];
    let currentVncMode = "live"; // "live" or "screenshot"

    // DOM Elements
    const sessionsListEl = document.getElementById("sessions-list");
    const activeTitleEl = document.getElementById("active-session-title");
    const activeIdEl = document.getElementById("active-session-id");
    const statusBadgeEl = document.getElementById("session-status-badge");
    const statusTextEl = document.getElementById("status-text");
    const chatMessagesEl = document.getElementById("chat-messages");
    const promptInputEl = document.getElementById("prompt-input");
    const promptFormEl = document.getElementById("prompt-form");
    const sendBtnEl = document.getElementById("send-btn");
    const stopBtnEl = document.getElementById("stop-btn");
    const newSessionBtnEl = document.getElementById("new-session-btn");
    
    // Modal Elements
    const createModalEl = document.getElementById("create-modal");
    const modalCancelBtnEl = document.getElementById("modal-cancel-btn");
    const modalSubmitBtnEl = document.getElementById("modal-submit-btn");
    const sessionTitleInputEl = document.getElementById("session-title-input");
    const sessionModelSelectEl = document.getElementById("session-model-select");

    // VNC Display Elements
    const liveScreenshotImgEl = document.getElementById("live-screenshot-img");
    const vncPlaceholderEl = document.getElementById("vnc-overlay-placeholder");
    const vncIframeEl = document.getElementById("vnc-iframe");
    const refreshVncBtnEl = document.getElementById("refresh-vnc-btn");
    const canvasContainerEl = document.getElementById("canvas-fallback-container");
    const modeVncBtnEl = document.getElementById("mode-vnc-btn");
    const modeScreenshotBtnEl = document.getElementById("mode-screenshot-btn");
    const popoutVncBtnEl = document.getElementById("popout-vnc-btn");
    const vncToastBannerEl = document.getElementById("vnc-toast-banner");
    const vncTitleTextEl = document.getElementById("vnc-title-text");

    // Lightbox Elements
    const lightboxModalEl = document.getElementById("lightbox-modal");
    const lightboxImgEl = document.getElementById("lightbox-img");
    const lightboxCaptionEl = document.getElementById("lightbox-caption");
    const lightboxCloseBtnEl = document.getElementById("lightbox-close-btn");

    // Check if noVNC on port 6080 is reachable
    async function checkVncAvailability() {
        const host = window.location.hostname || "localhost";
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 1000);
            await fetch(`http://${host}:6080`, { mode: "no-cors", signal: controller.signal });
            clearTimeout(timeoutId);
            return true;
        } catch (e) {
            return false;
        }
    }

    // Configure noVNC URL based on host and availability
    async function initVncUrls() {
        const host = window.location.hostname || "localhost";
        const vncUrl = `http://${host}:6080/vnc.html?autoconnect=true&reconnect=true&resize=scale`;
        if (vncIframeEl) {
            vncIframeEl.src = vncUrl;
        }
        if (popoutVncBtnEl) {
            popoutVncBtnEl.href = vncUrl;
        }

        const isVncUp = await checkVncAvailability();
        if (isVncUp) {
            setVncMode("live");
        } else {
            setVncMode("screenshot");
        }
    }

    // Set VNC Mode (live noVNC vs desktop screen image stream)
    function setVncMode(mode) {
        currentVncMode = mode;
        if (mode === "live") {
            modeVncBtnEl.classList.add("active");
            modeScreenshotBtnEl.classList.remove("active");
            vncIframeEl.style.display = "block";
            canvasContainerEl.style.display = "none";
            if (vncTitleTextEl) vncTitleTextEl.textContent = "Virtual Machine Desktop (noVNC Live)";
        } else {
            modeScreenshotBtnEl.classList.add("active");
            modeVncBtnEl.classList.remove("active");
            vncIframeEl.style.display = "none";
            canvasContainerEl.style.display = "flex";
            if (vncTitleTextEl) vncTitleTextEl.textContent = "Virtual Machine Desktop (Live Screen Stream)";
        }
    }

    modeVncBtnEl.addEventListener("click", async () => {
        const isUp = await checkVncAvailability();
        if (!isUp) {
            showToast("noVNC server on port 6080 is offline. Run via Docker ('docker-compose up') for full noVNC.");
        }
        setVncMode("live");
    });

    modeScreenshotBtnEl.addEventListener("click", () => {
        setVncMode("screenshot");
    });

    // Notification toast banner
    let toastTimeout = null;
    function showToast(msg) {
        if (!vncToastBannerEl) return;
        vncToastBannerEl.textContent = msg || "📸 Desktop screenshot updated";
        vncToastBannerEl.style.display = "block";
        if (toastTimeout) clearTimeout(toastTimeout);
        toastTimeout = setTimeout(() => {
            vncToastBannerEl.style.display = "none";
        }, 3000);
    }

    // Load Sessions
    async function loadSessions() {
        initVncUrls();
        try {
            const res = await fetch("/api/v1/sessions");
            sessions = await res.json();
            renderSessionsList();
            
            if (!activeSessionId && sessions.length > 0) {
                selectSession(sessions[0].id);
            }
        } catch (err) {
            console.error("Failed to load sessions:", err);
            sessionsListEl.innerHTML = `<div class="event-card error">Error loading sessions</div>`;
        }
    }

    function renderSessionsList() {
        sessionsListEl.innerHTML = "";
        if (sessions.length === 0) {
            sessionsListEl.innerHTML = `<div style="color: var(--text-dim); text-align: center; font-size: 13px; padding: 20px;">No active sessions</div>`;
            return;
        }

        sessions.forEach(sess => {
            const dateStr = new Date(sess.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            const item = document.createElement("div");
            item.className = `session-item ${sess.id === activeSessionId ? "active" : ""}`;
            item.innerHTML = `
                <div class="session-item-info">
                    <div class="session-item-title">${escapeHtml(sess.title)}</div>
                    <div class="session-item-date">${dateStr} • ${sess.status}</div>
                </div>
                <button class="delete-session-btn" title="Delete Session" data-id="${sess.id}">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    </svg>
                </button>
            `;

            item.addEventListener("click", (e) => {
                if (e.target.closest(".delete-session-btn")) return;
                selectSession(sess.id);
            });

            item.querySelector(".delete-session-btn").addEventListener("click", (e) => {
                e.stopPropagation();
                deleteSession(sess.id);
            });

            sessionsListEl.appendChild(item);
        });
    }

    async function selectSession(sessionId) {
        if (activeSessionId === sessionId) return;
        activeSessionId = sessionId;
        renderSessionsList();

        const sess = sessions.find(s => s.id === sessionId);
        if (sess) {
            activeTitleEl.textContent = sess.title;
            activeIdEl.textContent = `ID: ${sess.id.substring(0, 8)}...`;
            updateStatusBadge(sess.status);
        }

        // Enable Inputs
        promptInputEl.disabled = false;
        sendBtnEl.disabled = false;

        // Clear chat area
        chatMessagesEl.innerHTML = "";

        // Load Message History
        await loadMessageHistory(sessionId);

        // Connect WebSocket for real-time streaming
        connectWebSocket(sessionId);
    }

    async function loadMessageHistory(sessionId) {
        try {
            const res = await fetch(`/api/v1/sessions/${sessionId}/messages`);
            const messages = await res.json();
            
            if (messages.length === 0) {
                chatMessagesEl.innerHTML = `
                    <div class="welcome-card">
                        <h3>Session Ready</h3>
                        <p>Type a command below to instruct the Computer Use Agent.</p>
                    </div>
                `;
                return;
            }

            let latestScreenshot = null;
            messages.forEach(msg => {
                if (msg.role === "user") {
                    appendUserBubble(msg.content);
                } else if (msg.role === "assistant") {
                    if (msg.content) {
                        appendAssistantBubble(msg.content);
                    }
                    if (msg.tool_calls) {
                        msg.tool_calls.forEach(tc => appendToolCard(tc));
                    }
                    if (msg.screenshots && msg.screenshots.length > 0) {
                        latestScreenshot = msg.screenshots[msg.screenshots.length - 1];
                    }
                }
            });

            if (latestScreenshot) {
                updateLiveScreen(latestScreenshot);
            }
            scrollToBottom();
        } catch (err) {
            console.error("Failed to load messages:", err);
        }
    }

    function connectWebSocket(sessionId) {
        if (ws) {
            ws.close();
        }

        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws/sessions/${sessionId}`;
        
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log("WebSocket connected to session:", sessionId);
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleStreamEvent(data);
        };

        ws.onclose = () => {
            console.log("WebSocket closed for session:", sessionId);
            updateStatusBadge("disconnected");
        };

        ws.onerror = (err) => {
            console.error("WebSocket error:", err);
        };
    }

    function handleStreamEvent(data) {
        switch (data.type) {
            case "status":
                const st = (data.status || "").toLowerCase();
                updateStatusBadge(data.status);
                if (st.includes("idle") || st.includes("completed") || st.includes("stopped") || st.includes("error")) {
                    stopBtnEl.disabled = true;
                    sendBtnEl.disabled = false;
                    promptInputEl.disabled = false;
                } else if (st.includes("running") || st.includes("step")) {
                    stopBtnEl.disabled = false;
                    sendBtnEl.disabled = true;
                    promptInputEl.disabled = true;
                }
                break;
            case "finished":
                updateStatusBadge("idle");
                stopBtnEl.disabled = true;
                sendBtnEl.disabled = false;
                promptInputEl.disabled = false;
                break;

            case "user_message":
                appendUserBubble(data.content);
                break;
            case "text":
                appendAssistantTextChunk(data.text);
                break;
            case "tool_use":
                appendToolCard(data);
                break;
            case "tool_result":
                appendToolResultCard(data);
                if (data.base64_image) {
                    updateLiveScreen(data.base64_image);
                }
                break;
            case "error":
                appendErrorCard(data.error);
                updateStatusBadge("error");
                stopBtnEl.disabled = true;
                sendBtnEl.disabled = false;
                break;
        }
        scrollToBottom();
    }

    function updateStatusBadge(status) {
        statusBadgeEl.className = `status-badge ${status}`;
        statusTextEl.textContent = status.charAt(0).toUpperCase() + status.slice(1);
    }

    // Update the right-side Desktop Viewer screen with screenshot
    function updateLiveScreen(base64Image) {
        if (!base64Image) return;
        const src = `data:image/png;base64,${base64Image}`;
        liveScreenshotImgEl.src = src;
        liveScreenshotImgEl.style.display = "block";
        if (vncPlaceholderEl) vncPlaceholderEl.style.display = "none";
        
        // Switch to desktop screen image container to show the screenshot
        if (currentVncMode === "screenshot") {
            canvasContainerEl.style.display = "flex";
            vncIframeEl.style.display = "none";
        }

        showToast("📸 Desktop Screen Updated");
    }

    function appendUserBubble(text) {
        const msgDiv = document.createElement("div");
        msgDiv.className = "chat-msg user";
        msgDiv.innerHTML = `<div class="chat-bubble">${escapeHtml(text)}</div>`;
        chatMessagesEl.appendChild(msgDiv);
    }

    function appendAssistantBubble(text) {
        if (!text) return;
        const msgDiv = document.createElement("div");
        msgDiv.className = "chat-msg assistant";
        msgDiv.innerHTML = `<div class="chat-bubble">${escapeHtml(text)}</div>`;
        chatMessagesEl.appendChild(msgDiv);
    }

    let currentAssistantBubble = null;
    function appendAssistantTextChunk(text) {
        if (!currentAssistantBubble) {
            const msgDiv = document.createElement("div");
            msgDiv.className = "chat-msg assistant";
            currentAssistantBubble = document.createElement("div");
            currentAssistantBubble.className = "chat-bubble";
            msgDiv.appendChild(currentAssistantBubble);
            chatMessagesEl.appendChild(msgDiv);
        }
        currentAssistantBubble.textContent += text;
    }

    function formatToolActionLabel(name, input) {
        if (name === "computer") {
            const action = input.action || "action";
            const coord = input.coordinate ? `[${input.coordinate[0]}, ${input.coordinate[1]}]` : "";
            const text = input.text ? `"${input.text}"` : "";

            switch (action) {
                case "left_click":
                    return `🖱️ Left click ${coord}`;
                case "right_click":
                    return `🖱️ Right click ${coord}`;
                case "double_click":
                    return `🖱️ Double click ${coord}`;
                case "mouse_move":
                    return `📍 Move mouse to ${coord}`;
                case "type":
                    return `⌨️ Type ${text}`;
                case "key":
                    return `⌨️ Press Key ${text}`;
                case "screenshot":
                    return `📸 Capture Desktop Screenshot`;
                default:
                    return `🖥️ Computer: ${action} ${coord} ${text}`.trim();
            }
        } else if (name === "bash") {
            const cmd = input.command ? `"${input.command.length > 40 ? input.command.substring(0, 37) + '...' : input.command}"` : "";
            return `💻 Bash Command: ${cmd}`;
        }
        return `⚙️ Tool Use: ${name}`;
    }

    function appendToolCard(data) {
        currentAssistantBubble = null;
        const card = document.createElement("div");
        card.className = "event-card tool_use";
        
        const label = formatToolActionLabel(data.name, data.input || {});
        card.innerHTML = `
            <div class="event-header">${escapeHtml(label)}</div>
            <div class="event-body">${escapeHtml(JSON.stringify(data.input || {}, null, 2))}</div>
        `;
        chatMessagesEl.appendChild(card);
    }

    function appendToolResultCard(data) {
        const card = document.createElement("div");
        card.className = "event-card tool_result";
        let content = data.output || data.error || "Action completed.";
        
        let extraBadge = "";
        if (data.base64_image) {
            extraBadge = `<div class="screenshot-inline-badge" title="Click to view desktop screenshot in full view">📸 Screenshot captured (Updated on Right Desktop Panel)</div>`;
        }

        card.innerHTML = `
            <div class="event-header">✅ Action Result</div>
            <div class="event-body">${escapeHtml(content)}</div>
            ${extraBadge}
        `;

        if (data.base64_image) {
            card.querySelector(".screenshot-inline-badge")?.addEventListener("click", () => {
                openLightbox(`data:image/png;base64,${data.base64_image}`, "Segment Desktop Screenshot");
            });
        }

        chatMessagesEl.appendChild(card);
    }

    function appendErrorCard(errMessage) {
        const card = document.createElement("div");
        card.className = "event-card error";
        card.innerHTML = `
            <div class="event-header">❌ Error</div>
            <div class="event-body">${escapeHtml(errMessage)}</div>
        `;
        chatMessagesEl.appendChild(card);
    }

    function openLightbox(imageSrc, caption) {
        lightboxImgEl.src = imageSrc;
        lightboxCaptionEl.textContent = caption || "Screenshot";
        lightboxModalEl.classList.add("active");
    }

    lightboxCloseBtnEl.addEventListener("click", () => {
        lightboxModalEl.classList.remove("active");
    });

    lightboxModalEl.addEventListener("click", (e) => {
        if (e.target === lightboxModalEl) {
            lightboxModalEl.classList.remove("active");
        }
    });

    liveScreenshotImgEl.addEventListener("click", () => {
        if (liveScreenshotImgEl.src) {
            openLightbox(liveScreenshotImgEl.src, "Live Virtual Desktop Screen");
        }
    });

    function scrollToBottom() {
        chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
    }

    // Prompt Form Submit
    promptFormEl.addEventListener("submit", async (e) => {
        e.preventDefault();
        const prompt = promptInputEl.value.trim();
        if (!prompt || !activeSessionId) return;

        promptInputEl.value = "";
        sendBtnEl.disabled = true;
        stopBtnEl.disabled = false;
        currentAssistantBubble = null;

        try {
            const res = await fetch(`/api/v1/sessions/${activeSessionId}/messages`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt })
            });

            if (res.status === 409) {
                appendErrorCard("Session is currently busy. Please wait for the task to complete.");
                sendBtnEl.disabled = false;
            }
        } catch (err) {
            console.error("Failed to send message:", err);
            sendBtnEl.disabled = false;
        }
    });

    // Stop Task Button
    stopBtnEl.addEventListener("click", async () => {
        if (!activeSessionId) return;
        try {
            await fetch(`/api/v1/sessions/${activeSessionId}/stop`, { method: "POST" });
            stopBtnEl.disabled = true;
        } catch (err) {
            console.error("Failed to stop task:", err);
        }
    });

    // Create Session Modal Handlers
    newSessionBtnEl.addEventListener("click", () => {
        createModalEl.classList.add("active");
    });

    modalCancelBtnEl.addEventListener("click", () => {
        createModalEl.classList.remove("active");
    });

    modalSubmitBtnEl.addEventListener("click", async () => {
        const title = sessionTitleInputEl.value.trim() || "New Session";
        const model = sessionModelSelectEl.value;

        try {
            const res = await fetch("/api/v1/sessions", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title, model })
            });
            const newSess = await res.json();
            createModalEl.classList.remove("active");
            await loadSessions();
            selectSession(newSess.id);
        } catch (err) {
            console.error("Failed to create session:", err);
        }
    });

    async function deleteSession(sessionId) {
        if (!confirm("Are you sure you want to delete this session?")) return;
        try {
            await fetch(`/api/v1/sessions/${sessionId}`, { method: "DELETE" });
            if (activeSessionId === sessionId) {
                activeSessionId = null;
                activeTitleEl.textContent = "Select or Create a Session";
                activeIdEl.textContent = "ID: --";
                chatMessagesEl.innerHTML = `<div class="welcome-card"><h3>Session Deleted</h3></div>`;
                promptInputEl.disabled = true;
                sendBtnEl.disabled = true;
            }
            await loadSessions();
        } catch (err) {
            console.error("Failed to delete session:", err);
        }
    }

    refreshVncBtnEl.addEventListener("click", () => {
        const host = window.location.hostname || "localhost";
        vncIframeEl.src = `http://${host}:6080/vnc.html?autoplay=true&reconnect=true`;
        setVncMode(currentVncMode);
        showToast("Screen viewer refreshed");
    });

    function escapeHtml(str) {
        if (!str) return "";
        return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }

    // Initial Load
    initVncUrls();
    loadSessions();
});
