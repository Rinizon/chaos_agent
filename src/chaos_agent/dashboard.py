"""Small dependency-free operator dashboard served by the authenticated API."""

# Embedded browser assets intentionally use compact lines; Python code remains formatted.
# ruff: noqa: E501

DASHBOARD_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Chaos Agent</title><style>
body{font:16px system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#17202a;background:#f6f8fa}
main{background:white;border:1px solid #d0d7de;border-radius:12px;padding:1.5rem}h1{margin-top:0}
button{padding:.6rem 1rem;border:0;border-radius:6px;background:#0969da;color:#fff;cursor:pointer}button:disabled{opacity:.5}
input,select{padding:.55rem;border:1px solid #8c959f;border-radius:6px}label{margin-right:1rem}
.status{padding:.5rem;background:#ddf4ff;border-radius:6px}table{width:100%;border-collapse:collapse;margin-top:1rem}th,td{text-align:left;padding:.6rem;border-bottom:1px solid #d8dee4}
</style></head><body><main><h1>Chaos Agent</h1><p class="status" id="health">Loading local agent health…</p>
<section><h2>Launch experiment</h2><label>Bearer token <input id="token" type="password" autocomplete="off"></label>
<label>Scenario <select id="scenario"><option>apache-stop</option><option>cpu-pressure</option><option>disk-pressure</option></select></label>
<label>Duration <input id="duration" type="number" min="1" max="900" value="300"></label>
<button id="launch">Launch</button><p id="message" role="status"></p></section>
<section><h2>Experiment history</h2><button id="refresh">Refresh</button><table><thead><tr><th>ID</th><th>Scenario</th><th>State</th><th>Expires</th></tr></thead><tbody id="history"></tbody></table></section>
</main><script>
const token=()=>document.querySelector('#token').value;const auth=()=>({Authorization:'Bearer '+token()});
async function refresh(){let h=await fetch('/health');document.querySelector('#health').textContent='Local API: '+(h.ok?'healthy':'unavailable');if(!token())return;let r=await fetch('/api/v1/experiments',{headers:auth()});if(!r.ok)return;let data=await r.json();document.querySelector('#history').replaceChildren(...data.experiments.map(e=>{let tr=document.createElement('tr');[e.experiment_id,e.scenario,e.state,e.expires_at].forEach(v=>{let td=document.createElement('td');td.textContent=v;tr.append(td)});return tr}));}
document.querySelector('#refresh').onclick=refresh;document.querySelector('#launch').onclick=async()=>{if(!confirm('Schedule this approved experiment?'))return;let r=await fetch('/api/v1/experiments',{method:'POST',headers:{...auth(),'Content-Type':'application/json'},body:JSON.stringify({scenario:document.querySelector('#scenario').value,duration_seconds:Number(document.querySelector('#duration').value)})});document.querySelector('#message').textContent=r.ok?'Experiment scheduled.':'Request refused.';refresh()};refresh();
</script></body></html>"""
