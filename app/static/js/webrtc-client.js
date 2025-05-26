// app/static/js/webrtc-client.js
class GUIWebRTCClient {
    constructor(sessionId, container, options = {}) {
        this.sessionId = sessionId;
        this.container = container;
        this.options = {
            autoConnect: true,
            enableInput: true,
            scaleToFit: true,
            quality: 'high',
            frameRate: 30,
            ...options
        };
        
        // WebRTC components
        this.peerConnection = null;
        this.dataChannel = null;
        this.remoteStream = null;
        
        // Socket.IO connection
        this.socket = io();
        
        // GUI elements
        this.videoElement = null;
        this.canvasElement = null;
        this.canvasContext = null;
        
        // Input handling
        this.inputEnabled = false;
        this.mousePosition = { x: 0, y: 0 };
        this.isMouseDown = false;
        
        // Statistics
        this.stats = {
            framesReceived: 0,
            bytesReceived: 0,
            lastFrameTime: 0,
            fps: 0,
            latency: 0
        };
        
        // Initialize
        this.init();
    }
    
    async init() {
        try {
            this.setupGUI();
            await this.setupWebRTC();
            this.setupSocketIO();
            
            if (this.options.autoConnect) {
                await this.connect();
            }
            
            console.log('GUIWebRTCClient initialized');
        } catch (error) {
            console.error('Error initializing GUIWebRTCClient:', error);
            this.handleError('Initialization failed', error);
        }
    }
    
    setupGUI() {
        // Create video element for WebRTC stream
        this.videoElement = document.createElement('video');
        this.videoElement.style.cssText = `
            width: 100%;
            height: 100%;
            object-fit: ${this.options.scaleToFit ? 'contain' : 'fill'};
            background: #000;
            display: none;
        `;
        this.videoElement.autoplay = true;
        this.videoElement.muted = true;
        this.videoElement.playsInline = true;
        
        // Create canvas for frame-based streaming fallback
        this.canvasElement = document.createElement('canvas');
        this.canvasElement.style.cssText = `
            width: 100%;
            height: 100%;
            object-fit: ${this.options.scaleToFit ? 'contain' : 'fill'};
            background: #000;
            cursor: pointer;
        `;
        this.canvasContext = this.canvasElement.getContext('2d');
        
        // Add elements to container
        this.container.appendChild(this.videoElement);
        this.container.appendChild(this.canvasElement);
        
        // Setup input handlers
        if (this.options.enableInput) {
            this.setupInputHandlers();
        }
        
        // Setup resize handler
        window.addEventListener('resize', () => this.handleResize());
        this.handleResize();
    }
    
