// Shared local presentation only. No network requests, SQL, timers or rerun triggers.
function installMotion() {
  const version = '__BMT_MOTION_VERSION__';
  if (window.BMTMotion?.version === version) return;
  window.BMTMotion?.dispose();
  const main = document.querySelector('[data-testid="stMain"]');
  const app = document.querySelector('[data-testid="stApp"]');
  if (!main || !app) return;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const duration = 500, easing = 'cubic-bezier(0.2,0.7,0.2,1)';
  const instance=crypto.randomUUID();
  const records = new Map(), rootScopes = new Map(), active = new Set(), pending = new Map();
  let seenNodes = new WeakSet(), page = null, visit = 0, enabled = false;
  let scheduled = 0, completed = 0, cancelled = 0, started = 0;
  const roots = new Set();
  const rules = [
    ['card', '.bmt-kpi,.qp-npf,.cn-hero,.mk-summary,.hi-summary,.sm-result'],
    ['number', '[data-bmt-count]'],
    ['horizontal', '.bmt-track>div,.mk-bar,.sm-relative i>b'],
    ['vertical', '.hi-bar'],
    ['composition', '.qp-stacked:has(button)'],
    ['treemap', '.cn-treemap:has(.cn-tile)'],
    ['dot', '.mk-point>i'],
  ];
  try { CSS.registerProperty({name:'--bmt-composition-progress',syntax:'<percentage>',inherits:true,initialValue:'100%'}); } catch (_) {}
  const hash = text => { let h=2166136261;for(let i=0;i<text.length;i++) h=Math.imul(h^text.charCodeAt(i),16777619);return (h>>>0).toString(16); };
  const emit = (phase,kind) => window.dispatchEvent(new CustomEvent('bmt:motion',{detail:{phase,kind,at:performance.now()}}));
  const visible = el => { const r=el.getBoundingClientRect();return r.width>0&&r.height>0&&r.bottom>0&&r.top<innerHeight&&getComputedStyle(el).visibility!=='hidden'; };
  const currentRoute=route=>{
    if(route===undefined||route===null)return true;
    const path=decodeURIComponent(location.pathname).replace(/\/+$/,'');
    return route===''?path==='':path.endsWith('/'+route);
  };
  function changePage(next){
    enabled=!!next;
    if(page!==next){cancelAll();records.clear();rootScopes.clear();seenNodes=new WeakSet();visit++;page=next;}
  }
  const cancelAll = () => {
    for (const job of [...active]) job.finish(true);
    for (const el of pending.keys()) intersection.unobserve(el);
    pending.clear();
  };
  function start(job) {
    const {el,kind,key,signature,token}=job;
    intersection.unobserve(el);pending.delete(el);
    if (!el.isConnected || !enabled || job.visit!==visit || job.sourceRoot.dataset.bmtSnapshot!==token) return;
    if (records.get(key)===signature) return;
    records.set(key,signature);
    if (records.size>512) records.delete(records.keys().next().value);
    if (reduced.matches) return;
    let animation=null,raf=0,done=false;
    const final=el.dataset.bmtFinal;
    const visual=kind==='number'?el.querySelector('[aria-hidden="true"]'):null;
    job.finish=(wasCancelled=false) => {
      if(done)return;done=true;
      cancelAnimationFrame(raf);animation?.cancel();
      if(visual&&el.isConnected&&el.dataset.bmtFinal===final) visual.textContent=final;
      active.delete(job);
      if(wasCancelled)cancelled++;else completed++;
      emit(wasCancelled?'cancel':'end',kind);
    };
    active.add(job);started++;
    if (kind==='number') {
      const value=Number(el.dataset.bmtCount);
      if(!visual||!Number.isFinite(value)){job.finish();return;}
      visual.style.minWidth=visual.getBoundingClientRect().width+'px';
      visual.style.display='inline-block';visual.style.fontVariantNumeric='tabular-nums';
      const format=new Intl.NumberFormat('id-ID',{minimumFractionDigits:2,maximumFractionDigits:2});
      const began=performance.now();visual.textContent=format.format(0)+'%';
      emit('start',kind);
      const tick=now=>{
        if(!el.isConnected||job.visit!==visit||job.sourceRoot.dataset.bmtSnapshot!==token||el.dataset.bmtFinal!==final){job.finish(true);return;}
        const p=Math.min(1,(now-began)/duration), eased=1-Math.pow(1-p,3);
        if(p===1){job.finish();return;}
        visual.textContent=format.format(value*eased)+'%';raf=requestAnimationFrame(tick);
      };raf=requestAnimationFrame(tick);
    } else {
      emit('start',kind);
      let frames;
      if(kind==='horizontal'||kind==='vertical') {
        el.style.transformOrigin=kind==='horizontal'?'left center':'center bottom';
        frames={transform:kind==='horizontal'?['scaleX(0)','scaleX(1)']:['scaleY(0)','scaleY(1)']};
      } else if(kind==='composition') {
        el.classList.add('bmt-motion-composition');
        frames={'--bmt-composition-progress':['0%','100%']};
      } else frames={opacity:(kind==='card'||kind==='treemap')?[0.85,1]:[0.12,1]};
      animation=el.animate(frames,{duration,easing});
      animation.onfinish=()=>job.finish();animation.oncancel=()=>{if(!done)job.finish(true);};
    }
  }
  const intersection=new IntersectionObserver(entries=>{
    for(const entry of entries) if(entry.isIntersecting&&pending.has(entry.target)) start(pending.get(entry.target));
  },{threshold:0.01});
  function register(el,kind,selector) {
    const sourceRoot=el.closest('[data-bmt-snapshot]');
    if(!sourceRoot||!currentRoute(sourceRoot.dataset.bmtRoute)||el.closest('[data-stale="true"]'))return;
    changePage(sourceRoot.dataset.bmtPage);
    const nextScope=sourceRoot.dataset.bmtSnapshot;
    const rootKey=sourceRoot.dataset.bmtPage+'|'+sourceRoot.className+'|';
    if(rootScopes.get(rootKey)!==nextScope){
      for(const key of [...records.keys()])if(key.startsWith(rootKey))records.delete(key);
      rootScopes.set(rootKey,nextScope);
    }
    if(seenNodes.has(el))return;
    seenNodes.add(el);
    const siblings=[...(sourceRoot.matches(selector)?[sourceRoot]:[]),...sourceRoot.querySelectorAll(selector)];
    const index=siblings.indexOf(el);
    const key=rootKey+kind+':'+index;
    const source=kind==='number'?el.dataset.bmtCount+'|'+el.dataset.bmtFinal:
      el.getAttribute('style')+'|'+el.textContent+'|'+(kind==='composition'||kind==='treemap'?el.innerHTML:'');
    const signature=nextScope+'|'+hash(source);
    const job={el,kind,key,signature,token:nextScope,sourceRoot,visit};
    if(visible(el))start(job);
    else {pending.set(el,job);intersection.observe(el);}
  }
  function scan() {
    scheduled=0;
    if(!enabled){roots.clear();return;}
    for(const root of roots){
      if(!root.isConnected)continue;
      for(const [kind,selector] of rules){
        if(root.matches?.(selector))register(root,kind,selector);
        root.querySelectorAll?.(selector).forEach(el=>register(el,kind,selector));
      }
    }roots.clear();
    for(const job of [...active])if(!job.el.isConnected)job.finish(true);
    for(const el of [...pending.keys()])if(!el.isConnected){intersection.unobserve(el);pending.delete(el);}
  }
  const observer=new MutationObserver(mutations=>{
    for(const m of mutations)for(const node of m.addedNodes){
      if(node.nodeType!==1||node.closest?.('[data-bmt-count]'))continue;
      if(node.matches?.('.st-key-bmt_login')||node.querySelector?.('.st-key-bmt_login'))api.begin(null);
      roots.add(node);
    }
    // MutationObserver runs before paint: initialize new counters at zero now,
    // rather than painting the final value once and restarting on a later RAF.
    scan();
  });
  observer.observe(main,{subtree:true,childList:true});
  const stateObserver=new MutationObserver(()=>{
    if(app.dataset.testScriptState==='running')cancelAll();
  });
  stateObserver.observe(app,{attributes:true,attributeFilter:['data-test-script-state']});
  const reduceChanged=()=>{if(reduced.matches)cancelAll();};
  reduced.addEventListener('change',reduceChanged);
  const api={version,
    begin(next,route){
      if(!currentRoute(route))return;
      changePage(next);
      roots.add(main);scan();
    },
    inspect(){return {instance,active:active.size,pending:pending.size,started,completed,cancelled,reduced:reduced.matches};},
    dispose(){cancelAll();observer.disconnect();stateObserver.disconnect();intersection.disconnect();cancelAnimationFrame(scheduled);reduced.removeEventListener('change',reduceChanged);}
  };
  window.BMTMotion=api;
}

export default function({data,parentElement}) {
  installMotion();
  const controller=window.BMTMotion;
  if(!controller)return;
  controller.domBoundary={
    sameDocument:parentElement.ownerDocument===document,
    rootType:parentElement.getRootNode().nodeType,
    mainReachable:!!document.querySelector('[data-testid="stMain"]'),
    framed:window.frameElement!==null
  };
  controller.begin(data.page,data.route);
  return ()=>{
    controller.dispose();
    if(window.BMTMotion===controller)delete window.BMTMotion;
  };
}
