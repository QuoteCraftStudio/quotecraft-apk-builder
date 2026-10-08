'use strict';
const $ = id => document.getElementById(id);
let token = location.hash.slice(1) || sessionStorage.getItem('qc-pairing') || '';
history.replaceState(null, '', location.pathname);
let activeJob = null;
let ready = false;
let polling = false;
async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { Authorization: `Bearer ${token}`, ...(options.headers || {}) } });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.error || `Request failed (${response.status})`);
  }
  return response;
}
async function checkTools() {
  const data = await (await api('/api/tools')).json();
  ready = data.missing.length === 0;
  $('tools').textContent = ready ? 'Build tools are ready.' : 'One-time setup needed:\n' + data.missing.join('\n');
  $('build').disabled = !ready || polling;
}
async function connect() {
  $('error').textContent = '';
  token = $('token').value.trim() || token;
  try {
    await checkTools();
    sessionStorage.setItem('qc-pairing', token);
    $('pair').hidden = true;
    $('builder').hidden = false;
  } catch (e) { $('error').textContent = e.message; }
}
$('connect').onclick = connect;
$('check').onclick = async () => { try { await checkTools(); } catch (e) { $('error').textContent = e.message; } };
function readFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(',')[1]);
    reader.onerror = () => reject(new Error('Could not read the selected file.'));
    reader.readAsDataURL(file);
  });
}
async function poll() {
  try {
    const job = await (await api(`/api/jobs/${activeJob}`)).json();
    $('status').textContent = {queued:'Waiting for build',building:'Building your APK',complete:'Your APK is ready',failed:'Build needs attention'}[job.status];
    $('log').textContent = job.log;
    if (job.status === 'complete' || job.status === 'failed') {
      polling = false;
      $('build').disabled = !ready;
      $('download').hidden = job.status !== 'complete';
      return;
    }
    setTimeout(poll, 2000);
  } catch (e) {
    polling = false;
    $('error').textContent = e.message + '\nReconnect to your Windows builder, then reload this page to resume checking.';
    $('build').disabled = !ready;
  }
}
$('form').onsubmit = async event => {
  event.preventDefault();
  $('error').textContent = '';
  const file = $('file').files[0];
  if (!file || !file.size || file.size > 40 * 1024 * 1024) { $('error').textContent = 'Choose an HTML or ZIP file between 1 byte and 40 MB.'; return; }
  $('build').disabled = true;
  $('download').hidden = true;
  try {
    const fields = { name: $('name').value.trim(), package: $('package').value.trim(), version: Number($('version').value), filename: file.name, data: await readFile(file), microphone: $('microphone').checked, camera: $('camera').checked };
    const job = await (await api('/api/jobs', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(fields)})).json();
    activeJob = job.id;
    sessionStorage.setItem('qc-job', activeJob);
    polling = true;
    $('progress').hidden = false;
    await poll();
  } catch (e) { $('error').textContent = e.message; $('build').disabled = !ready; }
};
$('download').onclick = async () => {
  try {
    const blob = await (await api(`/api/jobs/${activeJob}/apk`)).blob();
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${$('package').value || 'quotecraft-app'}.apk`;
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 30000);
  } catch (e) { $('error').textContent = e.message; }
};
if (token) {
  $('token').value = token;
  connect().then(() => {
    activeJob = sessionStorage.getItem('qc-job');
    if (activeJob && !$('builder').hidden) { $('progress').hidden = false; polling = true; $('build').disabled = true; poll(); }
  });
}
