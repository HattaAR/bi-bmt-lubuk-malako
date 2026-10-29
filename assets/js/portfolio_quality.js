// Trusted local referensi desain UI interactions, scoped to this snapshot only.
(() => {
  const root = document.querySelector('.qp-root');
  if (!root) return;
  // st.html's HTML-only sanitizer strips inline SVG. Build only fixed SVG
  // elements/attributes from escaped, service-supplied presentation metadata.
  // No innerHTML, executable input, network, extra observer or animation runtime.
  const ring=root.querySelector('[data-bmt-quality-donut]');
  if(ring&&!ring.querySelector('svg')){
    const node=(tag,attrs)=>{const e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,String(v));return e;};
    const svg=node('svg',{viewBox:'0 0 240 240','aria-label':ring.dataset.label});
    const g=node('g',{transform:'rotate(-90 120 120)'});
    ring.querySelectorAll('.qp-slice-source').forEach(source=>{
      const d=source.dataset,share=Number(d.share),offset=Number(d.offset);
      if(!Number.isFinite(share)||!Number.isFinite(offset)||share<=0||share>100||!/^#[a-f\d]{6}$/i.test(d.color))return;
      const circle=node('circle',{cx:120,cy:120,r:88,fill:'none',stroke:d.color,'stroke-width':26,pathLength:100,
        'stroke-dasharray':`${share} ${100-share}`,'stroke-dashoffset':-offset,role:'button',tabindex:0,
        'aria-pressed':'false','aria-label':d.tooltip,'data-pick':d.pick,'data-category':d.category,
        'data-value':d.value,'data-share':d.share});
      const title=node('title',{});title.textContent=d.tooltip;circle.append(title);g.append(circle);
    });
    svg.append(g);ring.append(svg);
  }
  let selected = null;
  const clear = root.querySelector('.qp-clear');
  const apply = code => {
    root.querySelectorAll('.qp-donut [data-category],.qp-legend-row,.qp-arrears-row').forEach(el => {
      el.dataset.dimmed = !!code && el.dataset.category !== code;
    });
    root.querySelectorAll('.qp-detail-row').forEach(el => {
      el.dataset.highlight = !!code && el.dataset.category === code;
    });
    root.querySelectorAll('[data-pick]:not([hidden])').forEach(el => {
      el.setAttribute('aria-pressed', String(!!selected && el.dataset.pick === selected));
    });
    clear.hidden = !selected;
  };
  root.querySelectorAll('[data-pick]:not([hidden])').forEach(el => {
    el.onclick = () => { selected = selected === el.dataset.pick ? null : el.dataset.pick; apply(selected); };
    if(el.tagName.toLowerCase()==='circle')el.onkeydown=event=>{
      if(event.key==='Enter'||event.key===' '){event.preventDefault();el.onclick();}
    };
    el.onmouseenter = () => { if (!selected) apply(el.dataset.pick); };
    el.onmouseleave = () => { if (!selected) apply(null); };
    el.onfocus = () => { if (!selected) apply(el.dataset.pick); };
    el.onblur = () => { if (!selected) apply(null); };
  });
  clear.onclick = () => { selected = null; apply(null); };
})();
