// 质检页渲染冒烟：覆盖待判定/待裁决/已判定三种门牌对与空批次
// 运行：cd frontend && node ../test-artifacts/gb-1036/qc_page_render.mjs
import{render}from'../../frontend/src/pages/qc.js';
const side=id=>({id,code:'CQ-0'+id,street:'长桥路',number:18,label:'长桥路18号正门',lat:31.2,lng:121.4,aliases:[{id:1,text:'长桥路18号正门',evidence:[{reference:'照片-CQ',description:'现场门牌照片与地籍图核验'}]}]});
const fixture={rounds:[
 {id:1,code:'QC-1',run_id:3,seed:42,fraction:0.5,state:'collecting',created:'2026-11-18T09:00:00',
  frame:{'长桥路':{recommended:{population:3,sampled:2}},'河滨路':{unrecommended:{population:1,sampled:1}}},
  progress:{recommended:{sampled:2,decided:1,arbitration:1,pending:0},unrecommended:{sampled:1,decided:0,arbitration:0,pending:1}},
  estimates:{wrong_merge:{population:3,sampled:2,decided:1,unfinished:1,error_pairs:1,weighted_errors:1.5,rate:0.5},missed_merge:{population:1,sampled:1,decided:0,unfinished:1,error_pairs:0,weighted_errors:0,rate:null}},
  pairs:[
   {id:1,street:'长桥路',number:18,state:'decided',verdict:'same',recommended:1,similarity:0.8123,weight:1.5,vote_count:2,source:side(1),target:side(2),votes:[{adjudicator:'s1',verdict:'same',note:'书证一致',created:'t'},{adjudicator:'s2',verdict:'same',note:'同意',created:'t'}]},
   {id:2,street:'长桥路',number:18,state:'arbitration',recommended:1,similarity:0.5,weight:1.5,vote_count:2,source:side(3),target:side(4),votes:[{adjudicator:'s1',verdict:'same',note:'同址',created:'t'},{adjudicator:'s2',verdict:'different',note:'异址',created:'t'}]},
   {id:3,street:'河滨路',number:5,state:'pending',vote_count:1,source:side(5),target:side(6)}]},
 {id:2,code:'QC-2',run_id:3,seed:42,fraction:0.5,state:'closed',created:'t',frame:{},progress:{recommended:{sampled:0,decided:0,arbitration:0,pending:0},unrecommended:{sampled:0,decided:0,arbitration:0,pending:0}},estimates:{wrong_merge:{population:0,sampled:0,decided:0,unfinished:0,error_pairs:0,weighted_errors:0,rate:null},missed_merge:{population:0,sampled:0,decided:0,unfinished:0,error_pairs:0,weighted_errors:0,rate:null}},pairs:[]}]};
const html=render(null,fixture);
for(const s of['抽查批次 QC-1','错合率','漏合率','50.0%','第三人裁决','书证盲审中 · 已交卷 1/2','原相似度 0.812','匹配已推荐','抽样权重 1.500','封存批次','已判定','待裁决','待判定','/qc/pairs/3/votes','/qc/rounds/1/close'])if(!html.includes(s))throw new Error('missing: '+s);
if(html.includes('QC-2</h2>')&&!html.includes('已封存'))throw new Error('closed badge missing');
if(!render(null,{rounds:[]}).includes('尚无抽查批次'))throw new Error('empty state missing');
if(!render(null,null).includes('尚无抽查批次'))throw new Error('null qc missing');
console.log('qc page render OK,',html.length,'bytes');
