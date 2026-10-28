// Referensi desain UI: scoped, session-specific CCv2 events and visual highlighting.
export default function ({ parentElement, data, setTriggerValue }) {
  const host=parentElement.querySelector('.cn-host');
  host.innerHTML=data.html; // All source labels are escaped in Python.
  let selected=null;
  const pick=id=>{
    selected=selected===id?null:id;
    host.querySelectorAll('[data-pick]').forEach(e=>e.setAttribute('aria-pressed',String(e.dataset.pick===selected)));
    host.querySelectorAll('tr[data-group]').forEach(e=>e.dataset.selected=String(e.dataset.group===selected));
    host.querySelector('.cn-clear').hidden=!selected;
  };
  host.querySelectorAll('[data-pick]').forEach(e=>e.onclick=()=>pick(e.dataset.pick));
  host.querySelector('.cn-clear').onclick=()=>{selected=null;host.querySelectorAll('[data-pick]').forEach(e=>e.setAttribute('aria-pressed','false'));host.querySelectorAll('tr[data-group]').forEach(e=>e.dataset.selected='false');host.querySelector('.cn-clear').hidden=true;};
  host.querySelectorAll('button[data-metric]').forEach(e=>e.onclick=()=>setTriggerValue('metric',e.dataset.metric));
  host.querySelectorAll('[data-open]').forEach(e=>e.onclick=()=>setTriggerValue('open',e.dataset.open));
  const resize=new ResizeObserver(entries=>{
    for(const {target,contentRect:r} of entries){target.dataset.size=r.width>=150&&r.height>=140?'large':r.width>=75&&r.height>=26?'small':'tiny';}
  });
  host.querySelectorAll('.cn-tile').forEach(e=>resize.observe(e));
  return ()=>resize.disconnect();
}
