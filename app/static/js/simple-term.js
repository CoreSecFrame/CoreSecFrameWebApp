// app/static/js/simple-term.js
class SimpleTerm {
    constructor(sessionId, element) {
        this.sessionId = sessionId;
        this.element = element;
        this.term = new Terminal({
            cursorBlink: true,
            fontSize: 14,
            fontFamily: 'Menlo, Monaco, "Courier New", monospace',
            theme: {
                background: '#000000',
                foreground: '#f0f0f0'
            }
        });
        
        this.socket = io();
        this.currentLine = '';
        this.commandHistory = [];
        this.historyIndex = -1;
        this.initialized = false;
        this.readOnly = false;  // Default to interactive mode
        
        // Initialize terminal
        this.term.open(element);
        this.term.write('Initializing terminal...\r\n');
        this.term.focus();
        
        // Connect to socket
        this.socket.on('connect', () => {
            console.log('Socket connected');
            
            // Join session
            this.socket.emit('terminal_connect', { 
                session_id: this.sessionId 
            });
            
            // Request buffer to restore session
            this.socket.emit('terminal_get_buffer', {
                session_id: this.sessionId
            });
            
            // Write connecting message if not initialized
            if (!this.initialized) {
                this.term.write('\r\nConnecting to terminal...\r\n');
            }
        });
        
        this.socket.on('terminal_buffer', (data) => {
            console.log('Received terminal buffer:', data);
            
            // Update read-only status
            this.readOnly = !!data.read_only;
            
            if (data.buffer) {
                // Clear terminal and write buffer
                this.term.clear();
                this.term.write(data.buffer);
                this.initialized = true;
                
                // If in read-only mode, add a notice
                if (this.readOnly) {
                    this.term.write('\r\n\x1b[1;33m[Read-Only Mode: This session is inactive and cannot accept input]\x1b[0m\r\n');
                } else {
                    // Add prompt for interactive mode
                    this.term.write('\r\n$ ');
                }
            } else {
                // No buffer available
                this.term.clear();
                if (this.readOnly) {
                    this.term.write('\r\n\x1b[1;33m[Read-Only Mode: This session is inactive - No logs available]\x1b[0m\r\n');
                } else {
                    this.term.write('\r\n$ ');
                }
            }
            
            // Store command history
            if (data.history && Array.isArray(data.history)) {
                console.log('Received command history:', data.history.length, 'commands');
                this.commandHistory = data.history;
                this.historyIndex = this.commandHistory.length;
            }
        });
        
        // Handle output from server
        this.socket.on('terminal_output', (data) => {
            console.log('Received output:', data.length + ' chars');
            if (typeof data === 'string') {
                this.term.write(data);
            }
        });
        
        // Handle user input (only when not in read-only mode)
        this.term.onKey(({ key, domEvent }) => {
            // Skip input handling in read-only mode
            if (this.readOnly) {
                return;
            }
            
            const printable = !domEvent.altKey && !domEvent.ctrlKey && !domEvent.metaKey;
            
            if (domEvent.keyCode === 13) { // Enter key
                // Send the current line as a command
                this.term.write('\r\n');
                if (this.currentLine.trim() !== '') {
                    this.sendCommand(this.currentLine);
                    this.addToHistory(this.currentLine);
                } else {
                    // Empty line, just show prompt
                    this.socket.emit('terminal_newline', { session_id: this.sessionId });
                }
                this.currentLine = '';
                this.historyIndex = -1;
            } else if (domEvent.keyCode === 8) { // Backspace
                // Remove the last character from the current line
                if (this.currentLine.length > 0) {
                    this.currentLine = this.currentLine.slice(0, -1);
                    this.term.write('\b \b');
                }
            } else if (domEvent.keyCode === 38) { // Up arrow
                // Navigate command history
                if (this.commandHistory.length > 0) {
                    if (this.historyIndex === -1) {
                        this.historyIndex = this.commandHistory.length - 1;
                    } else if (this.historyIndex > 0) {
                        this.historyIndex--;
                    }
                    
                    // Clear current line
                    this.term.write('\r\x1B[K$ ' + this.commandHistory[this.historyIndex]);
                    this.currentLine = this.commandHistory[this.historyIndex];
                }
            } else if (domEvent.keyCode === 40) { // Down arrow
                // Navigate command history
                if (this.historyIndex < this.commandHistory.length - 1) {
                    this.historyIndex++;
                    this.term.write('\r\x1B[K$ ' + this.commandHistory[this.historyIndex]);
                    this.currentLine = this.commandHistory[this.historyIndex];
                } else {
                    // End of history, clear line
                    this.historyIndex = -1;
                    this.term.write('\r\x1B[K$ ');
                    this.currentLine = '';
                }
            } else if (printable) {
                // Add printable characters to the current line
                this.currentLine += key;
                this.term.write(key);
            }
        });
        
        // Socket disconnect
        this.socket.on('disconnect', () => {
            console.log('Socket disconnected');
            this.term.write('\r\n\r\nDisconnected from server. Please refresh the page.\r\n');
        });
    }
    
    sendCommand(command) {
        // Don't send commands in read-only mode
        if (this.readOnly) {
            return;
        }
        
        console.log('Sending command:', command);
        this.socket.emit('terminal_command', {
            session_id: this.sessionId,
            command: command
        });
    }
    
    addToHistory(command) {
        if (command.trim() !== '' && 
            (this.commandHistory.length === 0 || 
             this.commandHistory[this.commandHistory.length - 1] !== command)) {
            this.commandHistory.push(command);
            if (this.commandHistory.length > 100) {
                this.commandHistory.shift(); // Keep history to a reasonable size
            }
            this.historyIndex = this.commandHistory.length;
        }
    }
    
    focus() {
        this.term.focus();
    }
    
    clear() {
        this.term.clear();
        if (!this.readOnly) {
            this.term.write('$ ');
        }
    }
    
    testWrite(text) {
        this.term.write(text);
    }
    
    isReadOnly() {
        return this.readOnly;
    }
}