// Trusted local referensi desain UI interactions, scoped to this snapshot only.
(() => {
  const root = document.querySelector('.qp-root');
  if (!root) return;
  let selected = null;
  const clear = root.querySelector('.qp-clear');
  const apply = code => {
    root.querySelectorAll('.qp-stacked [data-category],.qp-legend-row').forEach(el => {
      el.dataset.dimmed = !!code && el.dataset.category !== code;
    });
    root.querySelectorAll('.qp-detail-row').forEach(el => {
      el.dataset.highlight = !!code && el.dataset.category === code;
    });
    root.querySelectorAll('[data-pick]').forEach(el => {
      el.setAttribute('aria-pressed', String(!!selected && el.dataset.pick === selected));
    });
    clear.hidden = !selected;
  };
  root.querySelectorAll('[data-pick]').forEach(el => {
    el.onclick = () => { selected = selected === el.dataset.pick ? null : el.dataset.pick; apply(selected); };
    el.onmouseenter = () => { if (!selected) apply(el.dataset.pick); };
    el.onmouseleave = () => { if (!selected) apply(null); };
    el.onfocus = () => { if (!selected) apply(el.dataset.pick); };
    el.onblur = () => { if (!selected) apply(null); };
  });
  clear.onclick = () => { selected = null; apply(null); };
})();
