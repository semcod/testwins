() => {
  if (window.__testwins_live_v1) return;
  const state={revision:0,last:performance.now(),layoutShifts:0,shiftValue:0};
  const touch=()=>{state.revision++;state.last=performance.now();};
  new MutationObserver(touch).observe(document,{subtree:true,childList:true,attributes:true,characterData:true});
  for(const name of ['resize','scroll','load']) window.addEventListener(name,touch,true);
  try {new PerformanceObserver(list=>{for(const e of list.getEntries()){
    if(!e.hadRecentInput){state.layoutShifts++;state.shiftValue+=e.value;touch();}
  }}).observe({type:'layout-shift',buffered:false});} catch {}
  window.__testwins_live_v1=state;
}