    setupInputHandlers() {
        const canvas = this.canvasElement;
        const video = this.videoElement;
        
        // Mouse events
        const handleMouseEvent = (event, type) => {
            if (!this.inputEnabled) return;
            
            event.preventDefault();
            event.stopPropagation();
            
            const rect = (canvas.style.display !== 'none' ? canvas : video).getBoundingClientRect();
            const scaleX = this.canvasElement.width / rect.width;
            const scaleY = this.canvasElement.height / rect.height;
            
            const x = Math.round((event.clientX - rect.left) * scaleX);
            const y = Math.round((event.clientY - rect.top) * scaleY);
            
            this.mousePosition = { x, y };
            
            if (type === 'mousemove') {
                this.sendInputEvent('mouse_move', { x, y });
            } else if (type === 'mousedown') {
                this.isMouseDown = true;
                this.sendInputEvent('mouse_click', { 
                    x, y, 
                    button: event.button + 1, // X11 buttons are 1-based
                    action: 'down'
                });
            } else if (type === 'mouseup') {
                this.isMouseDown = false;
                this.sendInputEvent('mouse_click', { 
                    x, y, 
                    button: event.button + 1,
                    action: 'up'
                });
            } else if (type === 'wheel') {
                this.sendInputEvent('mouse_wheel', {
                    x, y,
                    deltaX: event.deltaX,
                    deltaY: event.deltaY
                });
            }
        };
        
        // Add mouse event listeners to both elements
        [canvas, video].forEach(element => {
            element.addEventListener('mousemove', (e) => handleMouseEvent(e, 'mousemove'));
            element.addEventListener('mousedown', (e) => handleMouseEvent(e, 'mousedown'));
            element.addEventListener('mouseup', (e) => handleMouseEvent(e, 'mouseup'));
            element.addEventListener('wheel', (e) => handleMouseEvent(e, 'wheel'));
            element.addEventListener('contextmenu', (e) => e.preventDefault());
        });
        
        // Keyboard events (capture on document)
        const handleKeyEvent = (event, action) => {
            if (!this.inputEnabled) return;
            
            // Don't capture certain browser shortcuts
            if (event.ctrlKey && ['r', 'f5', 't', 'w'].includes(event.key.toLowerCase())) {
                return;
            }
            
            event.preventDefault();
            event.stopPropagation();
            
            const keyData = {
                key: this.mapKeyToX11(event.key, event.code),
                keyCode: event.keyCode,
                code: event.code,
                ctrlKey: event.ctrlKey,
                shiftKey: event.shiftKey,
                altKey: event.altKey,
                metaKey: event.metaKey,
                action: action
            };
            
            if (action === 'keydown') {
                this.sendInputEvent('key_press', keyData);
            } else if (action === 'keyup') {
                this.sendInputEvent('key_release', keyData);
            }
        };
        
        // Focus handling
        canvas.tabIndex = 0;
        video.tabIndex = 0;
        
        document.addEventListener('keydown', (e) => {
            if (document.activeElement === canvas || document.activeElement === video) {
                handleKeyEvent(e, 'keydown');
            }
        });
        
        document.addEventListener('keyup', (e) => {
            if (document.activeElement === canvas || document.activeElement === video) {
                handleKeyEvent(e, 'keyup');
            }
        });
        
        // Text input for typing
        const textInput = document.createElement('input');
        textInput.type = 'text';
        textInput.style.cssText = 'position: absolute; left: -9999px; opacity: 0;';
        document.body.appendChild(textInput);
        
        textInput.addEventListener('input', (event) => {
            if (!this.inputEnabled) return;
            
            const text = event.target.value;
            if (text) {
                this.sendInputEvent('key_type', { text });
                textInput.value = ''; // Clear for next input
            }
        });
        
        // Double-click to focus text input for typing
        [canvas, video].forEach(element => {
            element.addEventListener('dblclick', () => {
                if (this.inputEnabled) {
                    textInput.focus();
                }
            });
        });
    }
    
    mapKeyToX11(key, code) {
        // Map JavaScript key names to X11 key names
        const keyMap = {
            'Enter': 'Return',
            ' ': 'space',
            'Escape': 'Escape',
            'Backspace': 'BackSpace',
            'Delete': 'Delete',
            'Tab': 'Tab',
            'ArrowUp': 'Up',
            'ArrowDown': 'Down',
            'ArrowLeft': 'Left',
            'ArrowRight': 'Right',
            'Home': 'Home',
            'End': 'End',
            'PageUp': 'Page_Up',
            'PageDown': 'Page_Down',
            'F1': 'F1', 'F2': 'F2', 'F3': 'F3', 'F4': 'F4',
            'F5': 'F5', 'F6': 'F6', 'F7': 'F7', 'F8': 'F8',
            'F9': 'F9', 'F10': 'F10', 'F11': 'F11', 'F12': 'F12',
            'Control': 'ctrl',
            'Alt': 'alt',
            'Shift': 'shift',
            'Meta': 'Super_L'
        };
        
        return keyMap[key] || key.toLowerCase();
    }
    
