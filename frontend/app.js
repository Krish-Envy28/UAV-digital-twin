document.addEventListener("DOMContentLoaded", () => {

    // ==========================================
    // 1. Load SVG Schematic
    // ==========================================
    const svgContainer = document.getElementById("engine-svg-container");

    fetch('assets/engine.svg')
        .then(response => {
            if (!response.ok) throw new Error("SVG not found");
            return response.text();
        })
        .then(svgText => {
            svgContainer.innerHTML = svgText;
            console.log("SVG Loaded successfully");
            anime({
                targets: '#engine-svg-container svg path',
                strokeDashoffset: [anime.setDashoffset, 0],
                easing: 'easeInOutSine',
                duration: 2000,
                delay: function (el, i) { return i * 10 },
                direction: 'alternate',
                loop: false
            });
        })
        .catch(err => {
            console.warn("SVG not found.", err);
            svgContainer.innerHTML = '<div style="color: rgba(255,255,255,0.2); font-family: monospace; border: 1px dashed rgba(255,255,255,0.2); padding: 2rem; border-radius: 8px;">Awaiting engine.svg...</div>';
        });

    // ==========================================
    // 2. Tab Navigation
    // ==========================================
    const navPill = document.getElementById("nav-pill");
    const tabs = navPill.querySelectorAll("span");
    const tabPanels = document.querySelectorAll(".tab-panel");

    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            const target = tab.dataset.tab;

            // Update active pill
            tabs.forEach(t => t.classList.remove("active"));
            tab.classList.add("active");

            // Show the right panel
            tabPanels.forEach(panel => {
                panel.classList.remove("active");
            });
            const activePanel = document.getElementById("tab-" + target);
            activePanel.classList.add("active");

            // Anime.js: Staggered entrance for cards in the new tab
            runEntranceAnimation(activePanel);
            
            // Tab-specific voice greetings
            if (target === "mission") {
                voiceAssistant.speak("Mission planning active. Select a simulated mission profile.");
            } else if (target === "what-if") {
                voiceAssistant.speak("Analyzing what-if scenarios based on current mission parameters.");
            } else if (target === "recommendation") {
                const rectStatus = document.getElementById('rect-status').textContent;
                if (rectStatus === "CRITICAL ACTION REQUIRED") {
                    const step1 = document.getElementById('rect-step1').textContent;
                    const step2 = document.getElementById('rect-step2').textContent;
                    voiceAssistant.speak(`Critical Action Required. Step 1: ${step1}. Step 2: ${step2}.`);
                } else {
                    voiceAssistant.speak("Displaying AI generated rectification steps. System nominal.");
                }
            }
        });
    });

    // Run entrance animation on initial load
    setTimeout(() => {
        runEntranceAnimation(document.getElementById("tab-overview"));
    }, 100);

    function runEntranceAnimation(panel) {
        const cards = panel.querySelectorAll('.stat-card, .hero-card, .chart-card, .logs-container');
        cards.forEach(c => c.classList.remove('animated'));
        anime({
            targets: cards,
            opacity: [0, 1],
            translateY: [20, 0],
            delay: anime.stagger(80),
            duration: 600,
            easing: 'easeOutQuart',
            complete: () => cards.forEach(c => c.classList.add('animated'))
        });
    }

    // ==========================================
    // 3. Voice Alert System (Text-to-Speech)
    // ==========================================
    class VoiceAssistant {
        constructor() {
            this.enabled = true; // Enabled by default
            this.synth = window.speechSynthesis;
            this.voice = null;
            this.lastStage = null;
            this.firstAnomalyAnnounced = false;
            this._loadVoice();
        }

        _loadVoice() {
            // Try to pick a female English voice
            const loadVoices = () => {
                const voices = this.synth.getVoices();
                // Prefer female English voices
                const preferred = voices.find(v =>
                    v.lang.startsWith("en") &&
                    (v.name.toLowerCase().includes("female") ||
                     v.name.toLowerCase().includes("zira") ||       // Windows
                     v.name.toLowerCase().includes("samantha") ||   // macOS
                     v.name.toLowerCase().includes("google uk english female") ||
                     v.name.toLowerCase().includes("hazel"))
                );
                this.voice = preferred || voices.find(v => v.lang.startsWith("en")) || voices[0];
                if (this.voice) {
                    console.log("Voice selected:", this.voice.name);
                }
            };

            // Voices load asynchronously in some browsers
            if (this.synth.getVoices().length > 0) {
                loadVoices();
            } else {
                this.synth.onvoiceschanged = loadVoices;
            }
        }

        toggle() {
            this.enabled = !this.enabled;
            if (this.enabled) {
                this.speak("Voice alerts activated. Standing by for telemetry.");
            }
            return this.enabled;
        }

        speak(text) {
            if (!this.enabled || !this.synth) return;
            // Cancel any current speech to avoid overlapping
            this.synth.cancel();
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.rate = 0.95;
            utterance.pitch = 1.1;
            utterance.volume = 1.0;
            if (this.voice) utterance.voice = this.voice;
            this.synth.speak(utterance);
        }

        onTelemetry(phm) {
            if (!this.enabled) return;

            const stage = phm.degradation_stage;
            const isAnomaly = phm.anomaly;

            // Announce first anomaly
            if (isAnomaly && !this.firstAnomalyAnnounced) {
                this.firstAnomalyAnnounced = true;
                const score = phm.anomaly_score.toFixed(2);
                this.speak(`Anomaly detected. Anomaly score is ${score}. Monitoring closely.`);
                return; // Don't double-trigger with stage change
            }

            // Announce degradation stage changes (Phase 4 Vocabulary)
            if (stage !== this.lastStage && this.lastStage !== null) {
                switch (stage) {
                    case "healthy":
                        this.speak("Engine status nominal. Mission risk is low. All systems healthy.");
                        break;
                    case "early_deviation":
                        this.speak("Caution. Early deviation detected in sensor telemetry. Continuing mission as planned.");
                        break;
                    case "incipient_fault":
                        this.speak("Warning. Incipient fault detected. Mission risk elevated to moderate.");
                        break;
                    case "progressive_degradation":
                        this.speak("Alert. Progressive degradation confirmed. Recommend reducing load to 70% to extend remaining useful life and safely complete the mission.");
                        break;
                    case "critical":
                        const rul = phm.rul_hours.toFixed(0);
                        this.speak(`Critical alert. Severe degradation. Mission-conditioned RUL is ${rul} hours. Abort mission and land immediately.`);
                        break;
                }
            }

            this.lastStage = stage;
        }

        onConnect() {
            this.speak("Aero Telemetry online. All engine parameters nominal. Voice monitoring active. Standing by for anomaly detection.");
        }

        onDisconnect() {
            this.speak("Warning. Telemetry link lost.");
        }
    }

    const voiceAssistant = new VoiceAssistant();

    // Voice Toggle
    const voiceToggleBtn = document.getElementById("voice-toggle");
    voiceToggleBtn.addEventListener("click", () => {
        const isEnabled = voiceAssistant.toggle();
        if (isEnabled) {
            voiceToggleBtn.classList.add("active");
            addLog("[SYSTEM] Voice alerts enabled.", "info");
        } else {
            voiceToggleBtn.classList.remove("active");
            addLog("[SYSTEM] Voice alerts disabled.", "info");
        }
    });

    // Speed Toggle
    const speedToggleBtn = document.getElementById("speed-toggle");
    const speedIndicator = document.getElementById("speed-indicator");
    let currentSpeed = 10;
    
    speedToggleBtn.addEventListener("click", async () => {
        currentSpeed = currentSpeed === 1 ? 10 : 1;
        speedIndicator.innerText = `${currentSpeed}x`;
        if (currentSpeed === 10) {
            speedToggleBtn.classList.add("active");
        } else {
            speedToggleBtn.classList.remove("active");
        }
        try {
            await fetch('http://localhost:8000/api/speed', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({speed: currentSpeed})
            });
            addLog(`[SYSTEM] Simulation speed set to ${currentSpeed}x`, "info");
        } catch (e) {
            console.error("Failed to update speed", e);
            addLog(`[SYSTEM] Failed to change speed. Is server running?`, "critical");
        }
    });

    // ==========================================
    // 4. Logs Engine
    // ==========================================
    const logsBody = document.getElementById("logs-body");
    const MAX_LOG_LINES = 500;

    function addLog(message, level = "info") {
        const line = document.createElement("div");
        line.className = `log-line ${level}`;

        const now = new Date();
        const ts = now.toTimeString().split(' ')[0]; // HH:MM:SS
        line.textContent = `[${ts}] ${message}`;

        logsBody.appendChild(line);

        // Auto-scroll to bottom
        logsBody.scrollTop = logsBody.scrollHeight;

        // Limit log lines
        while (logsBody.children.length > MAX_LOG_LINES) {
            logsBody.removeChild(logsBody.firstChild);
        }
    }

    // Clear logs button
    document.getElementById("clear-logs").addEventListener("click", () => {
        logsBody.innerHTML = '';
        addLog("[SYSTEM] Log cleared.", "info");
    });

    // ==========================================
    // 5. Chart.js — Analysis Charts
    // ==========================================
    const chartDefaults = {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 400 },
        scales: {
            x: {
                ticks: { color: 'rgba(255,255,255,0.3)', font: { family: 'JetBrains Mono', size: 10 } },
                grid: { color: 'rgba(255,255,255,0.03)' }
            },
            y: {
                ticks: { color: 'rgba(255,255,255,0.3)', font: { family: 'JetBrains Mono', size: 10 } },
                grid: { color: 'rgba(255,255,255,0.05)' }
            }
        },
        plugins: {
            legend: {
                labels: { color: 'rgba(255,255,255,0.5)', font: { family: 'Inter', size: 11 } }
            }
        }
    };

    const MAX_CHART_POINTS = 100;
    const chartLabels = [];

    // Health Index Chart
    const healthChart = new Chart(document.getElementById("chart-health"), {
        type: 'line',
        data: {
            labels: chartLabels,
            datasets: [{
                label: 'Health Index (%)',
                data: [],
                borderColor: '#FF6B35',
                backgroundColor: 'rgba(255,107,53,0.1)',
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                borderWidth: 2
            }]
        },
        options: {
            ...chartDefaults,
            scales: {
                ...chartDefaults.scales,
                y: { ...chartDefaults.scales.y, min: 0, max: 100 }
            }
        }
    });

    // Anomaly Score Chart
    const anomalyChart = new Chart(document.getElementById("chart-anomaly"), {
        type: 'line',
        data: {
            labels: chartLabels,
            datasets: [{
                label: 'Anomaly Score',
                data: [],
                borderColor: '#e74c3c',
                backgroundColor: 'rgba(231,76,60,0.1)',
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                borderWidth: 2
            }]
        },
        options: {
            ...chartDefaults,
            scales: {
                ...chartDefaults.scales,
                y: { ...chartDefaults.scales.y, min: 0 }
            }
        }
    });

    // Sensor Readings Chart (multi-line)
    const sensorsChart = new Chart(document.getElementById("chart-sensors"), {
        type: 'line',
        data: {
            labels: chartLabels,
            datasets: [
                {
                    label: 'EGT (°C)',
                    data: [],
                    borderColor: '#FF6B35',
                    tension: 0.4, pointRadius: 0, borderWidth: 1.5
                },
                {
                    label: 'CHT (°C)',
                    data: [],
                    borderColor: '#3B82F6',
                    tension: 0.4, pointRadius: 0, borderWidth: 1.5
                },
                {
                    label: 'Vibration (G x100)',
                    data: [],
                    borderColor: '#2ecc71',
                    tension: 0.4, pointRadius: 0, borderWidth: 1.5
                }
            ]
        },
        options: chartDefaults
    });

    // Radar Chart (Phase 4 Innovation)
    const radarCtx = document.getElementById('radarChart');
    if (radarCtx) {
        window.radarChart = new Chart(radarCtx, {
            type: 'radar',
            data: {
                labels: ['Health', 'RUL', 'Confidence', 'Stability', 'Mission Fit'],
                datasets: [{
                    label: 'System Vitals',
                    data: [100, 100, 100, 100, 100],
                    backgroundColor: 'rgba(230, 126, 34, 0.2)',
                    borderColor: '#E67E22',
                    pointBackgroundColor: '#E67E22',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    r: {
                        angleLines: { color: 'rgba(255, 255, 255, 0.1)' },
                        grid: { color: 'rgba(255, 255, 255, 0.1)' },
                        pointLabels: {
                            color: 'rgba(255, 255, 255, 0.7)',
                            font: { family: 'JetBrains Mono', size: 9 }
                        },
                        ticks: { display: false, min: 0, max: 100 }
                    }
                },
                plugins: { legend: { display: false } }
            }
        });
    }

    function updateCharts(data) {
        const label = data.engine_hours.toFixed(1) + "h";

        // Add label (shared across charts)
        chartLabels.push(label);
        if (chartLabels.length > MAX_CHART_POINTS) chartLabels.shift();

        // Health
        healthChart.data.datasets[0].data.push(data.phm.health_index);
        if (healthChart.data.datasets[0].data.length > MAX_CHART_POINTS)
            healthChart.data.datasets[0].data.shift();
        healthChart.update('none');

        // Anomaly
        anomalyChart.data.datasets[0].data.push(data.phm.anomaly_score);
        if (anomalyChart.data.datasets[0].data.length > MAX_CHART_POINTS)
            anomalyChart.data.datasets[0].data.shift();
        anomalyChart.update('none');

        // Sensors
        sensorsChart.data.datasets[0].data.push(data.raw.egt);
        sensorsChart.data.datasets[1].data.push(data.raw.cht);
        sensorsChart.data.datasets[2].data.push(data.raw.vibration * 100); // scale up for visibility
        for (const ds of sensorsChart.data.datasets) {
            if (ds.data.length > MAX_CHART_POINTS) ds.data.shift();
        }
        sensorsChart.update('none');
    }

    // ==========================================
    // 6. WebSocket Connection
    // ==========================================
    const ws = new WebSocket("ws://localhost:8000/ws");

    ws.onopen = () => {
        console.log("Connected to UAV Telemetry Stream");
        document.getElementById("status-dot").style.backgroundColor = "var(--status-healthy)";
        document.getElementById("status-dot").style.boxShadow = "0 0 10px var(--status-healthy)";
        document.getElementById("stage-text").innerText = "DATALINK ACTIVE";
        addLog("[SYSTEM] Telemetry link established. Receiving data.", "info");
        voiceAssistant.onConnect();
    };

    ws.onclose = () => {
        console.log("Disconnected from stream");
        document.getElementById("status-dot").style.backgroundColor = "rgba(255,255,255,0.2)";
        document.getElementById("status-dot").style.boxShadow = "none";
        document.getElementById("stage-text").innerText = "DATALINK OFFLINE";
        addLog("[SYSTEM] Telemetry link lost.", "critical");
        voiceAssistant.onDisconnect();
    };

    // ==========================================
    // 7. Handle Incoming Telemetry
    // ==========================================
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        window.currentData = data; // Make available globally for What-If logic
        updateDashboard(data);
        updateHealthColor(data.phm.health_index);
        updateCharts(data);
        updateLogs(data);
        voiceAssistant.onTelemetry(data.phm);
        
        if (window.triggerWhatIfUpdate) {
            window.triggerWhatIfUpdate();
        }
    };

    const activeAnimations = {};

    function updateDashboard(data) {
        const phm = data.phm;
        
        // --- Update Key Health Stats (Left Col) ---
        const rulH = phm.rul_hours;
        const d = Math.floor(rulH / 24);
        const h = Math.floor(rulH % 24);
        const m = Math.floor((rulH * 60) % 60);
        const formattedRul = `${d}d ${h.toString().padStart(2, '0')}h ${m.toString().padStart(2, '0')}m`;
        
        document.getElementById("val-health").innerText = formattedRul;
        
        const stageStr = phm.degradation_stage.replace(/_/g, " ").toUpperCase();
        document.getElementById("val-stage").innerText = stageStr;
        
        document.getElementById("val-rul").innerText = formattedRul;
        
        const confPct = (phm.stage_confidence * 100).toFixed(1);
        document.getElementById("val-confidence").innerText = confPct;

        // --- Update Mission Overview (Right Col) ---
        // For demo, altitude is simulated (e.g. rising to 4000m)
        const alt = Math.min(4000, data.engine_hours * 1000).toFixed(0); 
        document.getElementById("val-altitude").innerText = alt + " m";
        
        // Throttle maps roughly to RPM
        const throttle = ((data.raw.rpm / 5000) * 100).toFixed(0);
        document.getElementById("val-throttle").innerText = throttle + " %";
        
        // Mission Risk & Recommendation Logic
        let risk = "LOW";
        let riskColor = "var(--status-healthy)";
        let ctaText = "🟢 CONTINUE MISSION";
        let ctaReason = "System nominal. Current load and altitude profiles are well within engine operating limits.";
        let glowClass = "glow-healthy";
        
        if (phm.degradation_stage === "critical") {
            risk = "HIGH";
            riskColor = "var(--status-critical)";
            ctaText = "🔴 ABORT / LAND IMMEDIATELY";
            ctaReason = "Critical degradation detected. Remaining useful life cannot support mission completion. Immediate landing required.";
            glowClass = "glow-critical";
        } else if (phm.degradation_stage !== "healthy" && phm.degradation_stage !== "early_deviation") {
            risk = "MODERATE";
            riskColor = "var(--status-warning)";
            ctaText = "🟡 REDUCE LOAD TO 70%";
            ctaReason = "Progressing degradation detected. Reducing throttle and load will extend RUL to safely complete the mission.";
            glowClass = "glow-warning";
        }

        const riskEl = document.getElementById("val-risk");
        riskEl.innerText = risk;
        riskEl.style.color = riskColor;
        
        const ctaBadge = document.getElementById("cta-badge");
        ctaBadge.innerText = ctaText;
        ctaBadge.classList.remove("warning", "critical");
        if (risk === "HIGH") ctaBadge.classList.add("critical");
        else if (risk === "MODERATE") ctaBadge.classList.add("warning");

        document.getElementById("cta-reasoning").innerText = ctaReason;

        // --- Engine Glow ---
        const engineContainer = document.getElementById("engine-svg-container");
        engineContainer.className = "engine-container " + glowClass;

        // --- What-If Scenario ---
        // (Handled separately by updateWhatIfAndRecommendation)

        // --- Update Raw Sensors Grid ---
        if (data.raw) {
            document.getElementById('val-raw-rpm').innerText = data.raw.rpm ? data.raw.rpm.toFixed(0) : '--';
            document.getElementById('val-raw-thr').innerText = data.raw.throttle ? data.raw.throttle.toFixed(0) : '--';
            document.getElementById('val-raw-map').innerText = data.raw.map ? data.raw.map.toFixed(1) : '--';
            document.getElementById('val-raw-alt').innerText = data.raw.altitude ? data.raw.altitude.toFixed(0) : '--';
            document.getElementById('val-raw-amb').innerText = data.raw.ambient_temp ? data.raw.ambient_temp.toFixed(1) : '--';
            document.getElementById('val-raw-egt').innerText = data.raw.egt ? data.raw.egt.toFixed(1) : '--';
            document.getElementById('val-raw-cht').innerText = data.raw.cht ? data.raw.cht.toFixed(1) : '--';
            document.getElementById('val-raw-oilp').innerText = data.raw.oil_pressure ? data.raw.oil_pressure.toFixed(1) : '--';
            document.getElementById('val-raw-oilt').innerText = data.raw.oil_temp ? data.raw.oil_temp.toFixed(1) : '--';
            document.getElementById('val-raw-vib').innerText = data.raw.vibration ? data.raw.vibration.toFixed(2) : '--';
            document.getElementById('val-raw-fuel').innerText = data.raw.fuel_flow ? data.raw.fuel_flow.toFixed(1) : '--';
        }

        // --- Radar Chart ---
        if (window.radarChart) {
            const safetyMargin = Math.max(0, 100 - phm.anomaly_score * 10);
            window.radarChart.data.datasets[0].data = [
                phm.health_index, 
                Math.min(100, (phm.rul_hours / 50) * 100), 
                phm.stage_confidence * 100,
                safetyMargin,
                (risk === "LOW" ? 95 : (risk === "MODERATE" ? 60 : 20))
            ];
            window.radarChart.update('none');
        }

        // Update Top Status Bar
        const stageText = document.getElementById("stage-text");
        stageText.innerText = stageStr;

        const statusDot = document.getElementById("status-dot");
        statusDot.style.backgroundColor = riskColor;
        statusDot.style.boxShadow = `0 0 10px ${riskColor}`;

        // --- Trigger SVG Micro-Animations ---
        triggerSVGAnimations(data.residual_z);
    }

    function updateLogs(data) {
        const phm = data.phm;
        const hours = data.engine_hours.toFixed(1);

        // Always log a concise data line
        addLog(
            `[${hours}h] HI:${phm.health_index.toFixed(1)}% | RUL:${phm.rul_hours.toFixed(1)}h | AS:${phm.anomaly_score.toFixed(3)} | Stage:${phm.degradation_stage}`,
            "data"
        );

        // Log significant events
        if (phm.anomaly) {
            addLog(
                `[ANOMALY] Score ${phm.anomaly_score.toFixed(3)} exceeds threshold at ${hours}h`,
                "critical"
            );
        }

        if (phm.degradation_stage === "critical") {
            if (!window.hasSpokenEngineCritical) {
                addLog(`[SYSTEM ALERT] Engine has reached CRITICAL degradation stage!`, "critical");
                if (voiceAssistant) {
                    voiceAssistant.speak("System Alert. Engine has reached critical degradation stage. Imminent failure detected.");
                }
                window.hasSpokenEngineCritical = true;
            }
        }

        // Check residuals for specific sensor warnings
        const threshold = 3.0;
        for (const [sensor, z] of Object.entries(data.residual_z)) {
            if (Math.abs(z) > threshold) {
                addLog(
                    `[SENSOR] ${sensor.toUpperCase()} residual Z-score: ${z.toFixed(2)} (|z| > ${threshold})`,
                    "warning"
                );
            }
        }
    }

    // ==========================================
    // 8. Helper Functions & Animations
    // ==========================================

    function animateNumberChange(elementId, endValue, decimals) {
        const el = document.getElementById(elementId);
        const startValue = parseFloat(el.innerText) || 0;

        const obj = { val: startValue };

        anime({
            targets: obj,
            val: endValue,
            round: Math.pow(10, decimals),
            easing: 'easeOutExpo',
            duration: 800,
            update: function () {
                el.innerHTML = (obj.val / Math.pow(10, decimals)).toFixed(decimals);
            }
        });
    }

    function updateProgressBar(elementId, current, max) {
        const pct = Math.min((current / max) * 100, 100);
        document.getElementById(elementId).style.width = pct + "%";
    }

    function triggerSVGAnimations(residual_z) {
        const threshold = 3.0;

        const sensors = {
            'egt': '#egt-sensor',
            'cht': '#cht-sensor',
            'vibration': '#vibration-sensor',
            'oil_pressure': '#oil-sensor',
            'fuel_flow': '#fuel-sensor'
        };

        for (const [key, id] of Object.entries(sensors)) {
            const z = Math.abs(residual_z[key] || 0);

            if (!document.querySelector(id)) continue;

            if (z > threshold) {
                if (!activeAnimations[key]) {
                    anime({
                        targets: `${id} path, ${id} rect, ${id} circle`,
                        stroke: '#ff0000',
                        strokeWidth: 3,
                        filter: 'drop-shadow(0 0 12px rgba(255,0,0,1))',
                        duration: 500,
                        easing: 'easeInOutSine'
                    });

                    if (key === 'vibration') {
                        activeAnimations['vibration_shake'] = anime({
                            targets: id,
                            translateX: [
                                { value: -3, duration: 50 },
                                { value: 3, duration: 50 },
                                { value: 0, duration: 50 }
                            ],
                            loop: true,
                            easing: 'easeInOutSine'
                        });
                    }

                    activeAnimations[key] = true;
                    
                    // Add click handler
                    const el = document.querySelector(id);
                    if (el) {
                        el.style.cursor = 'pointer';
                        el.onclick = async () => {
                            const res = await fetch("/api/events");
                            const data = await res.json();
                            if (data.events && data.events.length > 0) {
                                openEventModal(data.events[0].event_id);
                            }
                        };
                    }
                }
            } else {
                if (activeAnimations[key]) {
                    anime({
                        targets: `${id} path, ${id} rect, ${id} circle`,
                        stroke: 'rgba(255,255,255,0.3)',
                        strokeWidth: 1,
                        filter: 'drop-shadow(0 0 0px rgba(0,0,0,0))',
                        duration: 1000,
                        easing: 'easeOutQuad'
                    });

                    if (key === 'vibration' && activeAnimations['vibration_shake']) {
                        activeAnimations['vibration_shake'].pause();
                        anime({ targets: id, translateX: 0, duration: 300 });
                        activeAnimations['vibration_shake'] = null;
                    }

                    activeAnimations[key] = false;
                    
                    // Remove click handler
                    document.querySelector(id).style.cursor = 'default';
                    document.querySelector(id).onclick = null;
                }
            }
        }
    }


    // ==========================================
    // 9. EVENT HISTORY & MODAL (Phase 5)
    // ==========================================
    
    async function fetchEvents() {
        try {
            const res = await fetch("/api/events");
            const data = await res.json();
            renderEventList(data.events || []);
        } catch(e) {
            console.error("Failed to fetch events", e);
        }
    }
    
    function renderEventList(events) {
        const list = document.getElementById("event-history-list");
        list.innerHTML = "";
        
        if (events.length === 0) {
            list.innerHTML = "<div style='color: rgba(255,255,255,0.5);'>No historical events found.</div>";
            return;
        }
        
        events.forEach(evt => {
            const el = document.createElement("div");
            el.className = "glass-panel";
            el.style.padding = "15px";
            el.style.cursor = "pointer";
            el.style.borderLeft = "4px solid var(--status-critical)";
            
            el.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <div style="color: var(--status-critical); font-weight: bold; font-size: 16px;">${evt.event_id}</div>
                        <div style="color: rgba(255,255,255,0.7); font-size: 13px; margin-top: 5px;">Affected: ${evt.affected_component.component || 'Unknown'}</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="color: var(--status-warning); font-size: 12px;">Stage: ${evt.health.degradation_stage.toUpperCase()}</div>
                        <div style="color: rgba(255,255,255,0.4); font-size: 12px; margin-top: 5px;">${new Date(evt.recorded_at).toLocaleString()}</div>
                    </div>
                </div>
            `;
            
            el.onclick = () => openEventModal(evt.event_id);
            list.appendChild(el);
        });
    }
    
    async function openEventModal(eventId) {
        try {
            const res = await fetch(`/api/events/${eventId}`);
            if (!res.ok) throw new Error("Event not found");
            const evt = await res.json();
            
            document.getElementById("modal-event-id").innerText = evt.event_id;
            document.getElementById("modal-event-time").innerText = "Time: " + new Date(evt.recorded_at).toLocaleString();
            document.getElementById("modal-event-component").innerText = evt.affected_component.component || 'Multiple Components';
            document.getElementById("modal-event-stage").innerText = evt.health.degradation_stage.toUpperCase();
            
            document.getElementById("modal-event-status").innerText = evt.event_status.toUpperCase();
            document.getElementById("modal-event-score").innerText = evt.anomaly.score.toFixed(3);
            document.getElementById("modal-event-z").innerText = evt.anomaly.z_score.toFixed(2);
            document.getElementById("modal-event-hi").innerText = evt.health.health_index.toFixed(1);
            document.getElementById("modal-event-rul").innerText = evt.health.rul.toFixed(1);
            
            // Populate sensors
            const sensorsDiv = document.getElementById("modal-event-sensors");
            sensorsDiv.innerHTML = "";
            for (const [key, val] of Object.entries(evt.sensor_data)) {
                sensorsDiv.innerHTML += `<div><span style="color: rgba(255,255,255,0.5);">${key.toUpperCase()}:</span> ${typeof val === 'number' ? val.toFixed(2) : val}</div>`;
            }
            
            // Image
            document.getElementById("modal-event-image").src = `/api/events/${eventId}/image?t=${Date.now()}`;
            
            // JSON
            window.currentEventJson = evt;
            document.getElementById("modal-json-content").textContent = JSON.stringify(evt, null, 2);
            document.getElementById("modal-json-view").style.display = "none";
            
            document.getElementById("event-modal").style.display = "flex";
        } catch(e) {
            console.error("Failed to load event details", e);
        }
    }
    
    document.getElementById("refresh-events")?.addEventListener("click", fetchEvents);
    
    document.getElementById("close-event-modal")?.addEventListener("click", () => {
        document.getElementById("event-modal").style.display = "none";
    });
    
    document.getElementById("btn-view-json")?.addEventListener("click", () => {
        const view = document.getElementById("modal-json-view");
        view.style.display = view.style.display === "none" ? "block" : "none";
    });
    
    // Fetch initial events
    setTimeout(fetchEvents, 1000);

    // ==========================================
    // 10. Health Value Color Shifting
    // ==========================================
    function updateHealthColor(healthIndex) {
        const heroValueEl = document.querySelector('#card-health-idx .hero-value');
        if(heroValueEl) heroValueEl.classList.remove('health-good', 'health-warn', 'health-critical');

        const engineSvg = document.querySelector('.engine-container svg');
        let filterColor = '';

        if (healthIndex >= 80) {
            if(heroValueEl) heroValueEl.classList.add('health-good');
            filterColor = 'rgba(76, 175, 80, 0.4)'; // Green glow
        } else if (healthIndex >= 50) {
            if(heroValueEl) heroValueEl.classList.add('health-warn');
            filterColor = 'rgba(255, 152, 0, 0.5)'; // Orange glow
        } else {
            if(heroValueEl) heroValueEl.classList.add('health-critical');
            filterColor = 'rgba(244, 67, 54, 0.6)'; // Red glow
        }

        if (engineSvg) {
            engineSvg.style.filter = `drop-shadow(0 0 25px ${filterColor})`;
            engineSvg.style.transition = 'filter 0.5s ease';
        }
    }

    // Hook it into updateDashboard
    const originalUpdateDashboard = updateDashboard;
    // We'll just call updateHealthColor after updateDashboard via onmessage

    // ==========================================
    // 10. CSV Drag-and-Drop Upload System
    // ==========================================
    const overlay = document.getElementById('upload-overlay');
    const uploadBtn = document.getElementById('upload-btn');
    const closeBtn = document.getElementById('upload-close');
    const dropzone = document.getElementById('upload-dropzone');
    const fileInput = document.getElementById('csv-file-input');
    const controlsDiv = document.getElementById('upload-controls');
    const progressDiv = document.getElementById('upload-progress');
    const startBtn = document.getElementById('upload-start');

    let csvRows = [];
    let isStreaming = false;

    // Open/Close overlay
    uploadBtn.addEventListener('click', () => {
        overlay.classList.add('visible');
        anime({
            targets: '.upload-modal',
            scale: [0.9, 1],
            opacity: [0, 1],
            duration: 300,
            easing: 'easeOutQuart'
        });
    });

    closeBtn.addEventListener('click', () => {
        overlay.classList.remove('visible');
    });

    // Drag events
    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file && file.name.endsWith('.csv')) {
            handleCSVFile(file);
        }
    });

    // Click to browse
    dropzone.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files[0]) {
            handleCSVFile(e.target.files[0]);
        }
    });

    function handleCSVFile(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            const text = e.target.result;
            csvRows = parseCSV(text);

            document.getElementById('upload-filename').textContent = file.name;
            document.getElementById('upload-rows').textContent = csvRows.length + ' rows';
            controlsDiv.style.display = 'flex';

            addLog(`[UPLOAD] Loaded ${file.name} (${csvRows.length} rows)`, 'info');
        };
        reader.readAsText(file);
    }

    function parseCSV(text) {
        const lines = text.trim().split('\n');
        if (lines.length < 2) return [];

        const headers = lines[0].split(',').map(h => h.trim().toLowerCase());
        const rows = [];

        for (let i = 1; i < lines.length; i++) {
            const vals = lines[i].split(',');
            if (vals.length !== headers.length) continue;

            const obj = {};
            headers.forEach((h, idx) => {
                obj[h] = parseFloat(vals[idx].trim());
            });

            // Ensure required fields exist, fill defaults for missing optional ones
            if (isNaN(obj.engine_hours)) obj.engine_hours = i;
            if (isNaN(obj.timestamp)) obj.timestamp = i;

            rows.push(obj);
        }
        return rows;
    }

    // Start streaming
    startBtn.addEventListener('click', async () => {
        if (isStreaming || csvRows.length === 0) return;
        isStreaming = true;

        const speed = parseInt(document.getElementById('stream-speed').value);
        const total = csvRows.length;

        startBtn.textContent = 'STREAMING...';
        startBtn.style.opacity = '0.5';
        controlsDiv.querySelector('.speed-control select').disabled = true;

        progressDiv.style.display = 'flex';
        const progBar = document.getElementById('upload-prog-bar');
        const progText = document.getElementById('upload-prog-text');

        addLog(`[UPLOAD] Starting stream of ${total} readings at ${speed === 0 ? 'instant' : speed + 'ms'} intervals`, 'info');

        for (let i = 0; i < total; i++) {
            try {
                const response = await fetch('/api/telemetry', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(csvRows[i])
                });

                const pct = ((i + 1) / total * 100).toFixed(1);
                progBar.style.width = pct + '%';
                progText.textContent = `${i + 1} / ${total} readings sent (${pct}%)`;

            } catch (err) {
                addLog(`[UPLOAD] Error at row ${i}: ${err.message}`, 'critical');
            }

            if (speed > 0) {
                await new Promise(r => setTimeout(r, speed));
            }
        }

        addLog(`[UPLOAD] Stream complete. ${total} readings processed.`, 'info');
        startBtn.textContent = 'COMPLETE';
        isStreaming = false;
    });

    // ==========================================
    // 11. Global page-level drag-and-drop
    // ==========================================
    // If user drags a CSV anywhere on the page, show the upload overlay
    document.body.addEventListener('dragover', (e) => {
        e.preventDefault();
        if (!overlay.classList.contains('visible')) {
            overlay.classList.add('visible');
        }
    });

    // ==========================================
    // 12. Mission, What-If, and Recommendation Logic
    // ==========================================
    // ==========================================
    // 12. Mission, What-If, and Counterfactual Logic
    // ==========================================
    let activeMission = null;
    let whatIfAlternatives = [];

    function renderWhatIfControls() {
        const container = document.getElementById('whatif-controls');
        if (!container) return;
        
        let html = '';
        
        // Original Mission Controls (read-only)
        html += `
        <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; flex: 1; min-width: 200px;">
            <h4 style="color: var(--accent); margin-top: 0;">Original Mission</h4>
            <div style="margin-top: 10px;">
                <label style="display:block; font-size:12px; color:rgba(255,255,255,0.6);">Duration (min)</label>
                <input type="number" value="${activeMission.duration}" disabled style="width:100%; background:rgba(0,0,0,0.5); border:1px solid rgba(255,255,255,0.2); color:white; padding:5px; margin-bottom:10px;">
                
                <label style="display:block; font-size:12px; color:rgba(255,255,255,0.6);">Altitude (m)</label>
                <input type="number" value="${activeMission.altitude}" disabled style="width:100%; background:rgba(0,0,0,0.5); border:1px solid rgba(255,255,255,0.2); color:white; padding:5px; margin-bottom:10px;">
                
                <label style="display:block; font-size:12px; color:rgba(255,255,255,0.6);">Load (%)</label>
                <input type="number" value="${activeMission.load}" disabled style="width:100%; background:rgba(0,0,0,0.5); border:1px solid rgba(255,255,255,0.2); color:white; padding:5px;">
            </div>
        </div>`;
        
        // Alternative Scenarios
        whatIfAlternatives.forEach((alt, index) => {
            html += `
            <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; flex: 1; min-width: 200px;">
                <h4 style="color: white; margin-top: 0;">Alternative ${index + 1}</h4>
                <div style="margin-top: 10px;">
                    <label style="display:block; font-size:12px; color:rgba(255,255,255,0.6);">Duration (min)</label>
                    <input type="number" value="${alt.duration}" onchange="updateAlternative(${index}, 'duration', this.value)" style="width:100%; background:transparent; border:1px solid var(--accent); color:white; padding:5px; margin-bottom:10px;">
                    
                    <label style="display:block; font-size:12px; color:rgba(255,255,255,0.6);">Altitude (m)</label>
                    <input type="number" value="${alt.altitude}" onchange="updateAlternative(${index}, 'altitude', this.value)" style="width:100%; background:transparent; border:1px solid var(--accent); color:white; padding:5px; margin-bottom:10px;">
                    
                    <label style="display:block; font-size:12px; color:rgba(255,255,255,0.6);">Load (%)</label>
                    <input type="number" value="${alt.load}" onchange="updateAlternative(${index}, 'load', this.value)" style="width:100%; background:transparent; border:1px solid var(--accent); color:white; padding:5px;">
                </div>
            </div>`;
        });
        
        container.innerHTML = html;
        
        const btn = document.getElementById('btn-add-scenario');
        if (whatIfAlternatives.length >= 3) {
            btn.style.display = 'none';
        } else {
            btn.style.display = 'inline-block';
        }
    }

    window.updateAlternative = function(index, field, value) {
        whatIfAlternatives[index][field] = parseFloat(value);
        triggerWhatIfUpdate();
    };

    document.getElementById('btn-add-scenario')?.addEventListener('click', () => {
        if (whatIfAlternatives.length >= 3) return;
        const base = whatIfAlternatives.length > 0 ? whatIfAlternatives[whatIfAlternatives.length - 1] : activeMission;
        whatIfAlternatives.push({
            duration: base.duration,
            altitude: base.altitude,
            load: Math.max(10, base.load - 10)
        });
        renderWhatIfControls();
        triggerWhatIfUpdate();
    });

    window.selectMission = function(title, desc, load) {
        activeMission = { title, desc, load: parseFloat(load) };
        document.getElementById('whatif-desc').textContent = `Mission Selected: ${title}`;
        document.getElementById('whatif-container').style.display = 'block';
        document.getElementById('clear-mission-btn').style.display = 'inline-block';
        
        const cards = document.querySelectorAll('.mission-card');
        cards.forEach(c => c.style.border = '1px solid rgba(255,255,255,0.1)');
        event.currentTarget.style.border = '1px solid var(--accent-primary)';
        
        if (title.includes('Agriculture')) {
            activeMission.duration = 180;
            activeMission.altitude = 500;
        } else if (title.includes('Enemy Base')) {
            activeMission.duration = 240;
            activeMission.altitude = 4000;
        } else if (title.includes('Rescue')) {
            activeMission.duration = 90;
            activeMission.altitude = 2500;
        }
        
        whatIfAlternatives = [{
            duration: activeMission.duration,
            altitude: activeMission.altitude,
            load: activeMission.load > 70 ? 70 : activeMission.load - 10
        }];
        
        renderWhatIfControls();
        triggerWhatIfUpdate();
        
        if(voiceAssistant) voiceAssistant.speak(`Selected mission profile: ${title}. Preparing what if scenarios.`);
    };

    window.clearMission = function() {
        activeMission = null;
        whatIfAlternatives = [];
        document.getElementById('whatif-desc').textContent = 'Please select a mission from the Mission tab to view scenarios.';
        document.getElementById('whatif-container').style.display = 'none';
        document.getElementById('clear-mission-btn').style.display = 'none';
        
        const cards = document.querySelectorAll('.mission-card');
        cards.forEach(c => c.style.border = '1px solid rgba(255,255,255,0.1)');
        
        // Reset Recommendation Tab
        const rectStatus = document.getElementById('rect-status');
        const rectDesc = document.getElementById('rect-desc');
        const rectList = document.getElementById('rect-list');
        
        if (rectStatus) rectStatus.textContent = "SYSTEM NOMINAL";
        if (rectStatus) rectStatus.style.color = "var(--status-healthy)";
        if (rectDesc) rectDesc.textContent = "No mission selected. System is operating normally.";
        if (rectList) rectList.style.display = "none";
        
        window.hasSpokenRecommendation = false;
    };

    // Debounce to prevent lag
    let whatIfTimeout = null;
    window.triggerWhatIfUpdate = function() {
        if (whatIfTimeout) clearTimeout(whatIfTimeout);
        whatIfTimeout = setTimeout(() => {
            window.updateWhatIfAndRecommendation();
        }, 300);
    };

    window.updateWhatIfAndRecommendation = async function() {
        if (!activeMission || !window.currentData) return;
        
        const phm = window.currentData.phm;
        
        const engine_state = {
            health_index: phm.health_index,
            rul_hours: phm.rul_hours,
            degradation_rate: phm.degradation_rate || 0.0,
            anomaly_score: phm.anomaly_score,
            confidence: window.currentData.phm.anomaly_score < 0.5 ? 0.9 : 0.4
        };
        
        const original_mission = {
            duration_minutes: activeMission.duration,
            target_altitude: activeMission.altitude,
            engine_load_pct: activeMission.load
        };
        
        const alternativesPayload = whatIfAlternatives.map(alt => ({
            duration_minutes: alt.duration,
            target_altitude: alt.altitude,
            engine_load_pct: alt.load
        }));

        try {
            // Call /what-if (Counterfactual)
            const resWhatIf = await fetch('/api/mission/what-if', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ engine_state, original_mission, alternatives: alternativesPayload })
            });
            const dataWhatIf = await resWhatIf.json();
            
            if (dataWhatIf.scenarios) {
                // Render Table Head
                const tHead = document.getElementById('whatif-table-head');
                let headHtml = '<th style="padding: 12px; border-right: 1px solid rgba(255,255,255,0.1);">PARAMETER</th>';
                dataWhatIf.scenarios.forEach(scen => {
                    const isBest = scen.label === dataWhatIf.best_alternative;
                    const bg = isBest ? 'background: rgba(76, 175, 80, 0.2);' : '';
                    const color = isBest ? 'color: var(--status-healthy);' : '';
                    headHtml += `<th style="padding: 12px; text-align: center; ${bg} ${color}">${scen.label.toUpperCase()}${isBest ? ' ★' : ''}</th>`;
                });
                tHead.innerHTML = headHtml;
                
                // Render Table Body
                const tBody = document.getElementById('whatif-table-body');
                let bodyHtml = '';
                
                const rows = [
                    { label: "Duration (min)", key: "duration_minutes" },
                    { label: "Altitude (m)", key: "altitude_m" },
                    { label: "Load (%)", key: "load_pct" },
                    { label: "Risk Level", isRisk: true },
                    { label: "Recommendation", isRec: true }
                ];
                
                rows.forEach(r => {
                    bodyHtml += `<tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">`;
                    bodyHtml += `<td style="padding: 12px; border-right: 1px solid rgba(255,255,255,0.1); color: rgba(255,255,255,0.7);">${r.label}</td>`;
                    
                    dataWhatIf.scenarios.forEach(scen => {
                        const isBest = scen.label === dataWhatIf.best_alternative;
                        const bg = isBest ? 'background: rgba(76, 175, 80, 0.05);' : '';
                        
                        let val = '';
                        if (r.key) val = scen.params[r.key];
                        else if (r.isRisk) {
                            val = scen.result.risk_level;
                            let color = "var(--status-healthy)";
                            if (val === "CRITICAL" || val === "HIGH") color = "var(--status-critical)";
                            else if (val === "MODERATE") color = "var(--status-warning)";
                            val = `<span style="color: ${color}; font-weight: bold;">${val}</span>`;
                        }
                        else if (r.isRec) val = scen.result.recommendation.replace(/_/g, ' ');
                        
                        bodyHtml += `<td style="padding: 12px; text-align: center; ${bg}">${val}</td>`;
                    });
                    
                    bodyHtml += `</tr>`;
                });
                
                tBody.innerHTML = bodyHtml;
                
                // Render Reason
                let bestScen = dataWhatIf.scenarios.find(s => s.label === dataWhatIf.best_alternative) || dataWhatIf.scenarios[0];
                document.getElementById('whatif-reason-text').textContent = bestScen.result.reason;
                
                // Also update the analyze endpoints and recommendation tab based on Original
                const origScen = dataWhatIf.scenarios[0];
                
                const riskEl = document.getElementById("val-risk");
                if (riskEl) {
                    riskEl.innerText = origScen.result.risk_level;
                    if (origScen.result.risk_level === "HIGH") riskEl.style.color = "var(--status-critical)";
                    else if (origScen.result.risk_level === "MODERATE") riskEl.style.color = "var(--status-warning)";
                    else riskEl.style.color = "var(--status-healthy)";
                }
                
                const rectStatus = document.getElementById('rect-status');
                const rectDesc = document.getElementById('rect-desc');
                const rectList = document.getElementById('rect-list');
                
                if (origScen.result.risk_level === "HIGH" || origScen.result.risk_level === "MODERATE") {
                    rectStatus.textContent = "ACTION REQUIRED";
                    rectStatus.style.color = "var(--status-warning)";
                    rectDesc.textContent = `Mission "${activeMission.title}" has elevated risk. AI recommends the following counterfactual adjustments:`;
                    rectList.style.display = "flex";
                    
                    document.getElementById('rect-step1').textContent = `Recommended Action: ${bestScen.result.recommendation.replace(/_/g, ' ')} (${bestScen.label})`;
                    document.getElementById('rect-step2').textContent = `Reason: ${bestScen.result.reason}`;
                    document.getElementById('rect-step3').textContent = `Expected Effect: Lowers risk score to ${bestScen.result.risk_score.toFixed(0)}/100`;
                    
                    if (!window.hasSpokenRecommendation && window.voiceAssistant) {
                        window.voiceAssistant.speak(`Action Required. ${bestScen.result.reason}`);
                        window.hasSpokenRecommendation = true;
                    }
                } else {
                    rectStatus.textContent = "SYSTEM NOMINAL";
                    rectStatus.style.color = "var(--status-healthy)";
                    rectDesc.textContent = `No corrective actions required. Mission "${activeMission.title}" is viable.`;
                    rectList.style.display = "none";
                    window.hasSpokenRecommendation = false;
                }
            }
        } catch (e) {
            console.error("Failed to fetch mission API", e);
        }
    };
});
