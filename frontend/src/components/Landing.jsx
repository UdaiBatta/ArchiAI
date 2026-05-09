import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiService } from '../api';
import { generateFallbackLayout } from '../utils/fallback';
import '../styles/landing.css';

const PROMPT_EXAMPLES = [
  '2-floor Mumbai residence on 30m x 40m plot with parking',
  'Vastu compliant house with good natural light',
  'Modern office with reception and meeting rooms',
  'Compact residential layout with shared courtyard',
];

export default function Landing() {
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState('');
  const [settings, setSettings] = useState({
    location: 'Mumbai',
    plotWidth: 30,
    plotDepth: 40,
    numFloors: 2,
    buildingType: 'residential',
    useVastu: false,
    region: 'auto-detect',
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const handlePromptExample = (example) => {
    setPrompt(example);
  };

  const handleGenerateDesign = async () => {
    if (!prompt.trim()) {
      setError('Please enter a design prompt');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      // Store settings in sessionStorage
      sessionStorage.setItem(
        'designSettings',
        JSON.stringify({
          prompt,
          ...settings,
        })
      );

      // Try to generate design from backend
      const response = await apiService.generateDesign({
        prompt,
        plotWidth: parseFloat(settings.plotWidth),
        plotDepth: parseFloat(settings.plotDepth),
        numFloors: parseInt(settings.numFloors),
        buildingType: settings.buildingType,
        useVastu: settings.useVastu,
        region: settings.region,
      });

      // Store design in sessionStorage
      sessionStorage.setItem('currentDesign', JSON.stringify(response.data));

      // Navigate to studio
      navigate('/studio');
    } catch (err) {
      console.error('Design generation failed:', err);

      // Fall back to demo layout
      const fallback = generateFallbackLayout({
        plotWidth:    parseFloat(settings.plotWidth),
        plotDepth:    parseFloat(settings.plotDepth),
        numFloors:    parseInt(settings.numFloors),
        prompt,
        buildingType: settings.buildingType,
      });

      sessionStorage.setItem('currentDesign', JSON.stringify(fallback));
      sessionStorage.setItem(
        'designSettings',
        JSON.stringify({
          prompt,
          ...settings,
          isFallback: true,
        })
      );

      navigate('/studio');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSettingChange = (key, value) => {
    setSettings((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  return (
    <div className="landing">
      {/* Header */}
      <header className="landing-header">
        <div className="landing-logo">
          <div className="logo-icon">🏛</div>
          <h1>Archi3D Studio</h1>
        </div>
        <p className="landing-tagline">Design architectural concepts from a simple prompt.</p>
      </header>

      {/* Main content */}
      <main className="landing-main">
        <div className="landing-container">
          {/* Prompt Section */}
          <section className="prompt-section">
            <div className="form-group">
              <label htmlFor="prompt">Design Brief</label>
              <textarea
                id="prompt"
                placeholder="Describe your project, location, plot size, floors, vastu needs, parking, and design style…"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows="4"
                className="prompt-textarea"
              />
              <div className="char-count">{prompt.length} / 1000</div>
            </div>

            {/* Quick Examples */}
            <div className="quick-examples">
              <p className="quick-examples-label">Quick start examples:</p>
              <div className="examples-grid">
                {PROMPT_EXAMPLES.map((example, idx) => (
                  <button
                    key={idx}
                    className="example-chip"
                    onClick={() => handlePromptExample(example)}
                  >
                    {example}
                  </button>
                ))}
              </div>
            </div>

            {/* Error message */}
            {error && <div className="error-message">{error}</div>}
          </section>

          {/* Settings Section */}
          <section className="settings-section">
            <h2>Project Settings</h2>

            <div className="settings-grid">
              {/* Location */}
              <div className="form-group">
                <label htmlFor="location">Location</label>
                <input
                  id="location"
                  type="text"
                  placeholder="e.g., Mumbai, Delhi, NYC"
                  value={settings.location}
                  onChange={(e) => handleSettingChange('location', e.target.value)}
                  className="form-input"
                />
              </div>

              {/* Plot dimensions */}
              <div className="form-group">
                <label htmlFor="plotWidth">Plot Width (m)</label>
                <input
                  id="plotWidth"
                  type="number"
                  min="10"
                  max="100"
                  value={settings.plotWidth}
                  onChange={(e) => handleSettingChange('plotWidth', e.target.value)}
                  className="form-input"
                />
              </div>

              <div className="form-group">
                <label htmlFor="plotDepth">Plot Depth (m)</label>
                <input
                  id="plotDepth"
                  type="number"
                  min="10"
                  max="100"
                  value={settings.plotDepth}
                  onChange={(e) => handleSettingChange('plotDepth', e.target.value)}
                  className="form-input"
                />
              </div>

              {/* Floors */}
              <div className="form-group">
                <label htmlFor="numFloors">Floors</label>
                <input
                  id="numFloors"
                  type="number"
                  min="1"
                  max="10"
                  value={settings.numFloors}
                  onChange={(e) => handleSettingChange('numFloors', e.target.value)}
                  className="form-input"
                />
              </div>

              {/* Building Type */}
              <div className="form-group">
                <label htmlFor="buildingType">Building Type</label>
                <select
                  id="buildingType"
                  value={settings.buildingType}
                  onChange={(e) => handleSettingChange('buildingType', e.target.value)}
                  className="form-input"
                >
                  <option value="residential">Residential</option>
                  <option value="commercial">Commercial</option>
                  <option value="mixed-use">Mixed-use</option>
                </select>
              </div>

              {/* Region */}
              <div className="form-group">
                <label htmlFor="region">Bylaw Region</label>
                <select
                  id="region"
                  value={settings.region}
                  onChange={(e) => handleSettingChange('region', e.target.value)}
                  className="form-input"
                >
                  <option value="auto-detect">Auto-detect</option>
                  <option value="mumbai">🇮🇳 Mumbai</option>
                  <option value="delhi">🇮🇳 Delhi</option>
                  <option value="nyc">🇺🇸 New York City</option>
                  <option value="default">Default</option>
                </select>
              </div>

              {/* Vastu */}
              <div className="form-group checkbox">
                <label htmlFor="vastu">
                  <input
                    id="vastu"
                    type="checkbox"
                    checked={settings.useVastu}
                    onChange={(e) => handleSettingChange('useVastu', e.target.checked)}
                  />
                  <span>Vastu Compliance</span>
                </label>
              </div>
            </div>
          </section>

          {/* Buttons */}
          <div className="landing-buttons">
            <button
              className="btn btn-primary"
              onClick={handleGenerateDesign}
              disabled={isLoading || !prompt.trim()}
            >
              {isLoading ? 'Generating Design…' : '✨ Generate Design'}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
