/**
 * LineUp System - WebSocket & Audio/TTS Controller
 */

class SoundSynthesizer {
    constructor() {
        this.audioCtx = null;
        this.muted = false;
        this.isUnlocked = false;
        this.audioElements = {};
        this._setupAudioElements();
    }

    _setupAudioElements() {
        // Create or bind HTML5 audio elements for reliable playback on mobile devices
        if (typeof document !== 'undefined') {
            const files = {
                'dingdong': '/static/audio/dingdong.wav',
                'urgent': '/static/audio/urgent_alert.wav',
                'completion': '/static/audio/completion.wav'
            };
            Object.keys(files).forEach(key => {
                let el = document.getElementById(`sound-${key}`);
                if (!el) {
                    el = document.createElement('audio');
                    el.id = `sound-${key}`;
                    el.src = files[key];
                    el.preload = 'auto';
                    el.style.display = 'none';
                    document.body ? document.body.appendChild(el) : window.addEventListener('DOMContentLoaded', () => document.body.appendChild(el));
                }
                this.audioElements[key] = el;
            });
        }
    }

    initAudio() {
        // Unlock HTML5 Audio Elements on user gesture
        Object.values(this.audioElements).forEach(el => {
            if (el) {
                el.volume = 1.0;
                try {
                    const p = el.play();
                    if (p !== undefined) {
                        p.then(() => {
                            el.pause();
                            el.currentTime = 0;
                        }).catch(() => {});
                    }
                } catch (e) {}
            }
        });

        // Unlock Web Audio API context
        if (!this.audioCtx) {
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            if (AudioContextClass) {
                this.audioCtx = new AudioContextClass();
            }
        }
        if (this.audioCtx && this.audioCtx.state === 'suspended') {
            this.audioCtx.resume().catch(() => {});
        }
        this.isUnlocked = true;
    }

    _playHtmlAudio(name) {
        const el = this.audioElements[name] || document.getElementById(`sound-${name}`);
        if (el) {
            el.volume = 1.0;
            el.currentTime = 0;
            const p = el.play();
            if (p !== undefined) {
                p.catch(err => {
                    console.warn(`[Audio] HTML5 ${name} play blocked, relying on WebAudio:`, err);
                });
            }
            return true;
        }
        return false;
    }

