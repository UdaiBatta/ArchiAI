# Archi3D Frontend - Developer Quick Reference

## 🚀 Quick Start (5 minutes)

```bash
# Terminal 1: Start backend
cd "d:\My projects\Archi3D\backend"
.\.venv\Scripts\python manage.py runserver 0.0.0.0:8000

# Terminal 2: Start frontend
cd "d:\My projects\Archi3D\frontend"
npm run dev

# Terminal 3: Access browser
http://localhost:3000
```

---

## 📁 File Locations & Purposes

### Core Components
| File | Purpose | Lines |
|------|---------|-------|
| `src/components/Landing.jsx` | Landing page with prompt | 320 |
| `src/components/Studio.jsx` | Main design workspace | 480 |
| `src/App.jsx` | Router setup | 20 |

### Canvas Rendering
| File | Purpose | Lines |
|------|---------|-------|
| `src/utils/canvas2d.js` | 2D floor plan rendering | 180 |
| `src/utils/canvas3d.js` | 3D WebGL rendering | 380 |
| `src/utils/fallback.js` | Demo layouts & utilities | 150 |

### Styling
| File | Purpose | Lines |
|------|---------|-------|
| `src/styles/global.css` | Theme & global styles | 250 |
| `src/styles/landing.css` | Landing page styles | 200 |
| `src/styles/studio.css` | Studio page styles | 350 |

### Services
| File | Purpose | Lines |
|------|---------|-------|
| `src/api.js` | Axios API client | 120 |
| `.env.local` | Environment config | 1 |

---

## 🎯 Common Tasks

### Add a New Room Type

**Step 1:** Add color to `src/utils/fallback.js`
```javascript
const colors = {
  living_room: '#3B82F6',
  kitchen: '#F59E0B',
  conference_room: '#EF4444',  // ADD THIS
  // ...
}
```

**Step 2:** Use in `generateFallbackLayout()`
```javascript
layout_zones: [
  { type: 'conference_room', x: 0, y: 0, width: 10, depth: 8, floor: 1 },
  // ...
]
```

### Change Theme Color

Edit `src/styles/global.css`:
```css
:root {
  --color-accent-primary: #FF6B6B;  /* Change from #14b8a6 */
}
```

### Add New API Endpoint

In `src/api.js`:
```javascript
async getDesignCompliance(designId) {
  try {
    const res = await apiInstance.post(`/design/${designId}/compliance/`);
    return res.data;
  } catch (error) {
    throw new Error(`Compliance check failed: ${error.message}`);
  }
}
```

### Fix Canvas Not Rendering

**2D Canvas issues:**
```javascript
// In Studio.jsx useEffect for 2D rendering
render2DCanvas(canvas2dRef.current, zones, settings);
// Add console.log to debug
console.log('Zones to render:', zones);
```

**3D Canvas issues:**
```javascript
// In Studio.jsx, check if Canvas3D is initialized
if (canvas3d) {
  canvas3d.renderZones(zones);
}
```

---

## 🧪 Testing Checklist

### Landing Page Tests
- [ ] Prompt textarea accepts 1000 characters
- [ ] Character counter updates
- [ ] Example chips populate textarea
- [ ] Generate button disabled when prompt empty
- [ ] Settings form values persist to sessionStorage
- [ ] Generate redirects to `/studio`

### Studio Page Tests
- [ ] Page loads with correct title
- [ ] 2D canvas shows centered, scaled floor plan
- [ ] 3D button loads WebGL rendering
- [ ] Grid toggle works
- [ ] Layers clickable and highlight correctly
- [ ] Inspector shows room details on selection
- [ ] Statistics display correctly
- [ ] Export menu shows options
- [ ] Home button redirects to landing
- [ ] Demo badge shows for fallback layouts

### Canvas Interaction Tests
- [ ] Clicking room in 2D highlights in layers
- [ ] Clicking layer in list highlights on canvas
- [ ] Room details show in inspector
- [ ] 3D camera fit works
- [ ] 3D reset works
- [ ] Grid toggle shows/hides in 2D

### API Integration Tests
- [ ] Backend calls successful when API available
- [ ] Fallback layout generated on API error
- [ ] CORS headers correct
- [ ] Design data persists across page reload
- [ ] Export buttons work (UI or download)

---

## 🔍 Debugging Tips

### Check State
```javascript
// In React DevTools or console
console.log('sessionStorage:', sessionStorage.getItem('design'));
console.log('zones:', zones);
console.log('selectedZoneId:', selectedZoneId);
```

### Monitor API Calls
```javascript
// Network tab in DevTools shows all requests
// Look for POST /api/v1/design/
// Check response headers for Access-Control-Allow-Origin
```

### Test Fallback
```javascript
// Force fallback by changing backend URL
VITE_API_BASE_URL=http://localhost:9999  // Wrong port
// Then generate design - should use demo layout
```

