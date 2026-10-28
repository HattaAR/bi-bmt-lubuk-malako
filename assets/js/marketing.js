// Referensi desain UI: local highlighting, version-bound native navigation trigger.
export default function({parentElement,data,setTriggerValue}) {
 const host=parentElement.querySelector('.mk-host');host.innerHTML=data.html;
 let selected=null;
 const pick=id=>{
  selected=selected===id?null:id;
  host.querySelectorAll('[data-pick]').forEach(e=>e.setAttribute('aria-pressed',String(e.dataset.pick===selected)));
  host.querySelectorAll('tr[data-marketing]').forEach(e=>e.dataset.selected=String(e.dataset.marketing===selected));
  host.querySelector('.mk-clear').hidden=!selected;
 };
 host.querySelectorAll('[data-pick]').forEach(e=>e.onclick=()=>pick(e.dataset.pick));
 host.querySelector('.mk-clear').onclick=()=>{selected=null;pick(null);};
 host.querySelectorAll('button[data-metric]').forEach(e=>e.onclick=()=>setTriggerValue('metric',e.dataset.metric));
 host.querySelectorAll('button[data-open]').forEach(e=>e.onclick=()=>setTriggerValue('open',e.dataset.open));
}