    async setupWebRTC() {
        // Create peer connection
        this.peerConnection = new RTCPeerConnection({
            iceServers: [
                { urls: 'stun:stun.l.google.com:19302' },
                { urls: 'stun:stun1.l.google.com:19302' }
            ]
        });
        
        // Handle incoming stream
        this.peerConnection.ontrack = (event) => {
            console.log('Received remote stream');
            this.remoteStream = event.streams[0];
            this.videoElement.srcObject = this.remoteStream;
            this.videoElement.style.display = 'block';
            this.canvasElement.style.display = 'none';
            this.inputEnabled = true;
        };
        
        // Handle ICE candidates
        this.peerConnection.onicecandidate = (event) => {
            if (event.candidate) {
                this.socket.emit('gui_webrtc_ice_candidate', {
                    session_id: this.sessionId,
                    candidate: event.candidate
                });
            }
        };
        
        // Handle connection state changes
        this.peerConnection.onconnectionstatechange = () => {
            console.log('WebRTC connection state:', this.peerConnection.connectionState);
            
            if (this.peerConnection.connectionState === 'connected') {
                this.onWebRTCConnected();
            } else if (this.peerConnection.connectionState === 'disconnected' || 
                      this.peerConnection.connectionState === 'failed') {
                this.onWebRTCDisconnected();
            }
        };
        
        // Create data channel for low-latency input
        this.dataChannel = this.peerConnection.createDataChannel('input', {
            ordered: false, // Allow out-of-order delivery for lower latency
            maxRetransmits: 0
        });
        
        this.dataChannel.onopen = () => {
            console.log('Data channel opened');
        };
        
        this.dataChannel.onerror = (error) => {
            console.error('Data channel error:', error);
        };
    }
    
    setupSocketIO() {
        // Handle GUI-specific events
        this.socket.on('gui_connected', (data) => {
            console.log('Connected to GUI session:', data);
            this.onConnected(data);
        });
        
        this.socket.on('gui_frame', (data) => {
            if (data.session_id === this.sessionId) {
                this.handleFrameData(data);
            }
        });
        
        this.socket.on('webrtc_answer', (data) => {
            this.handleWebRTCAnswer(data);
        });
        
        this.socket.on('webrtc_ice_candidate', (data) => {
            this.handleWebRTCIceCandidate(data);
        });
        
        this.socket.on('gui_error', (data) => {
            console.error('GUI error:', data.error);
            this.handleError('GUI Error', data.error);
        });
        
        this.socket.on('disconnect', () => {
            console.log('Socket disconnected');
            this.inputEnabled = false;
        });
        
        this.socket.on('reconnect', () => {
            console.log('Socket reconnected');
            this.connect();
        });
    }
    
    async connect() {
        try {
            // Connect via Socket.IO
            this.socket.emit('gui_connect', {
                session_id: this.sessionId
            });
            
            // Try to establish WebRTC connection
            await this.startWebRTCConnection();
            
        } catch (error) {
            console.error('Error connecting:', error);
            this.handleError('Connection failed', error);
        }
    }
    
    async startWebRTCConnection() {
        try {
            // Create offer
            const offer = await this.peerConnection.createOffer({
                offerToReceiveVideo: true,
                offerToReceiveAudio: false
            });
            
            await this.peerConnection.setLocalDescription(offer);
            
            // Send offer via Socket.IO
            this.socket.emit('gui_webrtc_offer', {
                session_id: this.sessionId,
                offer: offer
            });
            
        } catch (error) {
            console.error('Error creating WebRTC offer:', error);
            throw error;
        }
    }
    
    async handleWebRTCAnswer(answerData) {
        try {
            const answer = new RTCSessionDescription(answerData);
            await this.peerConnection.setRemoteDescription(answer);
            
        } catch (error) {
            console.error('Error handling WebRTC answer:', error);
        }
    }
    
    async handleWebRTCIceCandidate(candidateData) {
        try {
            const candidate = new RTCIceCandidate(candidateData);
            await this.peerConnection.addIceCandidate(candidate);
            
        } catch (error) {
            console.error('Error handling ICE candidate:', error);
        }
    }
    
    handleFrameData(frameData) {
        // Handle frame-based streaming (fallback when WebRTC is not available)
        try {
            const img = new Image();
            img.onload = () => {
                // Update canvas size if needed
                if (this.canvasElement.width !== img.width || this.canvasElement.height !== img.height) {
                    this.canvasElement.width = img.width;
                    this.canvasElement.height = img.height;
                    this.handleResize();
                }
                
                // Draw frame
                this.canvasContext.drawImage(img, 0, 0);
                
                // Update statistics
                this.stats.framesReceived++;
                this.stats.lastFrameTime = Date.now();
                this.updateFPS();
                
                // Enable input if not already enabled
                if (!this.inputEnabled) {
                    this.inputEnabled = true;
                    this.canvasElement.style.display = 'block';
                    this.videoElement.style.display = 'none';
                }
            };
            
            img.src = frameData.frame_data;
            
        } catch (error) {
            console.error('Error handling frame data:', error);
        }
    }
    