### 3D Debugging
```javascript
// Add to Canvas3D class
console.log('Scene children:', this.scene.children.length);
console.log('Camera position:', this.camera.position);
console.log('Zones being rendered:', zones.length);
```

---

## 📊 Performance Optimization

### Current Metrics
- Landing page: ~200ms load
- Studio page: ~400ms (includes 3D scene)
- 2D render: <10ms
- 3D render: ~50ms

### Optimization Opportunities
1. **Lazy load Three.js** - Load only when 3D tab clicked
2. **Memoize components** - `React.memo()` on Landing/Studio
3. **Optimize canvas render** - Use `requestAnimationFrame` throttling
4. **Cache API responses** - Store in localStorage

---

## 🐛 Common Issues & Solutions

### Issue: "Cannot read property 'current' of undefined"
```javascript
// Make sure to initialize ref in component
const canvas2dRef = useRef(null);
// And attach to actual element
<canvas ref={canvas2dRef} className="canvas-2d" />
```

### Issue: CORS errors from backend
```
Frontend: http://localhost:3000
Backend: http://localhost:8000
Solution: Add to backend settings:
CORS_ALLOWED_ORIGINS = ["http://localhost:3000"]
```

### Issue: 3D not showing anything
```javascript
// Check WebGL context
const context = canvas.getContext('webgl2');
if (!context) {
  console.error('WebGL not supported');
  // Fallback to 2D mode
}
```

### Issue: Zones not clickable
```javascript
// Make sure getClickedZone returns correct coordinates
const zoneAtClick = getClickedZone(canvas, zones, e.offsetX, e.offsetY, settings);
console.log('Clicked zone:', zoneAtClick);
```

---

## 🔧 Build & Deployment

### Development
```bash
npm run dev        # Start dev server on port 3000
```

### Production Build
```bash
npm run build      # Create dist/ folder
npm run preview    # Test production build locally
```

### Deploy to Production
```bash
# Build frontend
npm run build

# Copy dist/ to web server
# Example with nginx:
# - Copy dist/* to /var/www/archi3d/

# Update backend CORS
# In backend/archi3d/settings/production.py:
CORS_ALLOWED_ORIGINS = ["https://archi3d.com"]
FRONTEND_URL = "https://archi3d.com"
```

---

## 📚 Tech Stack Reference

- **React 18** - UI framework
- **Vite 8** - Build tool
- **Three.js** - 3D rendering
- **Axios** - HTTP client
- **React Router** - SPA routing
- **CSS3** - Styling with variables
- **HTML5 Canvas** - 2D rendering

---

## 🎨 CSS Variables Reference

```css
/* Colors */
--color-bg-primary: #0b1020           /* Main background */
--color-bg-surface: #111827           /* Elevated surfaces */
--color-bg-panel: #151b2e             /* Panel backgrounds */
--color-canvas: #0f172a               /* Canvas background */

/* Text */
--color-text-primary: #e5e7eb         /* Primary text */
--color-text-muted: #94a3b8           /* Secondary text */

/* Accents */
--color-accent-primary: #14b8a6       /* Teal - main accent */
--color-accent-secondary: #2dd4bf     /* Light teal */
--color-accent-tertiary: #06b6d4      /* Cyan */

/* Success/Error */
--color-success: #10b981              /* Green */
--color-error: #ef4444                /* Red */
--color-warning: #f59e0b              /* Orange */
```

---

## 🚀 Performance Checklist

- [ ] Lighthouse score > 90
- [ ] First Contentful Paint < 1s
- [ ] Time to Interactive < 2s
- [ ] Cumulative Layout Shift < 0.1
- [ ] Bundle size < 200KB gzipped
- [ ] 3D canvas 60 FPS on mid-range devices

---

## 📝 Commit Message Format

```
feat: Add new room type selector
      Allows users to add custom room types to designs

fix: Fix 2D canvas not centering on page load
     Added bounding box calculation in render2DCanvas

docs: Update API documentation
      Added new endpoints and examples

refactor: Simplify canvas rendering logic
         Extracted common functions to utils

test: Add unit tests for fallback layout generation
      Coverage: 85%
```

---

## 🔐 Security Checklist

- [ ] No sensitive data in frontend code
- [ ] API calls use HTTPS in production
- [ ] CORS headers properly configured
- [ ] CSP headers set in backend
- [ ] No localStorage of passwords/tokens (use httpOnly cookies)
- [ ] Input validation on all forms

---

## 📞 Need Help?

1. Check `FRONTEND_SETUP_GUIDE.md` for full documentation
2. Look in browser console for error messages
3. Check network tab for failed API calls
4. Review Django backend logs for server errors
5. Test with demo layout to isolate API issues

---

**Last Updated:** May 9, 2026  
**Frontend Version:** 1.0.0  
**Status:** ✅ Ready for Development
