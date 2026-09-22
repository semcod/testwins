'use strict';
(() => {
  const root=document.documentElement;
  const themeButton=document.getElementById('theme-toggle');
  const themeLabel=document.getElementById('theme-label');
  // Start deterministically; only this explicit control changes the theme.
  themeButton?.addEventListener('click',()=>{
    const light=root.dataset.theme!=='light';root.dataset.theme=light?'light':'dark';
    themeLabel.textContent=light?'Tryb ciemny':'Tryb jasny';
  });
  const menu=document.getElementById('menu-toggle');
  menu?.addEventListener('click',()=>{
    const expanded=menu.getAttribute('aria-expanded')!=='true';
    menu.setAttribute('aria-expanded',String(expanded));
    document.getElementById('main-nav').classList.toggle('open',expanded);
  });
  const presets={web:['Audyt landing page','make landing-check'],shell:['Scenariusz shell przez TestQL','make scenario-demo'],gui:['Izolowany pulpit Linux','make desktop-demo']};
  document.querySelectorAll('[data-platform]').forEach(button=>button.addEventListener('click',()=>{
    document.querySelectorAll('[data-platform]').forEach(other=>{other.classList.remove('active');other.setAttribute('aria-pressed','false');});
    button.classList.add('active');button.setAttribute('aria-pressed','true');
    const [label,command]=presets[button.dataset.platform];
    document.getElementById('platform-state').textContent=label;
    document.getElementById('install-command').textContent=command;
    document.getElementById('copy-status').textContent='Komenda do uruchomienia lokalnie.';
  }));
  document.getElementById('copy-command')?.addEventListener('click',async()=>{
    const command=document.getElementById('install-command');const status=document.getElementById('copy-status');
    try {
      if(!navigator.clipboard?.writeText)throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(command.textContent);status.textContent='Skopiowano komendę.';
    } catch {
      const range=document.createRange();range.selectNodeContents(command);const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);
      status.textContent='Komenda zaznaczona. Użyj Ctrl+C lub ⌘C.';
    }
  });
})();
