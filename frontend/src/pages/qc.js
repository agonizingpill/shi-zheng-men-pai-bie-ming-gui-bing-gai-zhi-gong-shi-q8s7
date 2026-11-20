import{heading,form,input,select,area,badge,plaque}from'../components/registry.js';import{esc}from'../utils/format.js';
const pct=v=>v===null||v===undefined?'—':(v*100).toFixed(1)+'%';
const GROUPS=[['recommended','已推荐'],['unrecommended','未推荐']];
function side(x){return `<div>${plaque(x)}${x.aliases.map(a=>`<p class="evidence">别名「${esc(a.text)}」${a.evidence.map(v=>`<br><small>书证 ${esc(v.reference)}：${esc(v.description)}</small>`).join('')||'<br><small>暂无书证</small>'}</p>`).join('')}</div>`}
function votes(p){return `<table><thead><tr><th>核定员</th><th>判定</th><th>书证依据</th></tr></thead><tbody>${p.votes.map(v=>`<tr><td>${esc(v.adjudicator)}</td><td>${badge(v.verdict)}</td><td>${esc(v.note)}</td></tr>`).join('')}</tbody></table>`}
function pairCard(p,open){
 let panel='';
 if(p.state==='pending')panel=`<p>书证盲审中 · 已交卷 ${p.vote_count}/2 · 判定揭晓前不显示原分与推荐情况</p>`;
 else if(p.state==='arbitration')panel=`<p>两名核定员判定分歧，待未投票的第三人裁决。</p>${votes(p)}`;
 else panel=`<p>最终判定 ${badge(p.verdict)} · 揭晓：原相似度 ${p.similarity.toFixed(3)} · ${p.recommended?'匹配已推荐':'匹配未推荐'} · 抽样权重 ${p.weight.toFixed(3)}</p>${votes(p)}`;
 let ballot=open&&p.state!=='decided'?form('qc-vote-'+p.id,p.state==='arbitration'?'第三人裁决':'凭书证判定同址','/qc/pairs/'+p.id+'/votes',select('verdict','同址判定','<option value="same">同址</option><option value="different">异址</option>')+area('note','书证依据','对照门牌照片与地籍图等书证，说明判定为同址或异址的理由')):'';
 return `<article><h3>${esc(p.street)} ${p.number} 号 · 门牌对 #${p.id} ${badge(p.state)}</h3><div class="qc-pair">${side(p.source)}${side(p.target)}</div>${panel}${ballot}</article>`;
}
function roundCard(q){
 let e=q.estimates,pr=q.progress;
 return `<article><h2>抽查批次 ${esc(q.code)} ${badge(q.state)}</h2><p>参照匹配批次 #${q.run_id} · 抽样比例 ${q.fraction} · 随机种子 ${q.seed} · 框架冻结于 ${esc(q.created)}，重跑匹配不改换样本与分母</p><table><thead><tr><th>街道</th><th>组别</th><th>总体分母</th><th>抽中</th></tr></thead><tbody>${Object.entries(q.frame).map(([street,g])=>GROUPS.filter(([k])=>g[k]).map(([k,label])=>`<tr><td>${esc(street)}</td><td>${label}</td><td>${g[k].population}</td><td>${g[k].sampled}</td></tr>`).join('')).join('')}</tbody></table><table><thead><tr><th>组别</th><th>抽样</th><th>已判定</th><th>待裁决</th><th>待判定</th></tr></thead><tbody>${GROUPS.map(([k,label])=>`<tr><td>${label}</td><td>${pr[k].sampled}</td><td>${pr[k].decided}</td><td>${pr[k].arbitration}</td><td>${pr[k].pending}</td></tr>`).join('')}</tbody></table><table><thead><tr><th>折算指标</th><th>已判定</th><th>按抽中机会折算</th><th>未判完（单列）</th></tr></thead><tbody><tr><td>错合率（已推荐组判异址）</td><td>${e.wrong_merge.decided}/${e.wrong_merge.sampled} 对</td><td>${pct(e.wrong_merge.rate)} · 约合 ${e.wrong_merge.weighted_errors.toFixed(2)}/${e.wrong_merge.population} 对</td><td>${e.wrong_merge.unfinished} 对</td></tr><tr><td>漏合率（未推荐组判同址）</td><td>${e.missed_merge.decided}/${e.missed_merge.sampled} 对</td><td>${pct(e.missed_merge.rate)} · 约合 ${e.missed_merge.weighted_errors.toFixed(2)}/${e.missed_merge.population} 对</td><td>${e.missed_merge.unfinished} 对</td></tr></tbody></table>${q.state==='collecting'?`<button data-action="/qc/rounds/${q.id}/close">封存批次，停止判定</button>`:''}${q.pairs.map(p=>pairCard(p,q.state==='collecting')).join('')}</article>`;
}
export function render(d,qc){
 let rounds=qc?.rounds||[];
 return heading('07','归并质检，漏合也要查。','按街道分层，从已推荐与未推荐的同街同号门牌对中抽样；两名核定员各凭书证盲判同址，判完才揭晓原分与推荐情况；分歧交第三人裁决，按抽中机会折算错合率与漏合率。')+`<div class="split"><section>${rounds.map(roundCard).join('')||'<p>尚无抽查批次。先在归并候选页计算匹配，再由核定员创建质检抽查。</p>'}</section><aside>${form('qc-round-create','创建质检抽查','/qc/rounds',input('code','批次编号','QC-01')+input('fraction','每层抽样比例，0到1之间','0.5','number','step="any"')+input('seed','随机种子','42','number'))}<h3>质检规则</h3><p>抽样框架为创建时全部同街同号门牌对，按街道与推荐情况分层；批次冻结后重跑匹配、增补别名都不改换样本与分母。</p><p>两名核定员各自凭书证盲判，判定揭晓前不显示原相似度与推荐情况；两人分歧由未投票的第三人裁决；同一核定员重复提交不重复计票。</p><p>错合率与漏合率按抽中机会（层总体÷抽中数）折算，未判完的门牌对单列、不计入比率。</p></aside></div>`;
}
