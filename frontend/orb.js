(function() {
    const canvas = document.getElementById('orbCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    
    let width, height;
    let time = 0;
    
    function resize() {
        const parent = canvas.parentElement;
        width = parent.clientWidth;
        height = parent.clientHeight;
        canvas.width = width;
        canvas.height = height;
    }
    
    window.addEventListener('resize', resize);
    // Initial size setup
    setTimeout(resize, 0); 
    
    const targetState = {
        scale: 1.0,
        opacity: 0.2,
        speed: 0.5
    };
    
    const currentState = {
        scale: 1.0,
        opacity: 0.2,
        speed: 0.5
    };
    
    // Global trigger exposed for frontend/script.js
    window.setOrbState = function(state) {
        if (state === 'processing') {
            targetState.scale = 1.6;
            targetState.opacity = 0.8;
            targetState.speed = 3.0;
        } else {
            // default / chat mode
            targetState.scale = 1.0;
            targetState.opacity = 0.2;
            targetState.speed = 0.5;
        }
    };
    
    function lerp(a, b, t) {
        return a + (b - a) * t;
    }
    
    function drawLayer(radius, waves, amplitude, phase, opacity) {
        ctx.beginPath();
        for (let i = 0; i <= Math.PI * 2 + 0.1; i += 0.05) {
            // Complex wave combinations for an organic feel
            const r = radius 
                      + Math.sin(i * waves + phase) * amplitude 
                      + Math.cos(i * (waves * 0.5) - phase) * (amplitude * 0.5);
            
            const x = width / 2 + Math.cos(i) * r;
            const y = height / 2 + Math.sin(i) * r;
            
            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        }
        ctx.closePath();
        
        // Ensure opacity stays within bounds
        const safeOpacity = Math.max(0, Math.min(1, opacity));
        ctx.fillStyle = `rgba(124, 106, 239, ${safeOpacity})`;
        ctx.fill();
        ctx.strokeStyle = `rgba(124, 106, 239, ${Math.min(1, safeOpacity * 1.5)})`;
        ctx.lineWidth = 1.5;
        ctx.stroke();
    }
    
    function render() {
        ctx.clearRect(0, 0, width, height);
        
        if (width === undefined || height === undefined) {
            requestAnimationFrame(render);
            return;
        }
        
        // Smooth interpolation for fluid state transitions
        currentState.scale = lerp(currentState.scale, targetState.scale, 0.05);
        currentState.opacity = lerp(currentState.opacity, targetState.opacity, 0.05);
        currentState.speed = lerp(currentState.speed, targetState.speed, 0.05);
        
        time += 0.01 * currentState.speed;
        
        const baseRadius = (Math.min(width, height) * 0.15) * currentState.scale;
        
        // Render overlapping translucent mathematical layers
        drawLayer(baseRadius, 4, 15 * currentState.scale, time, currentState.opacity * 0.5);
        drawLayer(baseRadius * 0.9, 6, 20 * currentState.scale, -time * 1.2, currentState.opacity * 0.7);
        drawLayer(baseRadius * 0.8, 3, 25 * currentState.scale, time * 0.8, currentState.opacity);
        drawLayer(baseRadius * 0.5, 8, 10 * currentState.scale, -time * 2.0, currentState.opacity * 1.2);
        
        // Inner Core Glow
        ctx.beginPath();
        const glowRadius = baseRadius * 1.8;
        if (glowRadius > 0) {
            const gradient = ctx.createRadialGradient(width/2, height/2, 0, width/2, height/2, glowRadius);
            gradient.addColorStop(0, `rgba(124, 106, 239, ${Math.min(1, currentState.opacity * 0.4)})`);
            gradient.addColorStop(1, 'rgba(124, 106, 239, 0)');
            ctx.fillStyle = gradient;
            ctx.arc(width/2, height/2, glowRadius, 0, Math.PI * 2);
            ctx.fill();
        }
        
        requestAnimationFrame(render);
    }
    
    render();
})();
