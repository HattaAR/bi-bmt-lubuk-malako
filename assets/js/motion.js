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
  const homeStates = new Map(), homeNumbers = new Map();
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
    // Opt-in pilot targets share this controller; other pages keep their rules.
    ['vertical', '[data-bmt-home-bar]'],
    ['reveal', '[data-bmt-home-reveal]'],
    ['panel', '.home-category-panel'],
    ['panel', '.home-plot'],
    ['horizontal', '[data-bmt-quality-bar]'],
    ['donut', '[data-bmt-quality-donut]'],
    ['panel', '.qp-composition'],
  ];
  try { CSS.registerProperty({name:'--bmt-composition-progress',syntax:'<percentage>',inherits:true,initialValue:'100%'}); } catch (_) {}
  try { CSS.registerProperty({name:'--bmt-donut-progress',syntax:'<angle>',inherits:true,initialValue:'360deg'}); } catch (_) {}
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
    if(page!==next){cancelAll();records.clear();rootScopes.clear();homeStates.clear();homeNumbers.clear();seenNodes=new WeakSet();visit++;page=next;}
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
    if(job.numberSource!==undefined)homeNumbers.set(key,job.numberSource);
    if (records.size>512) records.delete(records.keys().next().value);
    if (reduced.matches) return;
    let animation=null,raf=0,done=false;
    const final=el.dataset.bmtFinal;
    const visual=kind==='number'?el.querySelector('[aria-hidden="true"]'):null;
    job.finish=(wasCancelled=false) => {
      if(done)return;done=true;
      cancelAnimationFrame(raf);animation?.cancel();
      if(visual&&el.isConnected&&el.dataset.bmtFinal===final&&
         (!['home','quality'].includes(job.sourceRoot.dataset.bmtMotion)||job.sourceRoot.dataset.bmtSnapshot===token)) visual.textContent=final;
      active.delete(job);
      if(wasCancelled)cancelled++;else completed++;
      emit(wasCancelled?'cancel':'end',kind);
    };
    active.add(job);started++;
    const home=job.sourceRoot.dataset.bmtMotion==='home';
    const quality=job.sourceRoot.dataset.bmtMotion==='quality',modern=home||quality;
    const panel=kind==='card'||kind==='panel';
    const runDuration=modern?(panel?300:760):duration;
    const runDelay=modern?(panel?60*Math.min(job.index,2):60+60*Math.min(job.index,2)):0;
    if (kind==='number') {
      const value=Number(el.dataset.bmtCount);
      if(!visual||!Number.isFinite(value)){job.finish();return;}
      visual.style.minWidth=visual.getBoundingClientRect().width+'px';
      visual.style.display='inline-block';visual.style.fontVariantNumeric='tabular-nums';
      const places=modern?Number(el.dataset.bmtPlaces??2):2;
      const prefix=modern?(el.dataset.bmtPrefix??''):'';
      const rawSuffix=modern?(el.dataset.bmtSuffix??'%'):'%';
      const suffix=modern&&el.hasAttribute('data-bmt-suffix')&&rawSuffix&&!rawSuffix.startsWith(' ')?' '+rawSuffix:rawSuffix;
      const format=new Intl.NumberFormat('id-ID',{minimumFractionDigits:places,maximumFractionDigits:places});
      const began=performance.now()+runDelay;visual.textContent=prefix+format.format(0)+suffix;
      emit('start',kind);
      const tick=now=>{
        if(!el.isConnected||job.visit!==visit||job.sourceRoot.dataset.bmtSnapshot!==token||el.dataset.bmtFinal!==final){job.finish(true);return;}
        if(now<began){raf=requestAnimationFrame(tick);return;}
        const p=Math.min(1,(now-began)/runDuration), eased=1-Math.pow(1-p,3);
        if(p===1){job.finish();return;}
        visual.textContent=prefix+format.format(value*eased)+suffix;raf=requestAnimationFrame(tick);
      };raf=requestAnimationFrame(tick);
    } else {
      emit('start',kind);
      let frames;
      if(kind==='horizontal'||kind==='vertical') {
        el.style.transformOrigin=kind==='horizontal'?'left center':'center bottom';
        const start=home?0.08:0;
        frames={transform:kind==='horizontal'?[`scaleX(${start})`,'scaleX(1)']:[`scaleY(${start})`,'scaleY(1)']};
      } else if(kind==='composition') {
        el.classList.add('bmt-motion-composition');
        frames={'--bmt-composition-progress':['0%','100%']};
      } else if(kind==='donut')frames={'--bmt-donut-progress':['0deg','360deg']};
      else if(kind==='reveal')frames={clipPath:['inset(0 92% 0 0)','inset(0 0% 0 0)']};
      else if(modern&&panel)frames={opacity:[.86,1],transform:['translateY(6px)','translateY(0)']};
      else frames={opacity:(kind==='card'||kind==='treemap')?[0.85,1]:[0.12,1]};
      animation=el.animate(frames,{duration:runDuration,easing,...(modern?{delay:runDelay,fill:'backwards'}:{})});
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
    const home=sourceRoot.dataset.bmtMotion==='home';
    const modern=home||sourceRoot.dataset.bmtMotion==='quality';
    let trigger=null;
    if(modern){
      const context=sourceRoot.dataset.bmtContext||nextScope,previous=homeStates.get(rootKey);
      if(!previous||previous.token!==nextScope){
        trigger=!previous?'entry':previous.context!==context?'data':'metric';
        homeStates.set(rootKey,{token:nextScope,context,trigger});
      }else trigger=previous.trigger;
    }
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
    if(modern){
      // Only entry fades panels. Data/metric reruns animate current data, not the shell.
      if((kind==='card'||kind==='panel')&&trigger!=='entry')return;
      if(kind==='number'){
        if((trigger!=='metric'&&homeNumbers.get(key)===source)||Number(el.dataset.bmtCount)===0){homeNumbers.set(key,source);return;}
      }
    }
    const job={el,kind,key,signature,token:nextScope,sourceRoot,visit,index,trigger,
      ...(modern&&kind==='number'?{numberSource:source}:{})};
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
