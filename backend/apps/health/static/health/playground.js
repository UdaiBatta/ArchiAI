(() => {
  const scriptNames = ['playground-core.js', 'playground-scene.js', 'playground-pipeline.js', 'playground-ui.js'];
  const baseUrl = new URL('.', document.currentScript.src);
  const cacheSuffix = new URL(document.currentScript.src).search;

  const loadScript = index => {
    if (index >= scriptNames.length) return;
    const script = document.createElement('script');
    script.src = new URL(scriptNames[index], baseUrl).href + cacheSuffix;
    script.defer = false;
    script.onload = () => loadScript(index + 1);
    script.onerror = () => {
      throw new Error('Could not load ' + scriptNames[index]);
    };
    document.head.appendChild(script);
  };

  loadScript(0);
})();