    sendInputEvent(type, data) {
        try {
            const inputData = {
                type: type,
                data: data,
                timestamp: Date.now()
            };
            
            // Try to send via data channel first (lower latency)
            if (this.dataChannel && this.dataChannel.readyState === 'open') {
                this.dataChannel.send(JSON.stringify(inputData));
            } else {
                // Fallback to Socket.IO
                this.socket.emit('gui_input', {
                    session_id: this.sessionId,
                    ...inputData
                });
            }
            
        } catch (error) {
            console.error('Error sending input event:', error);
        }
    }
    
    onConnected(data) {
        console.log('GUI session connected:', data);
        
        // Set canvas size based on remote resolution
        if (data.screen_resolution) {
            this.canvasElement.width = data.screen_resolution.width;
            this.canvasElement.height = data.screen_resolution.height;
            this.handleResize();
        }
        
        // Update UI or trigger callbacks
        if (this.options.onConnected) {
            this.options.onConnected(data);
        }
    }
    
    onWebRTCConnected() {
        console.log('WebRTC connection established');
        this.inputEnabled = true;
        
        if (this.options.onWebRTCConnected) {
            this.options.onWebRTCConnected();
        }
    }
    
    onWebRTCDisconnected() {
        console.log('WebRTC connection lost, falling back to frame streaming');
        this.inputEnabled = false;
        
        // Show canvas for frame-based streaming
        this.videoElement.style.display = 'none';
        this.canvasElement.style.display = 'block';
        
        if (this.options.onWebRTCDisconnected) {
            this.options.onWebRTCDisconnected();
        }
    }
    
    handleResize() {
        // Maintain aspect ratio while fitting container
        const container = this.container;
        const containerRect = container.getBoundingClientRect();
        
        if (this.options.scaleToFit) {
            const canvasAspect = this.canvasElement.width / this.canvasElement.height;
            const containerAspect = containerRect.width / containerRect.height;
            
            let displayWidth, displayHeight;
            
            if (canvasAspect > containerAspect) {
                // Canvas is wider than container
                displayWidth = containerRect.width;
                displayHeight = containerRect.width / canvasAspect;
            } else {
                // Canvas is taller than container
                displayWidth = containerRect.height * canvasAspect;
                displayHeight = containerRect.height;
            }
            
            // Apply to both elements
            [this.canvasElement, this.videoElement].forEach(element => {
                element.style.width = displayWidth + 'px';
                element.style.height = displayHeight + 'px';
            });
        }
    }
    
    updateFPS() {
        const now = Date.now();
        if (this.lastFPSUpdate) {
            const elapsed = now - this.lastFPSUpdate;
            if (elapsed >= 1000) { // Update every second
                this.stats.fps = Math.round((this.stats.framesReceived - this.lastFrameCount) * 1000 / elapsed);
                this.lastFrameCount = this.stats.framesReceived;
                this.lastFPSUpdate = now;
                
                // Trigger stats callback
                if (this.options.onStatsUpdate) {
                    this.options.onStatsUpdate(this.stats);
                }
            }
        } else {
            this.lastFPSUpdate = now;
            this.lastFrameCount = this.stats.framesReceived;
        }
    }
    
    handleError(title, error) {
        console.error(title + ':', error);
        
        if (this.options.onError) {
            this.options.onError(title, error);
        } else {
            // Default error handling
            this.showError(title + ': ' + (error.message || error));
        }
    }
    
    showError(message) {
        // Create simple error overlay
        const errorDiv = document.createElement('div');
        errorDiv.style.cssText = `
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(220, 53, 69, 0.9);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            z-index: 1000;
            max-width: 80%;
        `;
        errorDiv.innerHTML = `
            <h4>Connection Error</h4>
            <p>${message}</p>
            <button onclick="this.parentElement.remove()" style="
                background: white;
                color: #dc3545;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                cursor: pointer;
                margin-top: 10px;
            ">Close</button>
        `;
        
        this.container.appendChild(errorDiv);
        
        // Auto-remove after 10 seconds
        setTimeout(() => {
            if (errorDiv.parentElement) {
                errorDiv.remove();
            }
        }, 10000);
    }
    
    // Public methods
    
