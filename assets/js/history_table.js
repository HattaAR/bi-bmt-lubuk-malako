// Referensi desain UI. Triggers carry IDs only; guarded Python reads details.
export default function ({parentElement, data, setTriggerValue}) {
  const root = parentElement.querySelector('.ah-table-mount');
  root.innerHTML = data.html;
  const handle = event => {
    const button = event.target.closest('button[data-detail]');
    if (button) setTriggerValue('open', button.dataset.detail);
  };
  root.addEventListener('click', handle);
  return () => root.removeEventListener('click', handle);
}