    playDingDong() {
        if (this.muted) return;
        this.initAudio();

        // 1. Play real WAV file
        this._playHtmlAudio('dingdong');

        // 2. Play Web Audio synthesizer as dual-layer guarantee
        if (this.audioCtx && this.audioCtx.state === 'running') {
            try {
                const ctx = this.audioCtx;
                const now = ctx.currentTime;

                const osc1 = ctx.createOscillator();
                const gain1 = ctx.createGain();
                osc1.type = 'sine';
                osc1.frequency.setValueAtTime(659.25, now);
                gain1.gain.setValueAtTime(0.4, now);
                gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.6);
                osc1.connect(gain1);
                gain1.connect(ctx.destination);
                osc1.start(now);
                osc1.stop(now + 0.6);

                const osc2 = ctx.createOscillator();
                const gain2 = ctx.createGain();
                osc2.type = 'sine';
                osc2.frequency.setValueAtTime(523.25, now + 0.35);
                gain2.gain.setValueAtTime(0.45, now + 0.35);
                gain2.gain.exponentialRampToValueAtTime(0.0001, now + 1.2);
                osc2.connect(gain2);
                gain2.connect(ctx.destination);
                osc2.start(now + 0.35);
                osc2.stop(now + 1.2);
            } catch (e) {}
        }
    }

    playUrgentAlert() {
        if (this.muted) return;
        this.initAudio();

        // 1. Play real WAV file
        this._playHtmlAudio('urgent');

        // 2. Web Audio synthesis fallback
        if (this.audioCtx && this.audioCtx.state === 'running') {
            try {
                const ctx = this.audioCtx;
                const now = ctx.currentTime;
                [0, 0.2, 0.4].forEach((delay) => {
                    const osc = ctx.createOscillator();
                    const gain = ctx.createGain();
                    osc.type = 'triangle';
                    osc.frequency.setValueAtTime(880, now + delay);
                    gain.gain.setValueAtTime(0.3, now + delay);
                    gain.gain.exponentialRampToValueAtTime(0.01, now + delay + 0.15);
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    osc.start(now + delay);
                    osc.stop(now + delay + 0.15);
                });
            } catch (e) {}
        }

        // Trigger hardware vibration if available
        if (navigator.vibrate) {
            try {
                navigator.vibrate([200, 100, 200, 100, 400]);
            } catch (e) {}
        }
    }

    playCompletionChime() {
        if (this.muted) return;
        this.initAudio();

        // 1. Play real WAV file
        this._playHtmlAudio('completion');

        // 2. Web Audio synthesis fallback
        if (this.audioCtx && this.audioCtx.state === 'running') {
            try {
                const ctx = this.audioCtx;
                const now = ctx.currentTime;
                const notes = [523.25, 659.25, 783.99, 1046.50];
                notes.forEach((freq, idx) => {
                    const osc = ctx.createOscillator();
                    const gain = ctx.createGain();
                    osc.type = 'sine';
                    osc.frequency.setValueAtTime(freq, now + idx * 0.12);
                    gain.gain.setValueAtTime(0.25, now + idx * 0.12);
                    gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.12 + 0.5);
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    osc.start(now + idx * 0.12);
                    osc.stop(now + idx * 0.12 + 0.5);
                });
            } catch (e) {}
        }

        if (navigator.vibrate) {
            try {
                navigator.vibrate([150, 100, 250]);
            } catch (e) {}
        }
    }

    announceTicket(ticketNumber, counterNumber) {
        if (this.muted) return;
        
        // 1. Play Ding-Dong chime first
        this.playDingDong();

        // 2. Play Voice announcement after 900ms
        setTimeout(() => {
            if (!('speechSynthesis' in window)) return;

            window.speechSynthesis.cancel(); // clear previous speech

            // Format ticket spelling (e.g., "A 0 1 2" instead of "A minus twelve")
            const parts = ticketNumber.split('-');
            const prefix = parts[0] || '';
            const digits = (parts[1] || '').split('').join(' ');

            const textEnglish = `Ticket ${prefix} ${digits}, please proceed to counter ${counterNumber}`;

            const utterance = new SpeechSynthesisUtterance(textEnglish);
            utterance.rate = 0.95;
            utterance.pitch = 1.0;
            utterance.volume = 1.0;

            const voices = window.speechSynthesis.getVoices();
            // Check for Khmer or preferred English voice
            const khmerVoice = voices.find(v => v.lang.startsWith('km') || v.lang.startsWith('kh'));
            const enVoice = voices.find(v => v.lang.startsWith('en') && (v.name.includes('Natural') || v.name.includes('Google') || v.name.includes('Zira') || v.name.includes('Samantha')));

            if (khmerVoice) {
                // If Khmer voice is installed on client OS
                const khmerText = `សូមអញ្ជើញ លេខ ${ticketNumber} ទៅកាន់ បញ្ជរលេខ ${counterNumber}`;
                const khUtterance = new SpeechSynthesisUtterance(khmerText);
                khUtterance.voice = khmerVoice;
                khUtterance.rate = 0.9;
                window.speechSynthesis.speak(khUtterance);
            } else {
                if (enVoice) {
                    utterance.voice = enVoice;
                }
                window.speechSynthesis.speak(utterance);
            }
        }, 900);
    }
}

class QueueSocket {
    constructor() {
        this.listeners = [];
        this.socket = null;
        this.reconnectTimer = null;
        this.sound = new SoundSynthesizer();
        this.connect();
    }

    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        this.socket = new WebSocket(wsUrl);

        this.socket.onopen = () => {
            console.log('[QueueWS] Connected to LineUp WebSocket');
            const statusEl = document.getElementById('ws-status-indicator');
            if (statusEl) {
                statusEl.className = 'w-3 h-3 rounded-full bg-emerald-500 animate-pulse';
                statusEl.title = 'Real-time Connected';
            }
        };

        this.socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.dispatchEvent(data);
            } catch (err) {
                // simple string message
            }
        };

        this.socket.onclose = () => {
            console.warn('[QueueWS] Disconnected. Reconnecting in 3s...');
            const statusEl = document.getElementById('ws-status-indicator');
            if (statusEl) {
                statusEl.className = 'w-3 h-3 rounded-full bg-rose-500';
                statusEl.title = 'Connecting...';
            }
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = setTimeout(() => this.connect(), 3000);
        };

        this.socket.onerror = (err) => {
            console.error('[QueueWS] Socket error', err);
            this.socket.close();
        };
    }

    on(eventType, callback) {
        this.listeners.push({ type: eventType, callback });
    }

    dispatchEvent(data) {
        this.listeners.forEach(l => {
            if (l.type === '*' || l.type === data.event) {
                l.callback(data);
            }
        });
    }

    send(data) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(typeof data === 'string' ? data : JSON.stringify(data));
        }
    }
}

// Global instance
window.queueSocket = new QueueSocket();
window.queueSound = window.queueSocket.sound;
