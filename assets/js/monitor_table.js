// Referensi desain UI: the official CCv2 trigger opens a guarded, read-only detail.
export default function ({ parentElement, data, setTriggerValue }) {
  const root = parentElement.querySelector('.pm-table-mount');
  root.innerHTML = data.html; // HTML is constructed and escaped by Python.
  root.querySelectorAll('button[data-detail]').forEach(button => {
    button.onclick = () => setTriggerValue('open', button.dataset.detail);
  });
}