    disconnect() {
        try {
            this.inputEnabled = false;
            
            // Close WebRTC connection
            if (this.peerConnection) {
                this.peerConnection.close();
                this.peerConnection = null;
            }
            
            // Close data channel
            if (this.dataChannel) {
                this.dataChannel.close();
                this.dataChannel = null;
            }
            
            // Disconnect socket
            this.socket.emit('gui_disconnect', {
                session_id: this.sessionId
            });
            
            console.log('Disconnected from GUI session');
            
        } catch (error) {
            console.error('Error disconnecting:', error);
        }
    }
    
    setInputEnabled(enabled) {
        this.inputEnabled = enabled;
        
        // Update cursor style
        const cursor = enabled ? 'pointer' : 'not-allowed';
        this.canvasElement.style.cursor = cursor;
        this.videoElement.style.cursor = cursor;
    }
    
    setQuality(quality) {
        // Adjust quality settings
        this.options.quality = quality;
        
        const qualitySettings = {
            'low': { frameRate: 15, bitrate: 500 },
            'medium': { frameRate: 24, bitrate: 1000 },
            'high': { frameRate: 30, bitrate: 2000 },
            'ultra': { frameRate: 60, bitrate: 4000 }
        };
        
        const settings = qualitySettings[quality] || qualitySettings['medium'];
        this.options.frameRate = settings.frameRate;
        this.options.bitrate = settings.bitrate;
        
        // Update WebRTC sender parameters if connection exists
        if (this.peerConnection && this.peerConnection.connectionState === 'connected') {
            const sender = this.peerConnection.getSenders().find(s => 
                s.track && s.track.kind === 'video'
            );
            
            if (sender) {
                const params = sender.getParameters();
                if (params.encodings && params.encodings[0]) {
                    params.encodings[0].maxBitrate = settings.bitrate * 1000; // Convert to bps
                    sender.setParameters(params);
                }
            }
        }
    }
    
    takeScreenshot() {
        try {
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            
            if (this.videoElement.style.display !== 'none' && this.remoteStream) {
                // Capture from video element
                canvas.width = this.videoElement.videoWidth;
                canvas.height = this.videoElement.videoHeight;
                ctx.drawImage(this.videoElement, 0, 0);
            } else {
                // Capture from canvas
                canvas.width = this.canvasElement.width;
                canvas.height = this.canvasElement.height;
                ctx.drawImage(this.canvasElement, 0, 0);
            }
            
            // Convert to blob and trigger download
            canvas.toBlob((blob) => {
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `gui-session-${this.sessionId}-${Date.now()}.png`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            });
            
        } catch (error) {
            console.error('Error taking screenshot:', error);
        }
    }
    
    getStats() {
        return { ...this.stats };
    }
    
    // Utility methods for advanced input
    
    sendKeySequence(keys, delay = 100) {
        // Send a sequence of keys with delay
        const sendNextKey = (index) => {
            if (index >= keys.length) return;
            
            const key = keys[index];
            this.sendInputEvent('key_press', { key });
            
            setTimeout(() => {
                this.sendInputEvent('key_release', { key });
                setTimeout(() => sendNextKey(index + 1), delay);
            }, 50);
        };
        
        sendNextKey(0);
    }
    
    sendText(text) {
        // Send text as typing events
        this.sendInputEvent('key_type', { text });
    }
    
    sendMouseClick(x, y, button = 1) {
        // Send mouse click at specific coordinates
        this.sendInputEvent('mouse_click', { x, y, button, action: 'down' });
        setTimeout(() => {
            this.sendInputEvent('mouse_click', { x, y, button, action: 'up' });
        }, 50);
    }
    
    sendKeyboardShortcut(shortcut) {
        // Send common keyboard shortcuts
        const shortcuts = {
            'copy': ['ctrl', 'c'],
            'paste': ['ctrl', 'v'],
            'cut': ['ctrl', 'x'],
            'undo': ['ctrl', 'z'],
            'redo': ['ctrl', 'y'],
            'save': ['ctrl', 's'],
            'refresh': ['F5'],
            'fullscreen': ['F11'],
            'alt_tab': ['alt', 'Tab']
        };
        
        const keys = shortcuts[shortcut];
        if (keys) {
            // Press all keys
            keys.forEach(key => {
                this.sendInputEvent('key_press', { key });
            });
            
            // Release all keys in reverse order
            setTimeout(() => {
                keys.reverse().forEach((key, index) => {
                    setTimeout(() => {
                        this.sendInputEvent('key_release', { key });
                    }, index * 10);
                });
            }, 100);
        }
    }
}

