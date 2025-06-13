document.addEventListener('DOMContentLoaded', function () {
    const terminalContainer = document.getElementById('terminalContainer');
    if (!terminalContainer) {
        console.error("Terminal container not found. Terminal will not initialize.");
        return;
    }

    const sessionId = terminalContainer.dataset.sessionId;
    const isOwner = terminalContainer.dataset.isOwner === 'true';
    const isActive = terminalContainer.dataset.isActive === 'true';
    const urlExecuteModule = terminalContainer.dataset.urlExecuteModule;
    const csrfToken = terminalContainer.dataset.csrfToken; // Added for explicit use if needed
    const moduleToExecuteStr = terminalContainer.dataset.moduleToExecute;
    let moduleToExecute = null;
    try {
        if (moduleToExecuteStr && moduleToExecuteStr !== 'null') {
            moduleToExecute = JSON.parse(moduleToExecuteStr);
        }
    } catch (e) {
        console.error("Error parsing module_to_execute data:", e, moduleToExecuteStr);
    }


    // Function to get terminal colors (always dark theme)
    function getTerminalColors() {
        return {
            background: '#0c0c0c',
            foreground: '#cccccc',
            cursor: '#ffffff',
            cursorAccent: '#0c0c0c',
            selectionBackground: '#264f78',
            selectionForeground: '#ffffff',
            black: '#0c0c0c',
            red: '#e74856',
            green: '#16c60c',
            yellow: '#f9f1a5',
            blue: '#3b78ff',
            magenta: '#b4009e',
            cyan: '#61d6d6',
            white: '#cccccc',
            brightBlack: '#767676',
            brightRed: '#e74856',
            brightGreen: '#16c60c',
            brightYellow: '#f9f1a5',
            brightBlue: '#3b78ff',
            brightMagenta: '#b4009e',
            brightCyan: '#61d6d6',
            brightWhite: '#f2f2f2'
        };
    }

    if (isOwner) {
        const terminal = new Terminal({
            cursorBlink: true,
            fontFamily: 'Cascadia Code, Consolas, Monaco, "Courier New", monospace',
            fontSize: 14,
            lineHeight: 1.2,
            theme: getTerminalColors(),
            allowTransparency: false,
            scrollback: 5000,
            convertEol: true,
            cols: 80,
            rows: 24
        });

        const fitAddon = new FitAddon.FitAddon();
        const webLinksAddon = new WebLinksAddon.WebLinksAddon();
        const searchAddon = new SearchAddon.SearchAddon();

        terminal.loadAddon(fitAddon);
        terminal.loadAddon(webLinksAddon);
        terminal.loadAddon(searchAddon);

        const terminalElement = document.getElementById('terminal');
        if (terminalElement) {
            terminal.open(terminalElement);
            setTimeout(() => {
                fitAddon.fit();
            }, 100);
        }

        let resizeTimeout;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                fitAddon.fit();
                const dimensions = fitAddon.proposeDimensions();
                if (dimensions && socket && socket.connected) {
                    socket.emit('terminal_resize', {
                        session_id: sessionId,
                        rows: dimensions.rows,
                        cols: dimensions.cols
                    });
                }
            }, 250);
        });

        const socket = io();
        let isConnected = false;

        socket.on('connect', () => {
            console.log('Socket connected');
            isConnected = true;
            socket.emit('terminal_connect', { session_id: sessionId });
            socket.emit('terminal_get_buffer', { session_id: sessionId });
            const dimensions = fitAddon.proposeDimensions();
            if (dimensions) {
                socket.emit('terminal_resize', {
                    session_id: sessionId,
                    rows: dimensions.rows,
                    cols: dimensions.cols
                });
            }
        });

        socket.on('disconnect', () => {
            console.log('Socket disconnected');
            isConnected = false;
            terminal.write('\r\n\x1b[31m[Disconnected from server. Attempting to reconnect...]\x1b[0m\r\n');
        });

        socket.on('terminal_buffer', (data) => {
            terminal.clear();
            if (data.buffer) {
                terminal.write(data.buffer);
            }
            if (data.read_only || !isActive) { // Also check isActive from data attribute
                terminal.options.disableStdin = true;
                const pasteBtn = document.getElementById('btn-paste');
                if (pasteBtn) pasteBtn.disabled = true;
            } else {
                terminal.focus();
            }
        });

        socket.on('terminal_output', (data) => {
            if (data && typeof data === 'string') {
                terminal.write(data);
            }
        });

        socket.on('terminal_error', (data) => {
            console.error('Terminal error:', data.error);
            terminal.write('\r\n\x1b[31m[Error: ' + data.error + ']\x1b[0m\r\n');
        });

        if (isActive) {
            terminal.onData((data) => {
                if (socket && socket.connected) {
                    socket.emit('terminal_input', {
                        session_id: sessionId,
                        data: data
                    });
                }
            });
        } else {
            terminal.options.disableStdin = true;
        }

        const clearBtn = document.getElementById('btn-clear');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => terminal.clear());
        }

        const fullscreenBtn = document.getElementById('btn-fullscreen');
        if (fullscreenBtn) {
            fullscreenBtn.addEventListener('click', () => {
                if (!document.fullscreenElement) {
                    terminalContainer.requestFullscreen().then(() => {
                        terminalContainer.classList.add('fullscreen-active');
                        setTimeout(() => fitAddon.fit(), 100);
                    }).catch(err => console.error('Error entering fullscreen:', err));
                } else {
                    document.exitFullscreen().then(() => {
                        terminalContainer.classList.remove('fullscreen-active');
                        setTimeout(() => fitAddon.fit(), 100);
                    });
                }
            });
        }

        const copyBtn = document.getElementById('btn-copy');
        if (copyBtn) {
            copyBtn.addEventListener('click', () => {
                const selection = terminal.getSelection();
                if (selection) {
                    navigator.clipboard.writeText(selection).then(() => {
                        window.CoreSecFrame.showNotification('Copied to clipboard', 'success');
                    }).catch(err => {
                        console.error('Failed to copy:', err);
                        window.CoreSecFrame.showNotification('Failed to copy text', 'danger');
                    });
                } else {
                    window.CoreSecFrame.showNotification('No text selected', 'warning');
                }
            });
        }

        const pasteBtn = document.getElementById('btn-paste');
        if (pasteBtn && isActive) {
            pasteBtn.addEventListener('click', () => {
                navigator.clipboard.readText().then(text => {
                    if (socket && socket.connected) {
                        socket.emit('terminal_input', {
                            session_id: sessionId,
                            data: text
                        });
                    }
                }).catch(err => {
                    console.error('Failed to paste:', err);
                    window.CoreSecFrame.showNotification('Failed to paste text', 'danger');
                });
            });
        } else if (pasteBtn) {
            pasteBtn.disabled = true;
        }

        document.addEventListener('keydown', (e) => {
            if (e.key === 'F11' && fullscreenBtn) {
                e.preventDefault();
                fullscreenBtn.click();
            }
            if (e.ctrlKey && e.shiftKey && e.key === 'C' && copyBtn) {
                e.preventDefault();
                copyBtn.click();
            }
            if (e.ctrlKey && e.shiftKey && e.key === 'V' && pasteBtn && isActive) {
                e.preventDefault();
                pasteBtn.click();
            }
            if (e.ctrlKey && e.key === 'l' && document.activeElement === terminalElement && clearBtn) {
                e.preventDefault();
                clearBtn.click();
            }
        });

        document.addEventListener('fullscreenchange', () => {
            if (!document.fullscreenElement) {
                terminalContainer.classList.remove('fullscreen-active');
                setTimeout(() => fitAddon.fit(), 100);
            }
        });

        if (terminalElement) {
            terminalElement.addEventListener('click', () => terminal.focus());
        }

        if (isActive) {
            setTimeout(() => terminal.focus(), 500);
        }
    } // End of isOwner check

    const shortcutsBtn = document.getElementById('btn-shortcuts');
    if (shortcutsBtn) {
        shortcutsBtn.addEventListener('click', toggleShortcutsInternal);
    }
    // Expose toggleShortcutsInternal if it's called by inline HTML like `onclick="toggleShortcuts()"`
    window.toggleShortcuts = toggleShortcutsInternal;


    if (moduleToExecute && isActive && isOwner) {
        setTimeout(function () {
            console.log(`Executing module: ${moduleToExecute.name} in ${moduleToExecute.mode} mode`);
            fetch(urlExecuteModule, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    module_name: moduleToExecute.name,
                    mode: moduleToExecute.mode
                })
            })
            .then(response => response.json())
            .then(data => {
                if (!data.success) { // Assuming json_success/json_error format
                    console.error('Error executing module:', data.message);
                    window.CoreSecFrame.showNotification('Error executing module: ' + data.message, 'danger');
                } else {
                    window.CoreSecFrame.showNotification(data.message || `Module ${moduleToExecute.name} started.`, 'info');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                window.CoreSecFrame.showNotification('Error: ' + error.toString(), 'danger');
            });
        }, 1500);
    }
});

function toggleShortcutsInternal() { // Renamed
    const panel = document.getElementById('shortcuts-panel');
    if (panel) {
        panel.classList.toggle('hidden');
    }
}
