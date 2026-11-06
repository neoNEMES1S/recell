const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(`${__dirname}/implementation.js`, "utf8"), context);
const I = context.ReCellImplementation;
const u = {esc: String, fmt: (x, d=2) => Number(x).toFixed(d),
  title: (...x) => x.join("\n"), panel: (...x) => x.join("\n"),
  note: (...x) => x.join("\n"), kpi: (...x) => x.join(" "),
  select: (...x) => JSON.stringify(x), table: (...x) => JSON.stringify(x),
  chart: (...x) => JSON.stringify(x), bars: x => JSON.stringify(x)};
const r = {
  report: "reports/review.pdf", audit: {windows:333},
  ecm: {
    summary: [{model:"1rc",role:"test",rmse_mv:4.4},{model:"rint",role:"test",rmse_mv:8.182}],
    paths: [{cell_id:"G1",session:"RPT_3",step:10,rows:[[0,.2,3.7,99,99],[1,2,3.6,3.602,3.601]]}],
    parameters: [{cell_id:"G1",model:"1rc",r0_ohm:.03,r1_ohm:.01,tau_s:10}],
    per_cell:[{cell_id:"G1",model:"1rc",role:"test",rmse_mv:4.4},{cell_id:"G1",model:"rint",role:"test",rmse_mv:8.182}],
    primary:{difference:-3.782,low_95:-4.124,high_95:-3.432}},
  selection:{trials:270,summary:[{model:"selected",horizon:1,rmse_pp:.2465,mae_pp:.1921}],
    primary:{difference:.0277,low_95:-.0031,high_95:.0816},selections:[]},
  packages:[{id:"C05",name:"Simscape",status:"waiting_external",implemented:"export",remaining:"not run"}],
  verification:{ecm_rows_checked:175824,ecm_max_replay_difference_v:1e-15,health_rows_checked:2610,validation_trials_checked:270},
  bms:{records:60,quality_failures:0},life:{inventory:[]}
};
const D={implementation:r};
const electrical=I.render(D,u,{implementationTab:"electrical"});
assert.ok(electrical.includes("resistance-only 2.000 mV; one-RC 1.000 mV"), "Exclude the input anchor from the selected-window RMSE");
assert.ok(electrical.includes("not unseen cells"));
const ai=I.render(D,u,{implementationTab:"ai"});
assert.ok(ai.includes("higher mean"));
assert.ok(ai.includes("CPU results are not labelled as DGX evidence"));
const interfaces=I.render(D,u,{implementationTab:"interfaces"});
assert.ok(interfaces.includes("<strong>synthetic</strong>"));
assert.ok(interfaces.includes("Health output is unavailable"));
assert.ok(interfaces.includes("SOL remains undefined"));
assert.ok(I.render(D,u,{implementationTab:"gates"}).includes("full proposal is not yet validated"));
assert.ok(I.brief(D,u).includes("Simscape/DGX execution, real BMS integration, SOL definition"));
assert.equal(I.overview({},u), "");
console.log("Implementation view checks passed: anchor exclusion, adverse result and external evidence labels.");

// Optional integration check against an actual exported snapshot. This executes
// rendering/event code in a tiny DOM fixture; it is not visual browser QA.
if (process.argv[2]) {
  const data = JSON.parse(fs.readFileSync(process.argv[2], "utf8").replace(/^window.RECELL_DATA=/, "").trim().replace(/;$/, ""));
  const nodes = new Map(), events = {}, windowEvents = {};
  const node = id => {
    if (!nodes.has(id)) nodes.set(id, {innerHTML:"",textContent:"",focus(){},showModal(){},close(){},insertAdjacentHTML(_where,html){this.innerHTML+=html;}});
    return nodes.get(id);
  };
  const w={RECELL_DATA:data,addEventListener:(name,fn)=>{windowEvents[name]=fn;},scrollTo(){},print(){}};
  const c=vm.createContext({window:w,location:{hash:"#overview"},localStorage:{getItem:()=>null},
    document:{activeElement:null,getElementById:node,querySelectorAll:()=>[],addEventListener:(name,fn)=>{events[name]=fn;}}});
  for (const name of ["core.js","lessons.js","research.js","implementation.js","app.js"])
    vm.runInContext(fs.readFileSync(`${__dirname}/${name}`,"utf8"),c);
  for (const hash of ["overview","batteries","forecasts","dispatch","learn","pilot",
    "research/transfer","research/calendar","research/india","research/controller",
    "implementation/electrical","implementation/ai","implementation/gates","implementation/interfaces"]) {
    c.location.hash=`#${hash}`; windowEvents.hashchange();
    assert.ok(node("content").innerHTML.includes("<h1>"),hash);
    assert.ok(!/\bNaN\b|\bInfinity\b|[>=]undefined[<"]/.test(node("content").innerHTML),hash);
  }
  c.location.hash="#implementation/electrical";windowEvents.hashchange();
  events.change({target:{dataset:{state:"ecmSession"},value:"RPT_19"}});
  events.change({target:{dataset:{state:"ecmCell"},value:"W9"}});
  assert.ok(node("content").innerHTML.includes("W9 · RPT_3"),"Unavailable diagnostic falls back without mixing cells");
  const click=action=>events.click({target:{closest:selector=>selector==="[data-action]"?{dataset:{action}}:null}});
  click("sources");assert.ok(node("source-content").innerHTML.includes("Model implementation evidence"));
  click("print");assert.ok(node("print-report").innerHTML.includes("New mathematical-model implementation"));
  assert.equal(w.RECELL_LESSONS.length,18);
  console.log("Exported-snapshot integration checks passed: all 14 routes, W9 fallback, sources, print and 18 lessons.");
}
