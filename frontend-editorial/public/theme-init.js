(function () {
  var m = localStorage.getItem('prism_color_mode') || 'system';
  var dark = m === 'dark' || (m !== 'light' && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.setAttribute('data-theme', dark ? 'espresso' : 'paper');
})();