// GUI Viewer Controller Class
class GUIViewer {
    constructor(containerId, sessionId, options = {}) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            throw new Error(`Container element with id '${containerId}' not found`);
        }
        
        this.sessionId = sessionId;
        this.options = {
            showToolbar: true,
            showStats: false,
            enableFullscreen: true,
            enableScreenshots: true,
            ...options
        };
        
        this.client = null;
        this.toolbar = null;
        this.statsPanel = null;
        this.isFullscreen = false;
        
        this.init();
    }
    
    init() {
        // Setup container
        this.container.style.position = 'relative';
        this.container.style.overflow = 'hidden';
        
        // Create viewer area
        this.viewerArea = document.createElement('div');
        this.viewerArea.style.cssText = `
            width: 100%;
            height: 100%;
            position: relative;
            background: #000;
        `;
        this.container.appendChild(this.viewerArea);
        
        // Create toolbar
        if (this.options.showToolbar) {
            this.createToolbar();
        }
        
        // Create stats panel
        if (this.options.showStats) {
            this.createStatsPanel();
        }
        
        // Initialize WebRTC client
        this.client = new GUIWebRTCClient(this.sessionId, this.viewerArea, {
            onConnected: (data) => this.onConnected(data),
            onWebRTCConnected: () => this.onWebRTCConnected(),
            onWebRTCDisconnected: () => this.onWebRTCDisconnected(),
            onStatsUpdate: (stats) => this.updateStats(stats),
            onError: (title, error) => this.showError(title, error)
        });
        
        // Setup fullscreen handling
        document.addEventListener('fullscreenchange', () => {
            this.isFullscreen = document.fullscreenElement === this.container;
            this.updateToolbar();
        });
    }
    
    createToolbar() {
        this.toolbar = document.createElement('div');
        this.toolbar.style.cssText = `
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(0, 0, 0, 0.8);
            border-radius: 8px;
            padding: 8px;
            display: flex;
            gap: 8px;
            z-index: 100;
            opacity: 0.8;
            transition: opacity 0.3s;
        `;
        
        // Hide toolbar on mouse leave, show on hover
        this.toolbar.addEventListener('mouseenter', () => {
            this.toolbar.style.opacity = '1';
        });
        
        this.toolbar.addEventListener('mouseleave', () => {
            this.toolbar.style.opacity = '0.8';
        });
        
        // Create toolbar buttons
        const buttons = [
            {
                icon: 'arrows-fullscreen',
                title: 'Fullscreen',
                onClick: () => this.toggleFullscreen()
            },
            {
                icon: 'camera',
                title: 'Screenshot',
                onClick: () => this.takeScreenshot()
            },
            {
                icon: 'gear',
                title: 'Settings',
                onClick: () => this.showSettings()
            },
            {
                icon: 'graph-up',
                title: 'Stats',
                onClick: () => this.toggleStats()
            }
        ];
        
        buttons.forEach(btn => {
            const button = document.createElement('button');
            button.style.cssText = `
                background: transparent;
                border: 1px solid rgba(255, 255, 255, 0.3);
                color: white;
                padding: 8px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                transition: background 0.2s;
            `;
            button.innerHTML = `<i class="bi bi-${btn.icon}"></i>`;
            button.title = btn.title;
            button.addEventListener('click', btn.onClick);
            
            button.addEventListener('mouseenter', () => {
                button.style.background = 'rgba(255, 255, 255, 0.2)';
            });
            
            button.addEventListener('mouseleave', () => {
                button.style.background = 'transparent';
            });
            
            this.toolbar.appendChild(button);
        });
        
        this.container.appendChild(this.toolbar);
    }
    
    createStatsPanel() {
        this.statsPanel = document.createElement('div');
        this.statsPanel.style.cssText = `
            position: absolute;
            top: 10px;
            left: 10px;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 12px;
            border-radius: 8px;
            font-family: monospace;
            font-size: 12px;
            z-index: 100;
            display: none;
        `;
        
        this.container.appendChild(this.statsPanel);
    }
    
    onConnected(data) {
        console.log('GUI viewer connected:', data);
    }
    
    onWebRTCConnected() {
        this.showNotification('WebRTC connected - High quality streaming enabled', 'success');
    }
    
    onWebRTCDisconnected() {
        this.showNotification('WebRTC disconnected - Using fallback streaming', 'warning');
    }
    
    updateStats(stats) {
        if (this.statsPanel && this.statsPanel.style.display !== 'none') {
            this.statsPanel.innerHTML = `
                <div>FPS: ${stats.fps}</div>
                <div>Frames: ${stats.framesReceived}</div>
                <div>Latency: ${stats.latency}ms</div>
                <div>Quality: ${this.client.options.quality}</div>
            `;
        }
    }
    
    toggleFullscreen() {
        if (this.options.enableFullscreen) {
            if (!this.isFullscreen) {
                this.container.requestFullscreen();
            } else {
                document.exitFullscreen();
            }
        }
    }
    
    takeScreenshot() {
        if (this.options.enableScreenshots && this.client) {
            this.client.takeScreenshot();
            this.showNotification('Screenshot saved', 'success');
        }
    }
    
    toggleStats() {
        if (this.statsPanel) {
            const isVisible = this.statsPanel.style.display !== 'none';
            this.statsPanel.style.display = isVisible ? 'none' : 'block';
        }
    }
    
    showSettings() {
        // Create settings modal (simplified)
        const modal = document.createElement('div');
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 1000;
        `;
        
        const panel = document.createElement('div');
        panel.style.cssText = `
            background: white;
            padding: 20px;
            border-radius: 8px;
            max-width: 400px;
            width: 90%;
        `;
        
        panel.innerHTML = `
            <h3>GUI Viewer Settings</h3>
            <div style="margin: 15px 0;">
                <label>Quality:</label>
                <select id="quality-select" style="margin-left: 10px; padding: 5px;">
                    <option value="low">Low</option>
                    <option value="medium" selected>Medium</option>
                    <option value="high">High</option>
                    <option value="ultra">Ultra</option>
                </select>
            </div>
            <div style="margin: 15px 0;">
                <label>
                    <input type="checkbox" id="input-enabled" checked> Enable Input
                </label>
            </div>
            <div style="text-align: right; margin-top: 20px;">
                <button id="close-settings" style="padding: 8px 16px;">Close</button>
            </div>
        `;
        
        modal.appendChild(panel);
        document.body.appendChild(modal);
        
        // Handle settings changes
        panel.querySelector('#quality-select').addEventListener('change', (e) => {
            this.client.setQuality(e.target.value);
        });
        
        panel.querySelector('#input-enabled').addEventListener('change', (e) => {
            this.client.setInputEnabled(e.target.checked);
        });
        
        panel.querySelector('#close-settings').addEventListener('click', () => {
            modal.remove();
        });
        
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
    }
    
    updateToolbar() {
        // Update toolbar button states based on current state
        if (this.toolbar) {
            const fullscreenBtn = this.toolbar.querySelector('button[title="Fullscreen"] i');
            if (fullscreenBtn) {
                fullscreenBtn.className = this.isFullscreen ? 
                    'bi bi-fullscreen-exit' : 'bi bi-arrows-fullscreen';
            }
        }
    }
    
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: absolute;
            top: 50px;
            left: 50%;
            transform: translateX(-50%);
            background: ${type === 'success' ? '#28a745' : type === 'warning' ? '#ffc107' : '#17a2b8'};
            color: white;
            padding: 10px 20px;
            border-radius: 4px;
            z-index: 200;
            animation: fadeInOut 3s forwards;
        `;
        
        notification.textContent = message;
        this.container.appendChild(notification);
        
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 3000);
    }
    
    showError(title, error) {
        this.showNotification(`${title}: ${error.message || error}`, 'error');
    }
    
    // Public methods
    disconnect() {
        if (this.client) {
            this.client.disconnect();
        }
    }
    
    setQuality(quality) {
        if (this.client) {
            this.client.setQuality(quality);
        }
    }
    
    enableInput(enabled) {
        if (this.client) {
            this.client.setInputEnabled(enabled);
        }
    }
}