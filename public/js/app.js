let allData = [];
let sortKey = null, sortAsc = true;
let filterRules = [];
let _lastFiltered = [];
let _lastVCols = [];
let _useVirtual = false;
let _selectedPreset = localStorage.getItem('etf_selected_preset') || '';
let _cachedDataDate = '';
let huijinOverview = null;
let cffexPositionRank = [];
let huijinBacktest = null;
let _hjwSortKey = 'share_change_ratio_5d';
let _hjwSortAsc = false;
let _hjwFilter = 'all';

const ALL_COLS = [
  {key:'交易所', label:'所', group:'基础', def:true, srt:true},
  {key:'代码', label:'代码', group:'基础', def:true, srt:true},
  {key:'名称', label:'名称', group:'基础', def:true, srt:true},
  {key:'日期', label:'日期', group:'基础', def:false, srt:true},
  {key:'总份额_亿', label:'总份额(亿)', group:'份额', def:true, srt:true},
  {key:'份额日改变', label:'日改变(万)', group:'份额', def:true, srt:true, tip:'万份/减前一交易日'},
  {key:'份额日改变比例', label:'日改变%', group:'份额', def:false, srt:true},
  {key:'份额周改变', label:'周改变(万)', group:'份额', def:true, srt:true, tip:'万份/减约5日前'},
  {key:'份额周改变比例', label:'周改变%', group:'份额', def:false, srt:true},
  {key:'份额月改变', label:'月改变(万)', group:'份额', def:false, srt:true, tip:'万份/减约20日前'},
  {key:'份额月改变比例', label:'月改变%', group:'份额', def:false, srt:true},
  {key:'最新价', label:'最新价', group:'行情', def:true, srt:true},
  {key:'涨跌幅', label:'日涨跌', group:'行情', def:true, srt:true},
  {key:'周涨跌幅', label:'周涨跌', group:'行情', def:false, srt:true},
  {key:'月涨跌幅', label:'月涨跌', group:'行情', def:false, srt:true},
  {key:'成交额_万', label:'成交额(万)', group:'行情', def:true, srt:true},
  {key:'IOPV', label:'IOPV', group:'行情', def:true, srt:true, tip:'实时参考净值'},
  {key:'基金折价率', label:'IOPV溢价率', group:'行情', def:true, srt:true, tip:'现价对IOPV的溢价率'},
  {key:'规模_亿', label:'规模(亿)', group:'规模', def:true, srt:true},
  {key:'规模日改变_亿', label:'规模变化(亿)', group:'规模', def:true, srt:true},
  {key:'净值', label:'净值', group:'净值', def:true, srt:true},
  {key:'净值日期', label:'净值日期', group:'净值', def:false, srt:true},
  {key:'净值溢价率', label:'净值溢价率', group:'净值', def:false, srt:true},
  {key:'市盈率PE', label:'PE', group:'估值', def:false, srt:true, tip:'指数市盈率'},
  {key:'市净率PB', label:'PB', group:'估值', def:false, srt:true, tip:'指数市净率'},
  {key:'PE历史分位', label:'PE分位', group:'估值', def:true, srt:true, tip:'PE历史百分位(<20%低估)'},
  {key:'PB历史分位', label:'PB分位', group:'估值', def:true, srt:true, tip:'PB历史百分位(<20%低估)'},
  {key:'跟踪指数', label:'跟踪指数', group:'其他', def:true, srt:true, tip:'跟踪的指数名称'},
  {key:'指数涨跌幅', label:'指数涨跌', group:'其他', def:true, srt:true},
  {key:'基金公司', label:'基金公司', group:'其他', def:false, srt:true},
  {key:'汇金持股_亿', label:'汇金披露(亿份)', group:'其他', def:false, srt:true, tip:'报告期汇金披露持仓份额，非实时'},
  {key:'比汇金改变比', label:'份额变动强度', group:'其他', def:true, srt:true, tip:'份额改变额÷汇金披露线索份额，仅作公开份额观察'},
  {key:'机构持仓占比', label:'机构占比%', group:'机构', def:false, srt:true, tip:'机构投资者持有比例'},
  {key:'融资余额_亿', label:'融资(亿)', group:'两融', def:false, srt:true, tip:'融资余额'},
  {key:'融资净买入_亿', label:'融资净买(亿)', group:'两融', def:true, srt:true, tip:'融资净买入额'},
  {key:'认购IV', label:'波动率IV', group:'期权', def:false, srt:true, tip:'期权隐含波动率指数(QVIX收盘)'},
  {key:'认沽IV', label:'IV最高', group:'期权', def:false, srt:true, tip:'日内波动率最高值'},
  {key:'PCR成交量比', label:'PCR量比', group:'期权', def:false, srt:true, tip:'看跌/看涨成交量比(>1偏空)'},
];

let visibleKeys = new Set();
function initVisibleCols(){
  const saved = localStorage.getItem('etf_visible_cols');
  if(saved) {
    try {
      const arr = JSON.parse(saved);
      if(arr && arr.length) { arr.forEach(k=>visibleKeys.add(k)); return; }
    } catch(e) {}
  }
  ALL_COLS.forEach(c=>{if(c.def) visibleKeys.add(c.key);});
}
initVisibleCols();
function getVisibleCols(){return ALL_COLS.filter(c=>visibleKeys.has(c.key));}

function _na(){return '<span class="na">--</span>';}
function esc(v){
  return String(v ?? '').replace(/[&<>"']/g, ch=>({
    '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'
  }[ch]));
}
function num(v){
  if(v===null||v===undefined||v==='')return null;
  const n=Number(v);
  return Number.isFinite(n)?n:null;
}
function fmt(v, d=2){const n=num(v);return n===null?_na():n.toFixed(d);}
function fmtChg(v){
  const n=num(v);
  if(n===null)return _na();
  if(Math.abs(n)<0.05)return '<span class="na">0</span>';
  const cls=n>0?'pos':'neg';
  return `<span class="${cls}">${n>0?'+':''}${n.toFixed(1)}</span>`;
}
function fmtChg2(v){
  const n=num(v);
  if(n===null)return _na();
  if(Math.abs(n)<0.005)return '<span class="na">0</span>';
  const cls=n>0?'pos':'neg';
  return `<span class="${cls}">${n>0?'+':''}${n.toFixed(2)}</span>`;
}
function fmtPct(v){
  const n=num(v);
  if(n===null)return _na();
  if(Math.abs(n)<0.005)return '<span class="na">0.00%</span>';
  const cls=n>=0?'pos':'neg';
  return `<span class="${cls}">${n>=0?'+':''}${n.toFixed(2)}%</span>`;
}
function fmtPrice(v){const n=num(v);return n===null?_na():n.toFixed(3);}
function fmtHj(v){
  const n=num(v);
  if(n===null)return _na();
  if(Math.abs(n)<0.0005)return '<span class="na">0</span>';
  const cls=n>0?'pos':'neg';
  return `<span class="${cls}">${n>0?'+':''}${n.toFixed(3)}%</span>`;
}
function fmtRatio(v){
  const n=num(v);
  return n===null?_na():(n*100).toFixed(2)+'%';
}
function fmtStr(v){
  if(v===null||v===undefined||v==='')return _na();
  return `<span class="muted">${esc(v)}</span>`;
}

const NUM_COLS = new Set([
  '总份额_亿','份额日改变','份额日改变比例','份额周改变','份额周改变比例',
  '份额月改变','份额月改变比例','最新价','涨跌幅','周涨跌幅','月涨跌幅',
  '成交额_万','IOPV','基金折价率','规模_亿','规模日改变_亿','净值',
  '净值溢价率','指数涨跌幅','汇金持股_亿','比汇金改变比',
  '机构持仓占比','认购IV','认沽IV','PCR成交量比',
  '市盈率PE','市净率PB','PE历史分位','PB历史分位',
  '融资余额_亿','融资净买入_亿'
]);
function cellClass(col){
  const classes = [`col-${col.key.replace(/[^\w\u4e00-\u9fa5]/g,'-')}`];
  if(NUM_COLS.has(col.key)) classes.push('cell-num');
  if(col.key==='交易所') classes.push('cell-center cell-exchange');
  if(col.key==='代码') classes.push('cell-code');
  if(col.key==='名称') classes.push('cell-name');
  return classes.join(' ');
}

const RENDER = {
  '交易所': (d)=>`<span class="${d.交易所==='沪'?'badge-sse':'badge-szse'}">${esc(d.交易所)}</span>`,
  '代码': (d)=>`<span class="code">${esc(d.代码)}</span>`,
  '名称': (d)=>`<span class="name" title="${esc(d.名称)}">${esc(d.名称)}${d.汇金持股_亿!==null&&d.汇金持股_亿!==undefined?`<span class="hj-mark" title="汇金披露线索${esc(d.汇金持股_亿)}亿">◆</span>`:''}</span>`,
  '日期': (d)=>`<span class="muted small">${esc(d.日期)}</span>`,
  '总份额_亿': (d)=>`<span class="num">${fmt(d.总份额_亿,2)}</span>`,
  '份额日改变': (d)=>`<span class="num">${fmtChg(d.份额日改变)}</span>`,
  '份额日改变比例': (d)=>`<span class="num" style="font-size:12px">${fmtPct(d.份额日改变比例)}</span>`,
  '份额周改变': (d)=>`<span class="num">${fmtChg(d.份额周改变)}</span>`,
  '份额周改变比例': (d)=>`<span class="num" style="font-size:12px">${fmtPct(d.份额周改变比例)}</span>`,
  '份额月改变': (d)=>`<span class="num">${fmtChg(d.份额月改变)}</span>`,
  '份额月改变比例': (d)=>`<span class="num" style="font-size:12px">${fmtPct(d.份额月改变比例)}</span>`,
  '最新价': (d)=>`<span class="num">${fmtPrice(d.最新价)}</span>`,
  '涨跌幅': (d)=>`<span class="num">${fmtPct(d.涨跌幅)}</span>`,
  '周涨跌幅': (d)=>`<span class="num">${fmtPct(d.周涨跌幅)}</span>`,
  '月涨跌幅': (d)=>`<span class="num">${fmtPct(d.月涨跌幅)}</span>`,
  '成交额_万': (d)=>`<span class="num">${fmt(d.成交额_万,0)}</span>`,
  'IOPV': (d)=>`<span class="num">${fmtPrice(d.IOPV)}</span>`,
  '基金折价率': (d)=>`<span class="num">${fmtPct(d.基金折价率)}</span>`,
  '规模_亿': (d)=>`<span class="num">${fmt(d.规模_亿,2)}</span>`,
  '规模日改变_亿': (d)=>`<span class="num">${fmtChg2(d.规模日改变_亿)}</span>`,
  '净值': (d)=>`<span class="num">${fmtPrice(d.净值)}</span>`,
  '净值日期': (d)=>fmtStr(d.净值日期),
  '净值溢价率': (d)=>`<span class="num">${fmtPct(d.净值溢价率)}</span>`,
  '基金公司': (d)=>fmtStr(d.基金公司),
  '跟踪指数': (d)=>fmtStr(d.跟踪指数),
  '指数涨跌幅': (d)=>`<span class="num">${fmtPct(d.指数涨跌幅)}</span>`,
  '汇金持股_亿': (d)=>`<span class="num">${fmt(d.汇金持股_亿,2)}</span>`,
  '比汇金改变比': (d)=>`<span class="num">${fmtHj(d.比汇金改变比)}</span>`,
  '机构持仓占比': (d)=>`<span class="num">${d.机构持仓占比!=null?fmt(d.机构持仓占比,1)+'%':_na()}</span>`,
  '认购IV': (d)=>`<span class="num">${d.认购IV!=null?fmt(d.认购IV,1)+'%':_na()}</span>`,
  '认沽IV': (d)=>`<span class="num">${d.认沽IV!=null?fmt(d.认沽IV,1)+'%':_na()}</span>`,
  'PCR成交量比': (d)=>`<span class="num">${d.PCR成交量比!=null?fmt(d.PCR成交量比,2):_na()}</span>`,
};

// ====== Advanced Filter ======
const FILTER_OPS = [
  {key:'>=', label:'≥', num:true, str:false},
  {key:'<=', label:'≤', num:true, str:false},
  {key:'>', label:'>', num:true, str:false},
  {key:'<', label:'<', num:true, str:false},
  {key:'==', label:'=', num:true, str:true},
  {key:'!=', label:'≠', num:true, str:true},
  {key:'between', label:'区间', num:true, str:false},
  {key:'contains', label:'包含', num:false, str:true},
  {key:'!contains', label:'不包含', num:false, str:true},
  {key:'null', label:'为空', num:true, str:true},
  {key:'!null', label:'非空', num:true, str:true},
];

function evaluateRule(d, rule) {
  const val = d[rule.field];
  const cmp = rule.value;
  switch(rule.op) {
    case '>': return val !== null && val !== undefined && val !== '' && Number(val) > Number(cmp);
    case '>=': return val !== null && val !== undefined && val !== '' && Number(val) >= Number(cmp);
    case '<': return val !== null && val !== undefined && val !== '' && Number(val) < Number(cmp);
    case '<=': return val !== null && val !== undefined && val !== '' && Number(val) <= Number(cmp);
    case '==': return String(val ?? '') === String(cmp);
    case '!=': return String(val ?? '') !== String(cmp);
    case 'contains': return String(val ?? '').includes(String(cmp));
    case '!contains': return !String(val ?? '').includes(String(cmp));
    case 'between':
      if (!Array.isArray(cmp)) return false;
      if(val === null || val === undefined || val === '') return false;
      return Number(val) >= Number(cmp?.[0] ?? -Infinity) &&
             Number(val) <= Number(cmp?.[1] ?? Infinity);
    case 'null': return val === null || val === undefined || val === '';
    case '!null': return val !== null && val !== undefined && val !== '';
    default: return true;
  }
}

function matchAllRules(d) {
  if (!filterRules.length) return true;
  let ok = evaluateRule(d, filterRules[0]);
  for (let i = 1; i < filterRules.length; i++) {
    ok = filterRules[i].logic === 'AND'
      ? (ok && evaluateRule(d, filterRules[i]))
      : (ok || evaluateRule(d, filterRules[i]));
  }
  return ok;
}

const PRESET_CATEGORIES = [
  {label:'🏆 质量分层', keys:['核心配置池','优选候选池','初筛候选池']},
  {label:'📊 大类聚焦', keys:['宽基风格精选','行业ETF候选','债券ETF候选','跨境ETF候选']},
  {label:'⚡ 信号监测', keys:['折价博弈(<-1.5%)','溢价预警(>1.5%)','资金持续流入','大额赎回预警','放量下跌异动','规模激增异动','份额变动强度']},
  {label:'📈 资金/估值', keys:['量价背离','恐慌抄底','杠杆看多','汇金 ETF 份额观察','估值低位','估值高位']},
];

const FILTER_PRESETS = {
  '核心配置池': [
    {logic:'AND', field:'规模_亿', op:'>=', value:'50'},
    {logic:'AND', field:'成交额_万', op:'>=', value:'20000'},
    {logic:'AND', field:'净值溢价率', op:'between', value:['-0.5','0.5']}
  ],
  '优选候选池': [
    {logic:'AND', field:'规模_亿', op:'>=', value:'10'},
    {logic:'AND', field:'成交额_万', op:'>=', value:'5000'},
    {logic:'AND', field:'净值溢价率', op:'between', value:['-1','1']}
  ],
  '初筛候选池': [
    {logic:'AND', field:'规模_亿', op:'>=', value:'2'},
    {logic:'AND', field:'成交额_万', op:'>=', value:'1000'}
  ],
  '宽基风格精选': [
    {logic:'AND', field:'跟踪指数', op:'contains', value:'沪深300'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'中证A500'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'中证A50'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'上证50'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'上证180'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'中证500'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'中证1000'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'中证2000'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'科创50'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'科创100'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'创业板'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'中证800'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'中证红利'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'红利低波'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'深证100'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'MSCI中国'},
    {logic:'AND', field:'规模_亿', op:'>=', value:'10'},
    {logic:'AND', field:'成交额_万', op:'>=', value:'5000'},
    {logic:'AND', field:'净值溢价率', op:'between', value:['-1','1']}
  ],
  '行业ETF候选': [
    {logic:'AND', field:'跟踪指数', op:'contains', value:'半导体'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'芯片'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'人工智能'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'机器人'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'军工'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'医药'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'医疗'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'创新药'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'新能源'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'光伏'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'电池'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'消费'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'食品'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'酒'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'银行'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'证券'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'保险'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'传媒'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'通信'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'计算机'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'软件'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'汽车'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'化工'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'有色'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'煤炭'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'钢铁'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'农业'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'电力'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'家电'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'中药'},
    {logic:'AND', field:'规模_亿', op:'>=', value:'5'},
    {logic:'AND', field:'成交额_万', op:'>=', value:'3000'}
  ],
  '债券ETF候选': [
    {logic:'AND', field:'跟踪指数', op:'contains', value:'国债'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'国开'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'地债'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'信用债'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'短融'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'可转债'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'公司债'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'城投债'},
    {logic:'AND', field:'规模_亿', op:'>=', value:'2'},
    {logic:'AND', field:'成交额_万', op:'>=', value:'1000'}
  ],
  '跨境ETF候选': [
    {logic:'AND', field:'跟踪指数', op:'contains', value:'恒生'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'港股通'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'纳斯达克'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'标普'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'日经'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'DAX'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'CAC'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'富时'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'印度'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'越南'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'东南亚'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'海外中国'},
    {logic:'OR', field:'跟踪指数', op:'contains', value:'韩交所'},
    {logic:'AND', field:'规模_亿', op:'>=', value:'2'},
    {logic:'AND', field:'成交额_万', op:'>=', value:'1000'}
  ],
  '折价博弈(<-1.5%)': [
    {logic:'AND', field:'净值溢价率', op:'<=', value:'-1.5'},
    {logic:'AND', field:'规模_亿', op:'>=', value:'5'},
    {logic:'AND', field:'成交额_万', op:'>=', value:'5000'}
  ],
  '溢价预警(>1.5%)': [
    {logic:'AND', field:'净值溢价率', op:'>=', value:'1.5'},
    {logic:'AND', field:'最新价', op:'!null', value:''}
  ],
  '资金持续流入': [
    {logic:'AND', field:'份额周改变', op:'>', value:'0'},
    {logic:'AND', field:'份额月改变', op:'>', value:'0'},
    {logic:'AND', field:'成交额_万', op:'>', value:'0'}
  ],
  '放量下跌异动': [
    {logic:'AND', field:'涨跌幅', op:'<=', value:'-2'},
    {logic:'AND', field:'成交额_万', op:'>=', value:'10000'},
    {logic:'AND', field:'规模_亿', op:'>=', value:'5'}
  ],
  '份额变动强度': [
    {logic:'AND', field:'汇金持股_亿', op:'>', value:'0'},
    {logic:'AND', field:'比汇金改变比', op:'!=', value:'0'}
  ],
  '大额赎回预警': [
    {logic:'AND', field:'份额日改变', op:'<=', value:'-500'},
    {logic:'AND', field:'规模_亿', op:'>=', value:'10'},
    {logic:'AND', field:'成交额_万', op:'>=', value:'5000'}
  ],
  '规模激增异动': [
    {logic:'AND', field:'份额周改变', op:'>=', value:'5000'},
    {logic:'AND', field:'规模_亿', op:'>=', value:'5'},
    {logic:'AND', field:'成交额_万', op:'>', value:'0'}
  ],
  '量价背离': [
    {logic:'AND', field:'份额周改变', op:'>', value:'0'},
    {logic:'AND', field:'周涨跌幅', op:'<', value:'-3'},
    {logic:'AND', field:'成交额_万', op:'>=', value:'5000'}
  ],
  '恐慌抄底': [
    {logic:'AND', field:'PCR成交量比', op:'>', value:'1.2'},
    {logic:'AND', field:'份额日改变', op:'>', value:'0'},
    {logic:'AND', field:'涨跌幅', op:'<', value:'-2'}
  ],
  '杠杆看多': [
    {logic:'AND', field:'融资净买入_亿', op:'>', value:'0'},
    {logic:'AND', field:'份额日改变', op:'>', value:'0'}
  ],
  '汇金 ETF 份额观察': [
    {logic:'AND', field:'比汇金改变比', op:'>', value:'0.1'},
    {logic:'AND', field:'机构持仓占比', op:'>', value:'30'}
  ],
  '估值低位': [
    {logic:'AND', field:'PE历史分位', op:'>', value:'0'},
    {logic:'AND', field:'PE历史分位', op:'<', value:'20'}
  ],
  '估值高位': [
    {logic:'AND', field:'PE历史分位', op:'>', value:'80'}
  ],
};

function saveFilterRules() {
  localStorage.setItem('etf_filter_rules', JSON.stringify(filterRules));
}
function loadFilterRules() {
  try {
    const saved = localStorage.getItem('etf_filter_rules');
    if (saved) filterRules = JSON.parse(saved);
  } catch(e) {}
}
loadFilterRules();

// ====== Render ======
function render(data) {
  if(data) { allData = data; _cachedDataDate = _getMaxDate(); }
  const q = (document.getElementById('searchInput').value||'').trim().toLowerCase();
  const exch = document.getElementById('exchangeFilter').value;

  let f = allData;
  if(q) f = f.filter(d => String(d.代码||'').toLowerCase().includes(q) || String(d.名称||'').toLowerCase().includes(q));
  if(exch) f = f.filter(d => d.交易所 === exch);
  if(filterRules.length) f = f.filter(matchAllRules);

  if(sortKey) {
    f = [...f].sort((a,b)=>{
      let va=a[sortKey],vb=b[sortKey];
      if(va===null||va===undefined)va=-Infinity;
      if(vb===null||vb===undefined)vb=-Infinity;
      if(typeof va==='string')return sortAsc?va.localeCompare(vb):vb.localeCompare(va);
      return sortAsc?va-vb:vb-va;
    });
  }

  const total = f.length;
  const wc = f.filter(d=>d.份额日改变!==null);
  const pos = wc.filter(d=>d.份额日改变>0).length;
  const neg = wc.filter(d=>d.份额日改变<0).length;
  const net = wc.reduce((s,d)=>s+(d.份额日改变||0),0);
  const hjCnt = f.filter(d=>d.汇金持股_亿!==null).length;
  document.getElementById('statsBar').innerHTML =
    `<span class="stat">显示 <b>${total}</b> 只ETF</span>`+
    `<span class="stat"><span class="pos">⬆ ${pos}</span> / <span class="neg">⬇ ${neg}</span></span>`+
    `<span class="stat">净份额变动: <b class="${net>=0?'pos':'neg'}">${net>=0?'+':''}${(net/1e4).toFixed(2)}</b>亿</span>`+
    `<span class="stat">汇金线索: <b>${hjCnt}</b> 只</span>`;

  const visible = getVisibleCols();
  const colCount = Math.max(1, visible.length);
  if(!f.length) {
    document.getElementById('tbody').innerHTML = '<tr><td colspan="'+colCount+'" style="text-align:center;padding:40px;color:#5a5a7a">无匹配数据</td></tr>';
    document.getElementById('updateTime').textContent = '更新: '+new Date().toLocaleString();
    return;
  }

  const vCols = visible.map(c => ({
    cls: cellClass(c),
    fn: RENDER[c.key],
    tip: c.tip ? `<span class="tooltip" data-tip="${esc(c.tip)}">${esc(c.label)}</span>` : esc(c.label),
    key: c.key,
    srtCls: sortKey === c.key ? (sortAsc ? ' asc' : ' desc') : ''
  }));

  // Header
  let headHtml = '<tr>';
  for (let i = 0; i < vCols.length; i++) {
    const c = vCols[i];
    headHtml += `<th class="th-srt${c.srtCls} ${c.cls}" data-key="${esc(c.key)}">${c.tip}</th>`;
  }
  headHtml += '</tr>';
  document.querySelector('#table-head').innerHTML = headHtml;

  _lastFiltered = f;
  _lastVCols = vCols;

  // Body
  const wrap = document.querySelector('.table-wrap');
  if (f.length > 500) {
    _useVirtual = true;
    wrap.scrollTop = 0;
    renderVirtualChunk(f, vCols);
    if (!wrap._scrollBound) {
      wrap.addEventListener('scroll', onVirtualScroll);
      wrap._scrollBound = true;
    }
  } else {
    _useVirtual = false;
    wrap.scrollTop = 0;
    renderFull(f, vCols);
  }

  // Data date (cached, computed only on data load)
  document.getElementById('updateTime').textContent =
    (_cachedDataDate ? '数据:'+_cachedDataDate+' | ' : '')+'更新: '+new Date().toLocaleString();

  // Sort handlers
  document.querySelectorAll('.th-srt').forEach(th=>{
    th.addEventListener('click', ()=>{
      const key = th.dataset.key;
      if(sortKey===key) sortAsc=!sortAsc;
      else { sortKey=key; sortAsc=false; }
      render();
    });
  });

  updateFilterBadge();
}

function _getMaxDate() {
  let m = '';
  for (let i = 0; i < allData.length; i++) {
    const d = allData[i];
    if (d.最新价 != null && d.日期 > m) m = d.日期;
  }
  if (!m) {
    for (let i = 0; i < allData.length; i++) {
      const dt = allData[i].日期;
      if (dt > m) m = dt;
    }
  }
  if (m) return m.slice(0,4)+'-'+m.slice(4,6)+'-'+m.slice(6,8);
  return '';
}

function renderFull(f, vCols) {
  const parts = [];
  for (let i = 0; i < f.length; i++) {
    const d = f[i];
    parts.push('<tr data-code="' + escAttr(d['代码']) + '">');
    for (let j = 0; j < vCols.length; j++) {
      const c = vCols[j];
      parts.push(`<td class="${c.cls}">${c.fn ? c.fn(d) : _na()}</td>`);
    }
    parts.push('</tr>');
  }
  document.getElementById('tbody').innerHTML = parts.join('');
}

function getRowHeight() {
  const w = window.innerWidth;
  return w <= 480 ? 28 : w <= 900 ? 30 : 31;
}
const SCROLL_BUF = 12;

function renderVirtualChunk(f, vCols) {
  const wrap = document.querySelector('.table-wrap');
  const st = wrap.scrollTop;
  const vh = wrap.clientHeight;
  const ROW_H = getRowHeight();
  const startRow = Math.max(0, Math.floor(st / ROW_H) - SCROLL_BUF);
  const endRow = Math.min(f.length, startRow + Math.ceil(vh / ROW_H) + 2 * SCROLL_BUF);
  const topPad = startRow * ROW_H;
  const botPad = (f.length - endRow) * ROW_H;
  const colSpan = vCols.length;

  let parts = [];
  if (topPad > 0) {
    parts.push(`<tr style="height:${topPad}px;pointer-events:none"><td colspan="${colSpan}" style="border:none;padding:0"></td></tr>`);
  }
  for (let i = startRow; i < endRow; i++) {
    const d = f[i];
    parts.push('<tr data-code="' + escAttr(d['代码']) + '">');
    for (let j = 0; j < colSpan; j++) {
      const c = vCols[j];
      parts.push(`<td class="${c.cls}">${c.fn ? c.fn(d) : _na()}</td>`);
    }
    parts.push('</tr>');
  }
  if (botPad > 0) {
    parts.push(`<tr style="height:${botPad}px;pointer-events:none"><td colspan="${colSpan}" style="border:none;padding:0"></td></tr>`);
  }
  document.getElementById('tbody').innerHTML = parts.join('');
}

let _scrollTimer;
function onVirtualScroll() {
  if (!_useVirtual) return;
  clearTimeout(_scrollTimer);
  _scrollTimer = setTimeout(() => renderVirtualChunk(_lastFiltered, _lastVCols), 30);
}

// ====== Filter Panel UI ======
function updateFilterBadge() {
  const btn = document.getElementById('filterToggleBtn');
  if (!btn) return;
  const cnt = filterRules.length;
  btn.textContent = `条件选基${cnt ? '('+cnt+')' : ''}`;
  btn.classList.toggle('has-rules', cnt > 0);
}

function renderFilterPanel() {
  const panel = document.getElementById('filterPanel');
  let html = '';

  // Header bar (mobile)
  html += '<div class="fp-header"><span class="fp-header-title">条件选基</span><button class="fp-close" id="fpCloseBtn" title="关闭">✕</button></div>';

  if (!filterRules.length) {
    html += '<div class="fp-empty">暂无筛选条件，点击下方添加</div>';
  } else {
    html += '<div class="fp-grid">';
    filterRules.forEach((r, i) => {
      const isNum = NUM_COLS.has(r.field);
      const ops = FILTER_OPS.filter(o => (isNum && o.num) || (!isNum && o.str));
      html += `<div class="fp-cell" data-idx="${i}">`;
      if (i > 0) {
        html += `<select class="fp-logic" data-idx="${i}"><option value="AND"${r.logic==='AND'?' selected':''}>且</option><option value="OR"${r.logic==='OR'?' selected':''}>或</option></select>`;
      } else {
        html += '<span class="fp-logic-label">条件</span>';
      }
      html += `<select class="fp-field" data-idx="${i}">`;
      ALL_COLS.forEach(c => {
        html += `<option value="${esc(c.key)}"${r.field===c.key?' selected':''}>${esc(c.label)}</option>`;
      });
      html += '</select>';
      html += `<select class="fp-op" data-idx="${i}">`;
      ops.forEach(o => {
        html += `<option value="${o.key}"${r.op===o.key?' selected':''}>${o.label}</option>`;
      });
      html += '</select>';
      if (r.op === 'between') {
        html += `<input class="fp-val fp-val-from" data-idx="${i}" value="${esc(r.value?.[0]??'')}" placeholder="最小">`;
        html += `<span class="fp-sep">~</span>`;
        html += `<input class="fp-val fp-val-to" data-idx="${i}" value="${esc(r.value?.[1]??'')}" placeholder="最大">`;
      } else if (r.op !== 'null' && r.op !== '!null') {
        html += `<input class="fp-val" data-idx="${i}" value="${esc(r.value??'')}" placeholder="值">`;
      }
      html += `<button class="fp-del" data-idx="${i}" title="删除">✕</button>`;
      html += '</div>';
    });
    html += '</div>';
  }

  html += '<div class="fp-actions">';
  html += `<button class="btn-sm" id="fpAddBtn">+ 添加条件</button>`;
  html += `<select class="fp-preset" id="fpPresetSel"><option value="">— 预设方案 —</option>`;
  for (const cat of PRESET_CATEGORIES) {
    html += `<optgroup label="${esc(cat.label)}">`;
    for (const name of cat.keys) {
      html += `<option value="${esc(name)}">${esc(name)}</option>`;
    }
    html += '</optgroup>';
  }
  const saved = localStorage.getItem('etf_filter_presets');
  if (saved) {
    try {
      const presets = JSON.parse(saved);
      if (Object.keys(presets).length) {
        html += `<optgroup label="📌 自定义预设">`;
        for (const name of Object.keys(presets)) {
          html += `<option value="p:${esc(name)}">${esc(name)}</option>`;
        }
        html += '</optgroup>';
      }
    } catch(e) {}
  }
  html += '</select>';
  html += `<button class="btn-sm" id="fpSaveBtn" title="保存当前条件为自定义预设">保存</button>`;
  if (filterRules.length) html += `<button class="btn-sm" id="fpClearBtn">清空</button>`;
  html += '</div>';

  panel.innerHTML = html;

  // Bind events
  panel.querySelectorAll('.fp-logic').forEach(sel => {
    sel.addEventListener('change', () => {
      filterRules[+sel.dataset.idx].logic = sel.value;
      saveFilterRules(); render();
    });
  });
  panel.querySelectorAll('.fp-field').forEach(sel => {
    sel.addEventListener('change', () => {
      const i = +sel.dataset.idx;
      filterRules[i].field = sel.value;
      filterRules[i].op = NUM_COLS.has(sel.value) ? '>=' : 'contains';
      filterRules[i].value = '';
      _selectedPreset = ''; localStorage.removeItem('etf_selected_preset'); saveFilterRules(); renderFilterPanel(); render();
    });
  });
  panel.querySelectorAll('.fp-op').forEach(sel => {
    sel.addEventListener('change', () => {
      const i = +sel.dataset.idx;
      filterRules[i].op = sel.value;
      if (sel.value === 'null' || sel.value === '!null') filterRules[i].value = '';
      else if (sel.value === 'between') filterRules[i].value = ['', ''];
      else if (typeof filterRules[i].value === 'object') filterRules[i].value = '';
      _selectedPreset = ''; localStorage.removeItem('etf_selected_preset'); saveFilterRules(); renderFilterPanel(); render();
    });
  });
  panel.querySelectorAll('.fp-val').forEach(inp => {
    inp.addEventListener('input', () => {
      const i = +inp.dataset.idx;
      const r = filterRules[i];
      if (r.op === 'between') {
        if (!Array.isArray(r.value)) r.value = ['', ''];
        r.value[inp.classList.contains('fp-val-from') ? 0 : 1] = inp.value;
      } else {
        r.value = inp.value;
      }
    });
    inp.addEventListener('change', () => { saveFilterRules(); render(); });
  });
  panel.querySelectorAll('.fp-del').forEach(btn => {
    btn.addEventListener('click', () => {
      filterRules.splice(+btn.dataset.idx, 1);
      _selectedPreset = ''; localStorage.removeItem('etf_selected_preset'); saveFilterRules(); renderFilterPanel(); render();
    });
  });
  const addBtn = document.getElementById('fpAddBtn');
  if (addBtn) addBtn.addEventListener('click', () => {
    filterRules.push({ logic: 'AND', field: '总份额_亿', op: '>=', value: '' });
    _selectedPreset = ''; localStorage.removeItem('etf_selected_preset'); saveFilterRules(); renderFilterPanel(); render();
  });
  const clearBtn = document.getElementById('fpClearBtn');
  if (clearBtn) clearBtn.addEventListener('click', () => {
    filterRules = []; _selectedPreset = ''; localStorage.removeItem('etf_selected_preset'); saveFilterRules(); renderFilterPanel(); render();
  });
  const saveBtn = document.getElementById('fpSaveBtn');
  if (saveBtn) saveBtn.addEventListener('click', () => {
    const name = prompt('为当前筛选方案命名：');
    if (!name || !name.trim()) return;
    const savedP = JSON.parse(localStorage.getItem('etf_filter_presets') || '{}');
    savedP[name.trim()] = JSON.parse(JSON.stringify(filterRules));
    localStorage.setItem('etf_filter_presets', JSON.stringify(savedP));
    renderFilterPanel();
  });
  const presetSel = document.getElementById('fpPresetSel');
  if (presetSel) {
    if (_selectedPreset) presetSel.value = _selectedPreset;
    presetSel.addEventListener('change', () => {
      const val = presetSel.value;
      if (!val) { _selectedPreset = ''; localStorage.removeItem('etf_selected_preset'); return; }
      _selectedPreset = val;
      localStorage.setItem('etf_selected_preset', val);
      if (val.startsWith('p:')) {
        const savedP = JSON.parse(localStorage.getItem('etf_filter_presets') || '{}');
        filterRules = savedP[val.slice(2)] || [];
      } else if (FILTER_PRESETS[val]) {
        filterRules = JSON.parse(JSON.stringify(FILTER_PRESETS[val]));
      }
      // Auto-show relevant columns for this preset
      const PRESET_SHOW_COLS = {
        '估值低位': ['PE历史分位','PB历史分位'],
        '估值高位': ['PE历史分位','PB历史分位'],
        '杠杆看多': ['融资余额_亿','融资净买入_亿'],
        '恐慌抄底': ['PCR成交量比','融资净买入_亿'],
        '折价博弈(<-1.5%)': ['净值溢价率','IOPV'],
        '溢价预警(>1.5%)': ['净值溢价率','IOPV'],
        '份额变动强度': ['汇金持股_亿','比汇金改变比'],
        '汇金 ETF 份额观察': ['机构持仓占比','比汇金改变比'],
      };
      const showCols = PRESET_SHOW_COLS[val.replace(/^p:/, '')];
      if (showCols) {
        showCols.forEach(k => visibleKeys.add(k));
        localStorage.setItem('etf_visible_cols', JSON.stringify([...visibleKeys]));
      }
      saveFilterRules(); renderFilterPanel(); render();
    });
  }
}

// ====== Column Panel ======
function toggleCol(key){
  if(visibleKeys.has(key)) visibleKeys.delete(key);
  else visibleKeys.add(key);
  localStorage.setItem('etf_visible_cols', JSON.stringify([...visibleKeys]));
  render();
}
function renderColPanel(){
  const groups = {};
  ALL_COLS.forEach(c=>{
    if(!groups[c.group]) groups[c.group]=[];
    groups[c.group].push(c);
  });
  let html='';
  for(const [g,cols] of Object.entries(groups)){
    html+=`<div class="col-group-title">${g}</div>`;
    cols.forEach(c=>{
      const checked=visibleKeys.has(c.key)?'checked':'';
      html+=`<label class="col-item"><input type="checkbox" ${checked} data-key="${c.key}">${c.label}</label>`;
    });
  }
  document.getElementById('colPanel').innerHTML=html;
  document.querySelectorAll('#colPanel input').forEach(cb=>{
    cb.addEventListener('change',()=>toggleCol(cb.dataset.key));
  });
}
function getColCount(){return Math.max(1, getVisibleCols().length);}

// ====== Data Load ======
async function loadData(){
  const cc=getColCount();
  document.getElementById('tbody').innerHTML='<tr><td colspan="'+cc+'" class="loading">加载ETF数据...</td></tr>';
  try{
    const r=await fetch('/api/etf/all');
    const d=await r.json();
    if(!Array.isArray(d)){
      const errMsg = (d && d.error) ? d.error : '服务器返回数据格式异常';
      throw new Error(errMsg);
    }
    allData=d;
    render(allData);
    loadNorthbound();
    loadBondYield();
    loadSectorFlow();
    loadHuijinOverview();
    loadHuijinBacktest();
    loadCffexPositionRank();
  }catch(e){
    document.getElementById('tbody').innerHTML='<tr><td colspan="'+cc+'" class="error">加载失败: '+e.message+'</td></tr>';
  }
}

async function loadNorthbound(){
  try{
    const r=await fetch('/api/etf/northbound');
    const d=await r.json();
    if(d && d.total_net != null){
      const net = Number(d.total_net);
      const cls = net>=0?'pos':'neg';
      const nbEl = document.getElementById('northboundInfo');
      if(nbEl) nbEl.innerHTML = `北向: <b class="${cls}">${net>=0?'+':''}${net.toFixed(2)}</b>亿`;
    }
  }catch(e){}
}

async function loadBondYield(){
  try{
    const r=await fetch('/api/etf/bond-yield');
    const d=await r.json();
    if(d && d.y10 != null){
      const el = document.getElementById('bondYieldInfo');
      if(el){
        const y10Cls = d.y10 < 2 ? 'neg' : (d.y10 > 3 ? 'pos' : '');
        const spreadCls = d.spread_10_2 != null ? (d.spread_10_2 < 0 ? 'pos' : '') : '';
        let html = `10Y:<b class="${y10Cls}">${d.y10.toFixed(2)}%</b>`;
        if(d.spread_10_2 != null) html += ` | 10-2Y:<b class="${spreadCls}">${d.spread_10_2.toFixed(2)}%</b>`;
        el.innerHTML = html;
      }
    }
  }catch(e){}
}

async function loadHuijinOverview(){
  try{
    const r = await fetch('/api/huijin/overview');
    const d = await r.json();
    if(d && Array.isArray(d.items)){
      huijinOverview = d;
      renderHuijinWatch();
    }
  }catch(e){}
}

async function loadHuijinBacktest(){
  try{
    const r = await fetch('/api/huijin/backtest?windows=5,10,20,60');
    const d = await r.json();
    if(d && d.metrics){
      huijinBacktest = d;
      renderHuijinWatch();
    }
  }catch(e){}
}

async function loadCffexPositionRank(){
  try{
    const r = await fetch('/api/huijin/cffex-position-rank?limit=1000');
    const d = await r.json();
    if(Array.isArray(d)){
      cffexPositionRank = d;
      renderHuijinWatch();
    }
  }catch(e){}
}

// Huijin Watch tab switching
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    const isHuijin = tab.dataset.tab === 'huijin';
    document.getElementById('sectorFlowPanel').style.display = isHuijin ? 'none' : '';
    document.querySelector('.table-section').style.display = isHuijin ? 'none' : '';
    document.getElementById('huijinWatchPanel').style.display = isHuijin ? '' : 'none';
    document.querySelector('.filter-title').style.display = isHuijin ? 'none' : '';
    document.getElementById('exchangeFilterLabel').style.display = isHuijin ? 'none' : '';
    document.getElementById('searchInput').style.display = isHuijin ? 'none' : '';
    document.getElementById('statsBar').style.display = isHuijin ? 'none' : '';
    const nb = document.getElementById('northboundInfo');
    if(nb) nb.style.display = isHuijin ? 'none' : '';
    const by = document.getElementById('bondYieldInfo');
    if(by) by.style.display = isHuijin ? 'none' : '';
    // Hide topbar buttons unrelated to huijin tab
    document.getElementById('colToggleBtn').style.display = isHuijin ? 'none' : '';
    document.getElementById('filterToggleBtn').style.display = isHuijin ? 'none' : '';
    document.getElementById('refreshBtn').style.display = isHuijin ? 'none' : '';
  });
});

function firstIssueText(item){
  const issues = item.blockers && item.blockers.length ? item.blockers : (item.warnings || []);
  if(!issues.length) return '';
  const issue = issues[0];
  return issue.message || issue.issue_type || '';
}

function issueTypeList(item, max=3){
  const issues = [...(item.blockers || []), ...(item.warnings || [])];
  return issues.slice(0, max).map(i => i.issue_type || i.message).filter(Boolean).join(' / ');
}

function qualityLabel(item){
  if(item.quality_state && item.quality_state.label) return item.quality_state.label;
  const ql = item.quality_level || '';
  if(ql === 'data_blocked') return '数据阻断';
  if(ql === 'warning') return '质量警告';
  if(ql === 'observable') return '已核验可观察';
  if(ql === 'preview') return '区间预览';
  return '待核验';
}

function sourceLevelText(level){
  return {
    'A':'A 交易所直采',
    'B':'B 源日期推断',
    'C':'C 交易所滞后',
    'D':'D legacy/缺失'
  }[level] || level || 'N/A';
}

function resonanceText(level){
  return {
    'strong_resonance':'强共振',
    'weak_resonance':'弱共振',
    'single_driven':'单只驱动',
    'single_or_weak':'弱信号',
    'divergent':'分歧',
    'flat':'平稳',
    'no_signal':'样本不足'
  }[level] || level || '样本不足';
}

function marketSupportText(level){
  return {
    'supportive':'环境支持观察',
    'neutral':'环境中性',
    'caution':'环境需谨慎',
    'insufficient_data':'环境数据不足'
  }[level] || level || '环境数据不足';
}

function renderTenXRecentDays(signal){
  const days = (signal && signal.recent_days) || [];
  if(!days.length) return '';
  const chips = days.map(d => {
    const cls = d.passed ? 'hjw-signal-badge' : (d.direction === 'contraction' ? 'hjw-warn' : 'hjw-tag');
    const ratio = d.ratio_to_baseline == null ? '--' : Number(d.ratio_to_baseline).toFixed(1) + 'x';
    const delta = d.share_delta_万 == null ? '' : ' ' + Number(d.share_delta_万).toFixed(0) + '万';
    return '<span class="' + cls + '" title="' + esc(d.date || '') + delta + '">' + esc((d.date || '').slice(5)) + ' ' + esc(ratio) + '</span>';
  }).join(' ');
  return '<div class="hjw-detail-row"><span class="hjw-detail-label">10x近7日</span><span class="hjw-detail-val">' + chips + '</span></div>';
}

function renderBacktestBreakdownTable(title, data){
  const entries = Object.entries(data || {});
  if(!entries.length) return '';
  let html = '<div class="hjt-subtitle">' + esc(title) + '</div>';
  html += '<div class="hjw-table-wrap"><table class="hjw-table hjw-backtest-table"><thead><tr><th>分层</th><th>事件</th><th>5日命中</th><th>5日均值</th><th>20日命中</th><th>20日均值</th></tr></thead><tbody>';
  entries.slice(0, 8).forEach(([key, obj]) => {
    const m5 = (obj.metrics || {})['5'] || {};
    const m20 = (obj.metrics || {})['20'] || {};
    html += `<tr>
      <td>${esc(key)}</td>
      <td class="hjw-num">${esc(obj.event_count || 0)}</td>
      <td class="hjw-num">${m5.directional_hit_rate == null ? _na() : fmtPct(m5.directional_hit_rate)}</td>
      <td class="hjw-num">${m5.average_return_pct == null ? _na() : fmtPct(m5.average_return_pct)}</td>
      <td class="hjw-num">${m20.directional_hit_rate == null ? _na() : fmtPct(m20.directional_hit_rate)}</td>
      <td class="hjw-num">${m20.average_return_pct == null ? _na() : fmtPct(m20.average_return_pct)}</td>
    </tr>`;
  });
  html += '</tbody></table></div>';
  return html;
}

function renderHuijinBacktestPanel(){
  if(!huijinBacktest) {
    return '<div class="hjw-table-note">回测/复盘加载中；当前页面先按“样本不足/仅可观察”处理。</div>';
  }
  const status = huijinBacktest.status === 'ok' ? '<span class="hjw-ok">样本可复盘</span>' : '<span class="hjw-warn">样本不足/仅可观察</span>';
  const gate = huijinBacktest.sample_gate || {};
  const readyWindows = (huijinBacktest.ready_windows || gate.ready_windows || []).map(w => String(w) + '日').join('/');
  const insufficientWindows = (huijinBacktest.insufficient_windows || gate.insufficient_windows || []).map(w => String(w) + '日').join('/');
  let html = '<div class="hjt-title"><span class="hjt-dot ok"></span>回测/复盘<span class="hjt-note">事件研究，不生成直接买卖建议</span></div>';
  html += '<div class="hjw-table-note"><b>方法</b>：仅使用 disclosure_date ≤ 信号日的 verified 基准；T 日生成观察信号，T+1 或后续首个K线收盘价开始评估；默认过滤 blocked/warning；期指与持仓排名不进入核心公式。</div>';
  html += '<div class="hjw-backtest-summary"><span>状态 ' + status + '</span><span>事件 <b>' + esc(huijinBacktest.event_count || 0) + '</b></span><span>候选点 <b>' + esc(huijinBacktest.candidate_point_count || 0) + '</b></span><span>' + esc(huijinBacktest.message || '') + '</span>' + (readyWindows ? '<span>达标 <b>' + esc(readyWindows) + '</b></span>' : '') + (insufficientWindows ? '<span class="hjw-warn">不足 <b>' + esc(insufficientWindows) + '</b></span>' : '') + '</div>';
  const explanations = gate.explanation || [];
  const skippedReasons = huijinBacktest.skipped_reasons || [];
  const skippedIssues = huijinBacktest.skipped_issue_reasons || [];
  if(explanations.length || skippedReasons.length || skippedIssues.length){
    html += '<div class="hjw-issue-strip"><b>复盘门禁</b>';
    explanations.slice(0, 3).forEach(t => {
      html += '<span class="hjw-issue-pill">' + esc(t) + '</span>';
    });
    skippedReasons.slice(0, 4).forEach(r => {
      html += '<span class="hjw-issue-pill">' + esc(r.label || r.reason) + ' <b>' + esc(r.count) + '</b></span>';
    });
    skippedIssues.slice(0, 4).forEach(r => {
      html += '<span class="hjw-issue-pill">' + esc(r.issue_type) + ' <b>' + esc(r.count) + '</b></span>';
    });
    html += '</div>';
  }
  const metrics = huijinBacktest.metrics || {};
  html += '<div class="hjw-table-wrap"><table class="hjw-table hjw-backtest-table"><thead><tr><th>窗口</th><th>信号次数</th><th>方向命中率</th><th>平均收益</th><th>最大回撤</th><th>状态</th></tr></thead><tbody>';
  ['5','10','20','60'].forEach(k => {
    const m = metrics[k] || {};
    html += `<tr>
      <td>${esc(k)}日</td>
      <td class="hjw-num">${m.signal_count == null ? _na() : esc(m.signal_count)}</td>
      <td class="hjw-num">${m.directional_hit_rate == null ? _na() : fmtPct(m.directional_hit_rate)}</td>
      <td class="hjw-num">${m.average_return_pct == null ? _na() : fmtPct(m.average_return_pct)}</td>
      <td class="hjw-num">${m.max_drawdown_pct == null ? _na() : fmtPct(m.max_drawdown_pct)}</td>
      <td>${m.sample_status === 'ok' ? '<span class="hjw-ok">可复盘</span>' : '<span class="hjw-warn">样本不足</span>'}</td>
    </tr>`;
  });
  html += '</tbody></table></div>';
  const breakdowns = huijinBacktest.breakdowns || {};
  html += '<div class="hjw-table-note"><b>分层复盘</b>：按观察等级、方向、数据源等级、质量门禁和观察组拆解，避免只看总体样本导致误判。</div>';
  html += renderBacktestBreakdownTable('按观察等级', breakdowns.by_observation_level);
  html += renderBacktestBreakdownTable('按观察组', breakdowns.by_group);
  html += renderBacktestBreakdownTable('按数据源等级', breakdowns.by_source_level);
  return html;
}

function huijinOverviewItem(code){
  if(!huijinOverview || !Array.isArray(huijinOverview.items)) return null;
  return huijinOverview.items.find(i => String(i.code) === String(code)) || null;
}

function renderHuijinDetailMeta(code){
  const item = huijinOverviewItem(code);
  if(!item) return '';
  const base = item.baseline || {};
  const share = item.latest_share || {};
  const source = share.source_name || '待审计';
  const sourceDate = share.source_date || share.date || '';
  const inferred = share.source_date_inferred ? ' 推断' : '';
  let html = '<div class="hjw-detail-section">';
  html += '<div class="hjw-detail-title">汇金 ETF 份额观察</div>';

  // Baseline info
  if(base.s0_total_shares){
    const s0 = (base.s0_total_shares / 1e8).toFixed(2);
    const h0 = (base.h0_total_shares / 1e8).toFixed(2);
    const a = (base.a_ratio * 100).toFixed(1);
    html += '<div class="hjw-detail-row"><span class="hjw-detail-label">基准(S0)</span><span class="hjw-detail-val">' + s0 + '亿</span>';
    html += '<span class="hjw-detail-label">汇金(H0)</span><span class="hjw-detail-val">' + h0 + '亿</span>';
    html += '<span class="hjw-detail-label">占比(A)</span><span class="hjw-detail-val">' + a + '%</span></div>';
  }

  // Current shares and interval
  if(item.can_calculate_interval && item.interval){
    const iv = item.interval;
    const s1 = share.total_shares ? (share.total_shares / 1e8).toFixed(2) : '--';
    const b = (iv.b_ratio * 100).toFixed(2);
    html += '<div class="hjw-detail-row"><span class="hjw-detail-label">当前(S1)</span><span class="hjw-detail-val">' + s1 + '亿</span>';
    html += '<span class="hjw-detail-label">倍数(B)</span><span class="hjw-detail-val">' + b + '%</span>';
    html += '<span class="hjw-detail-label">区间(Y)</span><span class="hjw-detail-val">' + fmtRatio(iv.y_min) + ' ~ ' + fmtRatio(iv.y_max) + '</span></div>';
    // Trend direction vs price correlation
    const dir = item.share_change_direction || 'unknown';
    const dirLabel = item.share_change_direction_label || '';
    const obsLabel = item.observation_label || '观望';
    const chg5d = item.share_change_ratio_5d;
    html += '<div class="hjw-detail-row"><span class="hjw-detail-label">观察等级</span><span class="hjw-detail-val">' + esc(obsLabel) + '</span>';
    if(chg5d != null) html += '<span class="hjw-detail-label">份额5日</span><span class="hjw-detail-val' + (chg5d < -2 ? ' neg' : chg5d > 2 ? ' pos' : '') + '">' + Number(chg5d).toFixed(1) + '%</span>';
    if(item.share_change_ratio_20d != null) html += '<span class="hjw-detail-label">20日</span><span class="hjw-detail-val">' + Number(item.share_change_ratio_20d).toFixed(1) + '%</span>';
    html += '</div>';
    html += '<div class="hjw-detail-row" style="font-size:11px;color:#718096">区间方向: ' + esc(dirLabel) + '。观察等级反映份额变化趋势，与K线价格走势无直接对应关系。</div>';

    if(item.ten_x_signal && item.ten_x_signal.active){
      const days = item.ten_x_signal.consecutive_days || 0;
      html += '<div class="hjw-detail-row hjw-detail-signal">10x份额扩张: ' + esc(item.ten_x_signal.trigger_reason || '持续' + days + '天') + ', 基准量=' + fmtVol(item.ten_x_signal.baseline_volume) + ', 当前倍率=' + esc(item.ten_x_signal.current_ratio) + 'x</div>';
    }
    html += renderTenXRecentDays(item.ten_x_signal);
  } else {
    const reason = firstIssueText(item) || '缺少已核验基准或有效份额审计';
    html += '<div class="hjw-detail-row hjw-detail-blocked">阻断: ' + esc(reason) + '</div>';
    html += renderTenXRecentDays(item.ten_x_signal);
  }

  // Source and quality
  const hasDocUrl = base.source_doc_url ? 'Y' : 'N';
  const docLink = base.source_doc_url ? '<a href="' + esc(base.source_doc_url) + '" target="_blank" class="hjw-doc-link">查看公告</a>' : '';
  const slLabel = sourceLevelText(item.source_level);
  html += '<div class="hjw-detail-row"><span class="hjw-detail-label">份额源</span><span class="hjw-detail-val">' + esc(source) + ' ' + esc(sourceDate) + inferred + ' (' + slLabel + ')</span>';
  if(docLink) html += '<span class="hjw-detail-label">公告</span><span class="hjw-detail-val">' + docLink + '</span>';
  html += '</div>';

  // Quality marks
  const qmarks = [];
  if(inferred) qmarks.push('<span class="hjw-warn">推断</span>');
  if(hasDocUrl === 'N') qmarks.push('<span class="hjw-block">缺公告</span>');
  if(share.stale) qmarks.push('<span class="hjw-warn">滞后' + esc(share.stale_days || '') + '天</span>');
  const tags = item.quality_tags || [];
  tags.forEach(t => {
    const isWarn = t.includes('inferred') || t === 'legacy_source';
    qmarks.push(isWarn ? '<span class="hjw-warn">' + esc(t.replace(/_/g,' ')) + '</span>' : '<span class="hjw-tag">' + esc(t.replace(/_/g,' ')) + '</span>');
  });
  if(qmarks.length){
    html += '<div class="hjw-detail-row"><span class="hjw-detail-label">质量</span><span class="hjw-detail-val">' + qmarks.join(' ') + '</span></div>';
  }
  if(item.signal){
    const sig = item.signal;
    const rs = (sig.reasons || []).join('；') || '--';
    const nr = (sig.not_triggered_reasons || []).join('；') || '--';
    html += '<div class="hjw-detail-row"><span class="hjw-detail-label">观察等级</span><span class="hjw-detail-val">' + esc(sig.observation_label || qualityLabel(item)) + '</span>';
    html += '<span class="hjw-detail-label">方向</span><span class="hjw-detail-val">' + esc(sig.direction_label || '') + '</span></div>';
    html += '<div class="hjw-detail-row"><span class="hjw-detail-label">信号原因</span><span class="hjw-detail-val">' + esc(rs) + '</span></div>';
    html += '<div class="hjw-detail-row"><span class="hjw-detail-label">未触发原因</span><span class="hjw-detail-val">' + esc(nr) + '</span></div>';
  }

  html += '</div>';
  return html;
}

const TAG_LABELS = {
  baseline_verified: '基准已核验',
  baseline_unverified: '基准未核验',
  source_level_a: '源A级(交易所直采)',
  source_level_b: '源B级(交易所推断)',
  source_level_c: '源C级(滞后)',
  source_level_d: '源D级(旧数据)',
  exchange_source: '交易所源',
  source_date_inferred: '源日期推断',
  doc_url_missing: '缺公告链接',
  missing_h0: '缺H0',
  missing_verified_baseline: '缺verified基准',
  data_blocked: '数据阻断',
  stale_share: '份额滞后',
  sse_source_lag: '上交所滞后',
  legacy_source: '旧数据源',
  share_gap: '份额断档',
  abnormal_jump: '份额异常跳变',
};
const TAG_TIPS = {
  source_date_inferred: '深市份额数据无明确源日期，由交易日历推断',
  source_level_a: '上交所交易所直采，源日期明确',
  source_level_b: '深交所交易所直采，源日期由日历推断',
  exchange_source: '数据来自交易所官方接口',
  baseline_verified: '汇金披露基准已核验通过',
  stale_share: '份额日早于观察日对应交易日，按滞后数据观察',
  sse_source_lag: '上交所份额数据采集存在滞后',
};

function renderHuijinWatch(){
  const panel = document.getElementById('huijinWatchPanel');
  if(!panel || !huijinOverview || !Array.isArray(huijinOverview.items)) return;
  const items = huijinOverview.items;
  if(!items.length){ panel.style.display='none'; return; }
  const as_of = huijinOverview.as_of_date || '';
  const latest_share_date = huijinOverview.latest_share_date || '';
  const tenX = huijinOverview.ten_x_active_count || 0;
  const tenXCodes = huijinOverview.ten_x_active_codes || [];
  const qSummary = huijinOverview.quality_summary || {};
  const verifiedDoc = qSummary.observable_count ?? items.filter(i => i.quality_levels && i.quality_levels.overall_quality === 'observable').length;
  const warningDoc = qSummary.warning_count ?? items.filter(i => i.quality_levels && i.quality_levels.overall_quality === 'warning').length;
  const formulaPrev = qSummary.preview_count ?? items.filter(i => i.quality_levels && i.quality_levels.overall_quality === 'preview').length;
  const formulaCalc = qSummary.formula_calculable_count ?? items.filter(i => i.can_calculate_interval).length;
  const dataBlocked = qSummary.data_blocked_count ?? items.filter(i => i.quality_levels && i.quality_levels.overall_quality === 'data_blocked').length;
  const inferred = items.filter(i => i.quality_tags && i.quality_tags.includes('source_date_inferred')).length;
  const stale = items.filter(i => i.latest_share && i.latest_share.stale).length;
  const hasCffex = cffexPositionRank && cffexPositionRank.length > 0;
  const qCounts = qSummary.issue_counts || huijinOverview.quality_issue_counts || {};
  const issueRows = Object.entries(qCounts).sort((a,b) => b[1]-a[1]).slice(0, 8);
  const rows = [...items].sort((a,b) => {
    let va = a[_hjwSortKey], vb = b[_hjwSortKey];
    if(va == null && vb == null) return 0;
    if(va == null) return 1; if(vb == null) return -1;
    if(typeof va === 'string') va = va.toLowerCase();
    if(typeof vb === 'string') vb = vb.toLowerCase();
    try{
      if(va < vb) return _hjwSortAsc ? -1 : 1;
      if(va > vb) return _hjwSortAsc ? 1 : -1;
    }catch(e){}
    return 0;
  });
  // Apply filter
  const filteredRows = rows.filter(item => {
    if(_hjwFilter === 'all') return true;
    if(_hjwFilter === 'enhanced') return item.observation_level === 'strong' || item.observation_level === 'enhanced';
    if(_hjwFilter === 'weakened') return item.observation_level === 'weakened';
    if(_hjwFilter === 'tenx') return item.ten_x_signal && item.ten_x_signal.active;
    if(_hjwFilter === 'stale') return item.latest_share && item.latest_share.stale;
    return true;
  });

  let html = '<div class="hjw-head">';
  html += '<div class="hjw-title">汇金 ETF 份额观察</div>';
  html += '<details class="hjw-usage-details"><summary>使用说明</summary><div class="hjw-usage-body">';
  html += '<p><b>第一步：数据质量</b>—确认状态/质量为"可观察"，无阻断/警告。<b>排除</b>栏显示被移除ETF原因。</p>';
  html += '<p><b>第二步：单ETF分析</b>—点击代码查看K线+Y区间趋势。观察等级：增强观察=份额显著扩张，减弱观察=份额显著收缩，观望=无明显变化。10x信号仅表示持续份额异常放大，不确认交易。</p>';
  html += '<p><b>第三步：ETF池共振</b>—同指数多ETF合并观察。共振标记组内ETF方向一致性。单只贡献>60%时标记"驱动"，注意单只异动风险。</p>';
  html += '<p><b>第四步：期指辅助</b>—中金所排名仅辅助验证，不进公式。IF=沪深300，IH=上证50，IC=中证500，IM=中证1000。</p>';
  html += '<p><b>限制</b>：份额变化不必然来自中央汇金；Y区间是相对S0归一化口径，不是实时持仓；不输出买卖建议。</p>';
  html += '</div></details>';
  html += `<div class="hjw-summary"><span>区间可算 <b>${formulaCalc}</b></span><span>质量警告 <b>${warningDoc}</b></span><span>数据阻断 <b>${dataBlocked}</b></span><span>推断源日期 <b>${inferred}</b></span>${tenX ? `<span class="hjw-signal">10x份额扩张 <b>${tenX}</b></span>` : ''}</div>`;
  html += '<div class="hjw-subhead"><span>系统数据截至 <b>' + esc(as_of) + '</b></span><span>有效份额日 <b>' + esc(latest_share_date) + '</b></span><span>观察池 <b>14</b> 只</span></div>';
  html += '<div class="hjw-subnote">观察池基于基金年报汇金持仓数据。已排除: 588000(华夏科创50ETF)—2025年报前十名持有人未见中央汇金。</div>';
  html += '</div>';

  // ─── Quality summary bar ───
  html += '<div class="hjw-quality-bar"><span>已核验可观察 <b>' + verifiedDoc + '</b></span><span>可观察但警告 <b>' + warningDoc + '</b></span><span>区间预览 <b>' + formulaPrev + '</b></span><span>数据阻断 <b>' + dataBlocked + '</b></span><span>推断源日期 <b>' + inferred + '</b></span>' + (stale ? '<span class="hjw-warn">数据滞后 <b>' + stale + '</b></span>' : '') + '<span>期指 ' + (hasCffex ? '<b class="hjw-ok">有</b>' : '<b class="hjw-warn">无</b>') + '</span></div>';
  if(issueRows.length){
    html += '<div class="hjw-issue-strip"><b>问题清单</b>';
    issueRows.forEach(([type, count]) => {
      html += '<span class="hjw-issue-pill">' + esc(type) + ' <b>' + esc(count) + '</b></span>';
    });
    html += '</div>';
  }

  const marketSummary = huijinOverview.market_context || {};
  if(huijinOverview.groups && huijinOverview.groups.length){
    html += '<div class="hjw-issue-strip"><b>市场环境辅助</b>';
    html += '<span class="hjw-issue-pill">支持 <b>' + esc(marketSummary.supportive_count || 0) + '</b></span>';
    html += '<span class="hjw-issue-pill">中性 <b>' + esc(marketSummary.neutral_count || 0) + '</b></span>';
    html += '<span class="hjw-issue-pill">谨慎 <b>' + esc(marketSummary.caution_count || 0) + '</b></span>';
    html += '<span class="hjw-issue-pill">不足 <b>' + esc(marketSummary.insufficient_count || 0) + '</b></span>';
    html += '<span class="hjw-issue-pill">仅辅助，不进公式</span>';
    html += '</div>';
  }

  // ─── Table 1: 汇金 ETF 份额观察 ───
  html += '<div class="hjt-title"><span class="hjt-dot ok"></span>汇金 ETF 份额观察<span class="hjt-note">' + formulaCalc + '/' + items.length + ' 区间可算，点击代码查看K线+区间趋势</span></div>';
  html += '<div class="hjw-table-note"><b>字段说明</b>：<b>报告期</b>—汇金持有数据的来源报告（年报/半年报）。<b>披露日</b>—公告日期，此日期前的数据不可用。<b>份额日</b>—ETF总份额S1的最新交易日。<b>状态/质量</b>—可观察=基准核验+数据完整可进入公式；warning=可观察但默认不进回测；blocked=不输出区间和有效信号。<b>区间</b>—Y_min~Y_max归一化区间，Y_max=B=S1/S0（当前份额比），Y_min=max(0, B-(1-A))，A=H0/S0（披露日汇金占比）。<b>用法</b>：份额扩张→增强观察，份额收缩→减弱观察，无明显变化→观望。10x仅表示持续份额扩张，不确认交易。<b>变化%</b>—份额相对N个交易日前的变化率。</div>';
  // Filter bar
  const filters = [
    {key:'all', label:'全部', count:items.length},
    {key:'enhanced', label:'增强', count:items.filter(i=>i.observation_level==='strong'||i.observation_level==='enhanced').length},
    {key:'weakened', label:'减弱', count:items.filter(i=>i.observation_level==='weakened').length},
    {key:'tenx', label:'10x', count:items.filter(i=>i.ten_x_signal&&i.ten_x_signal.active).length},
    {key:'stale', label:'滞后', count:items.filter(i=>i.latest_share&&i.latest_share.stale).length},
  ];
  html += '<div class="hjw-filter-bar">';
  filters.forEach(f => {
    const active = _hjwFilter === f.key ? ' hjw-filter-active' : '';
    html += `<span class="hjw-filter-btn${active}" data-filter="${esc(f.key)}">${esc(f.label)} <b>${f.count}</b></span>`;
  });
  html += '</div>';
  const srt = (key) => _hjwSortKey === key ? (_hjwSortAsc ? ' ▲' : ' ▼') : '';
  html += '<div class="hjw-table-wrap"><table class="hjw-table"><thead><tr>'
    + '<th class="hjw-srt" data-sort="code">代码/名称' + srt('code') + '</th>'
    + '<th title="基于基准质量、份额质量和预警的综合评级">状态/质量</th>'
    + '<th title="当前观察等级及未触发增强/减弱观察的具体原因">观察/未触发原因</th>'
    + '<th class="hjw-srt" data-sort="can_calculate_interval" title="Y_min~Y_max归一化区间，Y_max=B=S1/S0，Y_min=max(0,B-(1-A))">区间/原因' + srt('can_calculate_interval') + '</th>'
    + '<th class="hjw-srt" data-sort="vs_baseline_pct" title="当前份额相对披露日S0的增减比例">变动强度' + srt('vs_baseline_pct') + '</th>'
    + '<th class="hjw-srt" data-sort="share_change_ratio_5d">5日%' + srt('share_change_ratio_5d') + '</th>'
    + '<th class="hjw-srt" data-sort="share_change_ratio_10d">10日%' + srt('share_change_ratio_10d') + '</th>'
    + '<th class="hjw-srt" data-sort="share_change_ratio_20d">20日%' + srt('share_change_ratio_20d') + '</th>'
    + '<th class="hjw-srt" data-sort="share_change_ratio_60d">60日%' + srt('share_change_ratio_60d') + '</th>'
    + '<th>观察组</th><th>报告期</th><th>披露日</th><th>份额日</th>'
    + '</tr></thead><tbody>';
  const okItems = items.filter(i => i.can_calculate_interval);
  filteredRows.forEach(item => {
    const base = item.baseline || {};
    const share = item.latest_share || {};
    const groups = (item.watch_groups || []).join(' / ');
    const inferredMark = share.source_date_inferred ? '<span class="hjw-warn">推断</span>' : '';
    const tenXSignal = item.ten_x_signal && item.ten_x_signal.active;
    const ql = (item.quality_levels && item.quality_levels.overall_quality) || 'blocked';
    const sl = item.source_level || 'D';
    const ol = item.observation_level || 'watch';
    const tags = item.quality_tags || [];
    let statusHtml;
    if(ql === 'data_blocked'){
      statusHtml = '<span class="hjw-block">数据阻断</span>';
    } else if(ql === 'warning'){
      statusHtml = '<span class="hjw-warn">质量警告</span>';
    } else if(ql === 'observable'){
      statusHtml = '<span class="hjw-ok">已核验可观察</span>';
    } else if(ql === 'preview'){
      statusHtml = '<span class="hjw-ok">区间预览</span>';
    } else {
      statusHtml = '<span class="hjw-block">待核验</span>';
    }
    // Observation level
    let obsHtml;
    if(ol === 'strong') obsHtml = '<span class="hjw-signal-badge">增强观察</span>';
    else if(ol === 'enhanced') obsHtml = '<span class="hjw-ok">增强观察</span>';
    else if(ol === 'weakened') obsHtml = '<span class="hjw-warn">减弱观察</span>';
    else if(ol === 'blocked') obsHtml = '<span class="hjw-block">数据阻断</span>';
    else obsHtml = '<span class="hjw-tag">观望</span>';
    // Quality tags display
const tagEls = tags.map(t => {
      const cls = t === 'baseline_verified' ? 'hjw-tag-ok' : t.includes('inferred') || t === 'legacy_source' ? 'hjw-tag-warn' : '';
      const label = TAG_LABELS[t] || t.replace(/_/g, ' ');
      const tip = TAG_TIPS[t] || label;
      return '<span class="hjw-tag ' + cls + '" title="' + esc(tip) + '">' + esc(label) + '</span>';
    });
    const tagShort = tagEls.slice(0, 2).join(' ');
    const signalBadge = tenXSignal ? '<span class="hjw-signal-badge">10x</span>' : '';
    let result = esc(firstIssueText(item));
    if(item.can_calculate_interval && item.interval){
      result = `${fmtRatio(item.interval.y_min)} ~ ${fmtRatio(item.interval.y_max)}`;
    }
    const chg = (v) => v != null && !isNaN(v) ? '<span class="hjw-chg' + (v < -10 ? ' hjw-chg-bad' : v > 2 ? ' hjw-chg-good' : '') + '">' + Number(v).toFixed(1) + '%</span>' : _na();
    const sig = item.signal || {};
    const notReason = (item.not_triggered_reasons || sig.not_triggered_reasons || []).slice(0, 2).join('；');
    const sigReason = (item.signal_reasons || sig.reasons || []).slice(0, 2).join('；');
    const obsTitle = sigReason || notReason || issueTypeList(item) || qualityLabel(item);
    const obsDetail = sigReason ? sigReason : notReason;
    html += `<tr>
      <td><span class="code clickable" data-code="${esc(item.code)}" data-name="${esc(item.name || '')}">${esc(item.code)}</span> ${obsHtml}<br><span class="hjw-name">${esc(item.name || '')}</span></td>
      <td>${statusHtml}<br><span class="hjw-row-tags">${tagShort}</span></td>
      <td class="hjw-result" title="${esc(obsTitle)}">${obsDetail ? esc(obsDetail) : _na()}</td>
      <td class="hjw-result" title="${esc(result)}">${result || _na()}</td>
      <td class="hjw-num" title="相对披露日S0的变化率">${item.vs_baseline_pct != null ? chg(item.vs_baseline_pct) : _na()}</td>
      <td class="hjw-num">${chg(item.share_change_ratio_5d)}</td>
      <td class="hjw-num">${chg(item.share_change_ratio_10d)}</td>
      <td class="hjw-num">${chg(item.share_change_ratio_20d)}</td>
      <td class="hjw-num">${chg(item.share_change_ratio_60d)}</td>
      <td>${groups ? esc(groups) : _na()}</td>
      <td>${base.report_period ? esc(base.report_period) : _na()}</td>
      <td>${base.disclosure_date ? esc(base.disclosure_date) : _na()}</td>
      <td>${share.date ? esc(share.date) : _na()} ${inferredMark}
      ${share.stale ? `<span class="hjw-warn" title="${esc(share.data_lag_reason || '')}">滞后${esc(share.stale_days || '')}天</span>` : ''}</td>
    </tr>`;
  });
  // Summary row
  if(okItems.length > 0){
    const avg = (field) => {
      const vals = okItems.map(i => i[field]).filter(v => v != null && isFinite(v));
      return vals.length ? vals.reduce((a,b) => a+b, 0) / vals.length : null;
    };
    const avgVsBase = avg('vs_baseline_pct');
    const avg5d = avg('share_change_ratio_5d');
    const avg10d = avg('share_change_ratio_10d');
    const avg20d = avg('share_change_ratio_20d');
    const avg60d = avg('share_change_ratio_60d');
    const chgS = (v) => v != null && !isNaN(v) ? '<span class="hjw-chg' + (v < -10 ? ' hjw-chg-bad' : v > 0 ? ' hjw-chg-good' : '') + '">' + Number(v).toFixed(1) + '%</span>' : _na();
    html += `<tr class="hjw-summary-row">
      <td><b>平均(${okItems.length}只)</b></td>
      <td></td>
      <td></td>
      <td></td>
      <td class="hjw-num">${chgS(avgVsBase)}</td>
      <td class="hjw-num">${chgS(avg5d)}</td>
      <td class="hjw-num">${chgS(avg10d)}</td>
      <td class="hjw-num">${chgS(avg20d)}</td>
      <td class="hjw-num">${chgS(avg60d)}</td>
      <td colspan="4"></td>
    </tr>`;
  }
  html += '</tbody></table></div>';

  // ─── Table 2: ETF 池份额观察 ───
  if(huijinOverview.groups && huijinOverview.groups.length){
    html += '<div class="hjt-title"><span class="hjt-dot ok"></span>ETF池贡献拆解<span class="hjt-note">按跟踪指数归并，仅含汇金持仓ETF</span></div>';
    html += '<div class="hjw-table-note"><b>说明</b>：将跟踪同一指数的多只汇金持仓ETF合并观察。<b>共振</b>—组内ETF份额方向是否一致；<b>环境</b>—代表ETF回撤/收益与指数估值分位，仅辅助验证。合并口径不代表单一账户持有比例，仅用于观察同指数ETF的整体份额趋势。</div>';
    html += '<div class="hjw-table-wrap"><table class="hjw-table hjw-pool-table"><thead><tr><th>观察组/成分</th><th>代码</th><th>状态</th><th>共振/环境</th><th>总份额(亿)</th><th>权重</th><th>5日%</th><th>20日%</th><th>5日贡献</th></tr></thead><tbody>';
    huijinOverview.groups.forEach(g => {
      const codes = (g.codes || []).join(' / ');
      const chg = (v) => v != null && !isNaN(v) ? '<span class="hjw-chg' + (v < -10 ? ' hjw-chg-bad' : v > 2 ? ' hjw-chg-good' : '') + '">' + Number(v).toFixed(1) + '%</span>' : _na();
      const warnNote = [];
      if(g.blocked_codes && g.blocked_codes.length) warnNote.push('blocked ' + g.blocked_codes.join('/'));
      if(g.warning_codes && g.warning_codes.length) warnNote.push('warning ' + g.warning_codes.join('/'));
      const mc = g.market_context || {};
      const resonance = resonanceText(g.resonance_level);
      const resonanceReasons = (g.resonance_reasons || []).slice(0, 2).join('；');
      const marketReasons = (mc.reasons || []).slice(0, 2).join('；');
      html += `<tr class="hjw-pool-group">
        <td><b>${esc(g.group_name)}</b></td>
        <td>${esc(codes)}</td>
        <td>${warnNote.length ? '<span class="hjw-warn">' + esc(warnNote.join('；')) + '</span>' : '<span class="hjw-ok">可观察</span>'}</td>
        <td><span class="hjw-tag">${esc(resonance)}</span><br><span class="hjw-name" title="${esc(resonanceReasons + '；' + marketReasons)}">${esc(marketSupportText(mc.support_level))}</span></td>
        <td class="hjw-num">${g.latest_total_shares ? (g.latest_total_shares / 1e8).toFixed(2) : _na()}</td>
        <td class="hjw-num">100%</td>
        <td class="hjw-num">${chg(g.share_change_ratio_5d)}</td>
        <td class="hjw-num">${chg(g.share_change_ratio_20d)}</td>
        <td class="hjw-num">${_na()}</td>
      </tr>`;
      (g.components || []).forEach(gi => {
        const giShares = gi.latest_total_shares || 0;
        const giPct = gi.share_weight_pct != null ? gi.share_weight_pct.toFixed(1) : '--';
        const state = gi.quality_filter_level === 'blocked' ? '<span class="hjw-block">blocked</span>' :
          gi.quality_filter_level === 'warning' ? '<span class="hjw-warn">warning</span>' : '<span class="hjw-ok">ok</span>';
        const contrib = gi.change_contribution_5d_pct != null ? gi.change_contribution_5d_pct.toFixed(1) + '%' : '--';
        const isDriver = gi.change_contribution_5d_pct != null && Math.abs(gi.change_contribution_5d_pct) > 60;
        const giChg = (v) => v != null && !isNaN(v) ? '<span class="hjw-chg' + (v < -10 ? ' hjw-chg-bad' : v > 2 ? ' hjw-chg-good' : '') + '">' + Number(v).toFixed(1) + '%</span>' : _na();
        html += `<tr class="hjw-pool-child">
          <td class="hjw-pool-indent">${esc(gi.name || gi.code)}${isDriver ? ' <span class="hjw-signal-badge">驱动</span>' : ''}</td>
          <td>${esc(gi.code)}</td>
          <td>${state}</td>
          <td>${esc(gi.share_change_direction_label || '')}</td>
          <td class="hjw-num">${giShares > 0 ? (giShares / 1e8).toFixed(2) : _na()}</td>
          <td class="hjw-num"><span class="hjw-pool-share">${giPct}%</span></td>
          <td class="hjw-num">${giChg(gi.share_change_ratio_5d)}</td>
          <td class="hjw-num">${giChg(gi.share_change_ratio_20d)}</td>
          <td class="hjw-num">${esc(contrib)}</td>
        </tr>`;
      });
    });
    html += '</tbody></table></div>';
  }

  // ─── 10x signal detail (compact bar) ───
  if(tenXCodes.length){
    html += '<div class="hjw-signal-detail">';
    tenXCodes.forEach(code => {
      const item = items.find(i => String(i.code) === String(code));
      if(item && item.ten_x_signal){
        const s = item.ten_x_signal;
        const days = s.consecutive_days || 0;
        const recent = (s.recent_days || []).slice(-3).map(d => (d.date || '').slice(5) + ':' + (d.ratio_to_baseline == null ? '--' : Number(d.ratio_to_baseline).toFixed(1) + 'x')).join(' / ');
        html += `<span class="hjw-signal-item">${esc(code)}: ${s.trigger_reason || '持续' + days + '天'}, 基准量=${fmtVol(s.baseline_volume)}, 当前倍率=${s.current_ratio}x${recent ? '，近3日 ' + esc(recent) : ''}</span>`;
      }
    });
    html += '</div>';
  }

  html += renderHuijinBacktestPanel();

  // ─── Table 3: 期指辅助 ───
  html += '<div class="hjt-title"><span class="hjt-dot ok"></span>期指辅助<span class="hjt-note">中金所排名，不进入核心公式，仅辅助验证</span></div>';
  const cffexMeta = huijinOverview.cffex_meta || {};
  if(cffexPositionRank.length){
    const rankRows = cffexPositionRank.slice(0, 40);
    const metaLine = cffexMeta.available
      ? `日期 <b>${esc(cffexMeta.latest_date || '')}</b>，合约覆盖 <b>${esc(cffexMeta.contract_count || 0)}</b> 个${cffexMeta.stale ? '，<span class="hjw-warn">滞后</span>' : '，<span class="hjw-ok">当日</span>'}`
      : '<span class="hjw-warn">暂无期指辅助数据</span>';
    html += '<div class="hjw-table-note"><b>说明</b>：中金所股指期货成交持仓排名，仅作辅助验证，不进入核心公式。' + metaLine + '。IF=沪深300，IH=上证50，IC=中证500，IM=中证1000。</div>';
    html += '<div class="hjw-table-wrap"><table class="hjw-table hjw-cffex-table"><thead><tr><th>合约</th><th>类型</th><th>排名</th><th>会员</th><th>数量</th><th>变化</th></tr></thead><tbody>';
    rankRows.forEach(r => {
      html += `<tr>
        <td>${esc(r.contract || '')}</td>
        <td>${esc(rankTypeText(r.rank_type))}</td>
        <td>${r.rank_no == null ? _na() : esc(r.rank_no)}</td>
        <td>${esc(r.member_name || '')}</td>
        <td>${r.volume == null ? _na() : esc(Number(r.volume).toFixed(0))}</td>
        <td>${r.change == null ? _na() : fmtChg(Number(r.change))}</td>
      </tr>`;
    });
    html += '</tbody></table></div>';
  } else {
    html += '<div class="hjw-table-note" style="color:#718096">期指辅助暂无数据（交易日18:30后更新），不影响核心公式，仅影响辅助验证。页面仍按汇金 ETF 份额观察处理。</div>';
  }

  panel.innerHTML = html;

  // Click handler for huijin code → open detail modal
  panel.querySelectorAll('.code.clickable').forEach(el => {
    el.addEventListener('click', () => {
      openDetail(el.dataset.code, el.dataset.name);
    });
  });
  // Click handler for huijin table sort
  panel.querySelectorAll('.hjw-srt').forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.sort;
      if(_hjwSortKey === key) _hjwSortAsc = !_hjwSortAsc;
      else { _hjwSortKey = key; _hjwSortAsc = false; }
      renderHuijinWatch();
    });
  });
  // Click handler for huijin filter
  panel.querySelectorAll('.hjw-filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      _hjwFilter = btn.dataset.filter;
      renderHuijinWatch();
    });
  });
}

function rankTypeText(type){
  if(type === 'long') return '多单';
  if(type === 'short') return '空单';
  if(type === 'volume') return '成交';
  return type || '';
}

let _sfAllData = {};
let _sfSortPeriod = '1d';
let _sfSortDir = 'desc';

async function loadSectorFlow(){
  try {
    const periods = ['1d','3d','5d','10d','20d'];
    const labels = {'1d':'即时','3d':'3日','5d':'5日','10d':'10日','20d':'20日'};
    const results = await Promise.all(periods.map(p =>
      fetch('/api/etf/sector-flow?period='+p).then(r => r.json()).catch(() => ({}))
    ));
    _sfAllData = {};
    let hasData = false;
    periods.forEach((p, i) => {
      const data = results[i].data || [];
      if(data.length) hasData = true;
      _sfAllData[p] = {data, label: labels[p]};
    });
    if(!hasData) return;
    const panel = document.getElementById('sectorFlowPanel');
    panel.style.display = '';
    const body = document.getElementById('sectorFlowBody');
    if(body) body.style.display = 'none';
    _sfRender();
  } catch(e) {
    console.error('sector flow load error:', e);
  }
}

function _sfRender(){
  const wrap = document.getElementById('sfTableWrap');
  const periods = ['1d','3d','5d','10d','20d'];
  const labels = {'1d':'即时','3d':'3日','5d':'5日','10d':'10日','20d':'20日'};

  // Build merged map: sector_name -> {1d: net, 3d: net, ...}
  const merged = {};
  periods.forEach(p => {
    (_sfAllData[p]?.data || []).forEach(s => {
      const name = s.sector_name;
      if(!merged[name]) merged[name] = {sector_name: name, '1d': null, '3d': null, '5d': null, '10d': null, '20d': null};
      merged[name][p] = Number(s.net_main || 0);
    });
  });

  const rows = Object.values(merged);
  if(!rows.length){ wrap.innerHTML='<div class="sf-empty">暂无数据</div>'; return; }

  const periodKeys = ['1d','3d','5d','10d','20d'];
  const maxAbsByPeriod = {};
  periodKeys.forEach(p => {
    maxAbsByPeriod[p] = Math.max(...rows.map(s => Math.abs(Number(s[p] || 0))), 1);
  });

  const sorted = [...rows].sort((a,b) => {
    const va = Number(a[_sfSortPeriod] || 0);
    const vb = Number(b[_sfSortPeriod] || 0);
    return _sfSortDir === 'desc' ? vb - va : va - vb;
  });

  // Column headers: 行业, then each period (clickable for sort)
  let html = '<table class="sf-table"><tr><th class="sf-th" style="text-align:left">行业</th>';
  periodKeys.forEach(p => {
    const active = p === _sfSortPeriod;
    const arrow = active ? (_sfSortDir === 'desc' ? ' ▼' : ' ▲') : '';
    html += `<th class="sf-th" data-period="${p}" style="text-align:right">${labels[p]}${arrow}</th>`;
  });
  html += '</tr>';

  sorted.forEach(s => {
    html += `<tr class="sf-row" data-sector="${escHtml(s.sector_name)}"><td class="sf-name">${escHtml(s.sector_name)}</td>`;
    periodKeys.forEach(p => {
      const nm = Number(s[p] || 0);
      const cls = nm >= 0 ? 'pos' : 'neg';
      const pct = maxAbsByPeriod[p] > 0 ? Math.abs(nm) / maxAbsByPeriod[p] : 0;
      const barDir = nm >= 0 ? 'right' : 'left';
      html += `<td class="sf-num ${cls}"><div class="sf-bar-wrap"><div class="sf-bar sf-bar-${barDir}" style="width:${(pct*100).toFixed(0)}%"></div><span class="sf-bar-val">${fmtNum(nm)}</span></div></td>`;
    });
    html += '</tr>';
  });
  html += '</table>';
  wrap.innerHTML = html;

  // Sortable period headers
  wrap.querySelectorAll('.sf-th[data-period]').forEach(th => {
    th.addEventListener('click', () => {
      const p = th.dataset.period;
      if(p === _sfSortPeriod) _sfSortDir = _sfSortDir === 'desc' ? 'asc' : 'desc';
      else { _sfSortPeriod = p; _sfSortDir = 'desc'; }
      _sfRender();
    });
  });
  wrap.querySelectorAll('.sf-row').forEach(row => {
    row.addEventListener('click', () => {
      const sector = row.dataset.sector;
      applySectorFilter(sector);
    });
  });
}



function escHtml(s){
  if(!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function escAttr(s){
  return String(s).replace(/"/g,'&quot;').replace(/&/g,'&amp;');
}

function fmtNum(v){
  if(v == null) return '<span class="na">--</span>';
  const n = Number(v);
  if(n >= 10000) return (n/10000).toFixed(2) + '亿';
  return n.toFixed(2) + '万';
}

function applySectorFilter(sector){
  const rules = [{logic:'AND', field:'跟踪指数', op:'contains', value:sector}];
  filterRules = rules;
  _selectedPreset = '';
  localStorage.removeItem('etf_selected_preset');
  saveFilterRules();
  renderFilterPanel();
  render();
}

// ====== ETF Detail Panel ======
let _detailFetchController = null;

function openDetail(code, name){
  const modal = document.getElementById('detailModal');
  document.getElementById('detailTitle').textContent = code + ' ' + (name || '');
  modal.style.display = 'flex';
  // Cancel previous fetch
  if(_detailFetchController) _detailFetchController.abort();
  _detailFetchController = new AbortController();
  // Reset previous state
  const canvas = document.getElementById('klineCanvas');
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  document.getElementById('detailMeta').innerHTML = '<span class="loading" style="padding:8px">加载K线数据...</span>';
  const wrap = document.getElementById('huijinTrendWrap');
  if(wrap) wrap.style.display = 'none';
  fetchKlineAndRender(code, name);
}

document.getElementById('detailClose').addEventListener('click', closeDetail);
document.getElementById('detailModal').addEventListener('click', (e) => {
  if(e.target.closest('.modal-content')) return;
  closeDetail();
});
document.addEventListener('keydown', (e) => {
  if(e.key === 'Escape') closeDetail();
});
function closeDetail(){
  if(_detailFetchController) _detailFetchController.abort();
  _detailFetchController = null;
  const canvas = document.getElementById('klineCanvas');
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  document.getElementById('detailMeta').innerHTML = '';
  const wrap = document.getElementById('huijinTrendWrap');
  if(wrap) wrap.style.display = 'none';
  document.getElementById('detailModal').style.display = 'none';
}

async function fetchKlineAndRender(code, name){
  const controller = _detailFetchController;
  if(!controller) return;
  try{
    const r = await fetch('/api/etf/kline?code=' + code + '&limit=120', {signal: controller.signal});
    const data = await r.json();
    if(!data || !data.length){
      document.getElementById('detailMeta').innerHTML = '<span class="na">K线数据暂不可用（backfill进行中）</span>';
      return;
    }
    data.reverse();
    renderKlineChart(data);
    const meta = document.getElementById('detailMeta');
    const last = data[data.length-1];
    const prices = data.map(d => d.close);
    const ma5 = calcMA(prices, 5);
    const ma20 = calcMA(prices, 20);
    const rsi = calcRSI(prices, 14);
    const bbands = calcBollinger(prices, 20, 2);
    const lastMA5 = ma5[ma5.length-1];
    const lastMA20 = ma20[ma20.length-1];
    const lastRSI = rsi[rsi.length-1];
    const lastBB = bbands[bbands.length-1];
    let html = '';
    html += '<span class="dm-item">收盘:<b>' + last.close + '</b></span>';
    if(lastMA5 != null) html += '<span class="dm-item">MA5:<b>' + lastMA5.toFixed(2) + '</b></span>';
    if(lastMA20 != null) html += '<span class="dm-item">MA20:<b>' + lastMA20.toFixed(2) + '</b></span>';
    if(lastRSI != null){
      const rsiCls = lastRSI < 30 ? 'neg' : (lastRSI > 70 ? 'pos' : '');
      html += '<span class="dm-item">RSI(14):<b class="' + rsiCls + '">' + lastRSI.toFixed(1) + '</b></span>';
    }
    if(lastBB){
      html += '<span class="dm-item">布林上:<b>' + lastBB.upper.toFixed(2) + '</b></span>';
      html += '<span class="dm-item">布林中:<b>' + lastBB.mid.toFixed(2) + '</b></span>';
      html += '<span class="dm-item">布林下:<b>' + lastBB.lower.toFixed(2) + '</b></span>';
    }
    html += '<span class="dm-item">振幅:<b>' + last.amplitude + '%</b></span>';
    if(last.volume) html += '<span class="dm-item">成交量:<b>' + fmtVol(last.volume) + '</b></span>';
    if(last.turnover != null) html += '<span class="dm-item">换手率:<b>' + last.turnover + '%</b></span>';
    html += renderHuijinDetailMeta(code);
    meta.innerHTML = html;

    // Conditionally load Huijin trend chart
    const hi = huijinOverviewItem(code);
    const wrap = document.getElementById('huijinTrendWrap');
    if(hi && hi.can_calculate_interval && hi.interval){
      wrap.style.display = '';
      try{
        const sr = await fetch('/api/huijin/' + code + '/series?limit=90', {signal: controller.signal});
        const sd = await sr.json();
        if(sd && sd.series && sd.series.length > 1){
          renderHuijinTrendChart(sd.series, sd.baseline);
        }else{
          wrap.style.display = 'none';
        }
      }catch(e){
        wrap.style.display = 'none';
      }
    }else{
      wrap.style.display = 'none';
    }
  }catch(e){
    if(e.name === 'AbortError') return;
    const wrap = document.getElementById('huijinTrendWrap');
    if(wrap) wrap.style.display = 'none';
    document.getElementById('detailMeta').innerHTML = '<span class="error" style="padding:8px">K线数据加载失败，请确认服务器运行中</span>';
  }
}

function fmtVol(v){
  if(v == null) return '--';
  if(v >= 1e8) return (v/1e8).toFixed(2) + '亿';
  if(v >= 1e4) return (v/1e4).toFixed(0) + '万';
  return v.toFixed(0);
}

function calcMA(data, period){
  const result = [];
  for(let i=0; i<data.length; i++){
    if(i < period-1){ result.push(null); continue; }
    let sum = 0;
    for(let j=i-period+1; j<=i; j++) sum += data[j];
    result.push(sum / period);
  }
  return result;
}

function calcRSI(data, period){
  const result = [];
  for(let i=0; i<data.length; i++){
    if(i < period){ result.push(null); continue; }
    let gains = 0, losses = 0;
    for(let j=i-period+1; j<=i; j++){
      const diff = data[j] - data[j-1];
      if(diff > 0) gains += diff;
      else losses -= diff;
    }
    const avgGain = gains / period;
    const avgLoss = losses / period;
    if(avgLoss === 0){ result.push(100); continue; }
    const rs = avgGain / avgLoss;
    result.push(100 - 100 / (1 + rs));
  }
  return result;
}

function calcBollinger(data, period, k){
  const result = [];
  for(let i=0; i<data.length; i++){
    if(i < period-1){ result.push(null); continue; }
    let sum = 0;
    for(let j=i-period+1; j<=i; j++) sum += data[j];
    const mid = sum / period;
    let sqSum = 0;
    for(let j=i-period+1; j<=i; j++) sqSum += (data[j] - mid) ** 2;
    const std = Math.sqrt(sqSum / period);
    result.push({mid, upper: mid + k*std, lower: mid - k*std});
  }
  return result;
}

function renderKlineChart(data){
  const canvas = document.getElementById('klineCanvas');
  const rect = canvas.parentElement.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const isMobile = window.innerWidth <= 900;
  const w = Math.max(280, rect.width - 2);
  const h = isMobile ? Math.min(280, Math.round(w * 0.6)) : 360;
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = w + 'px';
  canvas.style.height = h + 'px';
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);

  const pad = {top:20, bottom:25, left:10, right:10};
  const chartW = w - pad.left - pad.right;
  const chartH = h - pad.top - pad.bottom;

  const prices = data.map(d => d.close);
  const ma5 = calcMA(prices, 5);
  const ma20 = calcMA(prices, 20);
  const bbands = calcBollinger(prices, 20, 2);

  const validPrices = prices.filter(p => p != null);
  if(!validPrices.length) return;
  const minP = Math.min(...validPrices);
  const maxP = Math.max(...validPrices);
  const range = maxP - minP || 1;
  const padRange = range * 0.08;
  const yMin = minP - padRange;
  const yMax = maxP + padRange;

  const toX = i => pad.left + (i / (data.length-1)) * chartW;
  const toY = v => pad.top + chartH - ((v - yMin) / (yMax - yMin)) * chartH;

  ctx.clearRect(0, 0, w, h);

  // Grid lines
  ctx.strokeStyle = '#f0f0f0';
  ctx.lineWidth = 1;
  for(let i=0; i<5; i++){
    const y = pad.top + (i/4) * chartH;
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(w-pad.right, y); ctx.stroke();
  }

  // Bollinger Bands
  ctx.fillStyle = 'rgba(0,184,148,0.06)';
  ctx.beginPath();
  let started = false;
  for(let i=0; i<data.length; i++){
    const bb = bbands[i];
    if(!bb){ continue; }
    if(!started){ ctx.moveTo(toX(i), toY(bb.upper)); started = true; }
    else ctx.lineTo(toX(i), toY(bb.upper));
  }
  for(let i=data.length-1; i>=0; i--){
    const bb = bbands[i];
    if(!bb) continue;
    ctx.lineTo(toX(i), toY(bb.lower));
  }
  ctx.closePath(); ctx.fill();

  // MA20
  ctx.strokeStyle = '#f39c12';
  ctx.lineWidth = 1;
  ctx.setLineDash([4,3]);
  ctx.beginPath();
  started = false;
  for(let i=0; i<data.length; i++){
    const v = ma20[i];
    if(v == null){ started = false; continue; }
    if(!started){ ctx.moveTo(toX(i), toY(v)); started = true; }
    else ctx.lineTo(toX(i), toY(v));
  }
  ctx.stroke();
  ctx.setLineDash([]);

  // MA5
  ctx.strokeStyle = '#e74c3c';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  started = false;
  for(let i=0; i<data.length; i++){
    const v = ma5[i];
    if(v == null){ started = false; continue; }
    if(!started){ ctx.moveTo(toX(i), toY(v)); started = true; }
    else ctx.lineTo(toX(i), toY(v));
  }
  ctx.stroke();

  // Candlesticks
  const candleW = Math.max(1, (chartW / data.length) * 0.6);
  for(let i=0; i<data.length; i++){
    const d = data[i];
    if(d.open == null || d.close == null) continue;
    const x = toX(i) - candleW/2;
    const openY = toY(d.open);
    const closeY = toY(d.close);
    const highY = toY(d.high || d.close);
    const lowY = toY(d.low || d.close);
    const isGreen = d.close >= d.open;
    ctx.fillStyle = isGreen ? '#e74c3c' : '#16833a';
    ctx.strokeStyle = isGreen ? '#e74c3c' : '#16833a';
    ctx.lineWidth = 1;
    // wick
    ctx.beginPath(); ctx.moveTo(toX(i), highY); ctx.lineTo(toX(i), lowY); ctx.stroke();
    // body
    const bodyY = Math.min(openY, closeY);
    const bodyH = Math.max(1, Math.abs(closeY - openY));
    ctx.fillRect(x, bodyY, candleW, bodyH);
  }
}

function renderHuijinTrendChart(series, baseline){
  const canvas = document.getElementById('huijinTrendCanvas');
  if(!canvas) return;
  const wrap = document.getElementById('huijinTrendWrap');
  const rect = canvas.parentElement.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const isMobile = window.innerWidth <= 900;
  const w = Math.max(280, rect.width - 2);
  const h = isMobile ? Math.min(200, Math.round(w * 0.5)) : 240;
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = w + 'px';
  canvas.style.height = h + 'px';
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);

  const pad = {top:16, bottom:22, left:8, right:8};
  const chartW = w - pad.left - pad.right;
  const chartH = h - pad.top - pad.bottom;

  const valid = series.filter(d => d.status === 'ok' && d.y_min != null && d.y_max != null && d.b_ratio != null);
  if(valid.length < 2){ if(wrap) wrap.style.display = 'none'; return; }

  const aVal = baseline && baseline.a_ratio != null ? parseFloat(baseline.a_ratio) : null;
  const allVals = valid.flatMap(d => [d.y_min, d.y_max, d.b_ratio]);
  if(aVal != null) allVals.push(aVal);
  const minV = Math.min(0, ...allVals);
  const maxV = Math.max(...allVals) * 1.1;
  const range = maxV - minV || 1;

  const toX = i => pad.left + (i / (valid.length-1)) * chartW;
  const toY = v => pad.top + chartH - ((v - minV) / range) * chartH;

  ctx.clearRect(0, 0, w, h);

  // ─── Anomaly overlays: data gaps ───
  for(let i=1; i<valid.length; i++){
    const days = (new Date(valid[i].date) - new Date(valid[i-1].date)) / 86400000;
    if(days > 5){
      const gx = (toX(i-1) + toX(i)) / 2;
      ctx.strokeStyle = 'rgba(231,76,60,0.25)';
      ctx.lineWidth = 1;
      ctx.setLineDash([2,3]);
      ctx.beginPath(); ctx.moveTo(gx, pad.top); ctx.lineTo(gx, pad.top + chartH); ctx.stroke();
      ctx.setLineDash([]);
    }
  }

  // Grid lines
  ctx.strokeStyle = '#f0f0f0';
  ctx.lineWidth = 1;
  for(let i=0; i<5; i++){
    const y = pad.top + (i/4) * chartH;
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(w-pad.right, y); ctx.stroke();
  }

  // Y_min-Y_max fill band
  ctx.fillStyle = 'rgba(0,184,148,0.12)';
  ctx.beginPath();
  let started = false;
  for(let i=0; i<valid.length; i++){
    const d = valid[i];
    if(!started){ ctx.moveTo(toX(i), toY(d.y_max)); started = true; }
    else ctx.lineTo(toX(i), toY(d.y_max));
  }
  for(let i=valid.length-1; i>=0; i--){
    ctx.lineTo(toX(i), toY(valid[i].y_min));
  }
  ctx.closePath(); ctx.fill();

  // Y_max line
  ctx.strokeStyle = '#00b894';
  ctx.lineWidth = 1;
  ctx.beginPath();
  started = false;
  for(let i=0; i<valid.length; i++){
    if(!started){ ctx.moveTo(toX(i), toY(valid[i].y_max)); started = true; }
    else ctx.lineTo(toX(i), toY(valid[i].y_max));
  }
  ctx.stroke();

  // Y_min line
  ctx.strokeStyle = 'rgba(0,184,148,0.5)';
  ctx.lineWidth = 1;
  ctx.setLineDash([3,3]);
  ctx.beginPath();
  started = false;
  for(let i=0; i<valid.length; i++){
    if(!started){ ctx.moveTo(toX(i), toY(valid[i].y_min)); started = true; }
    else ctx.lineTo(toX(i), toY(valid[i].y_min));
  }
  ctx.stroke();
  ctx.setLineDash([]);

  // B-ratio line
  ctx.strokeStyle = '#00b894';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  started = false;
  for(let i=0; i<valid.length; i++){
    const v = valid[i].b_ratio;
    if(v == null){ started = false; continue; }
    if(!started){ ctx.moveTo(toX(i), toY(v)); started = true; }
    else ctx.lineTo(toX(i), toY(v));
  }
  ctx.stroke();

  // A-ratio baseline
  if(aVal != null){
    ctx.strokeStyle = '#f39c12';
    ctx.lineWidth = 1;
    ctx.setLineDash([5,4]);
    const ay = toY(aVal);
    ctx.beginPath(); ctx.moveTo(pad.left, ay); ctx.lineTo(w-pad.right, ay); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = '#f39c12';
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('A=' + aVal.toFixed(3), pad.left + 3, ay - 3);
  }

  // ─── Anomaly markers: inferred dates ───
  for(let i=0; i<valid.length; i++){
    if(valid[i].source_date_inferred){
      const x = toX(i);
      const y = toY(valid[i].b_ratio != null ? valid[i].b_ratio : valid[i].y_max);
      ctx.fillStyle = 'rgba(227,52,47,0.5)';
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // X-axis date labels
  ctx.fillStyle = '#718096';
  ctx.font = '10px sans-serif';
  ctx.textAlign = 'center';
  const labelStep = Math.max(1, Math.floor(valid.length / 6));
  for(let i=0; i<valid.length; i+=labelStep){
    const label = (valid[i].date || '').slice(5);
    ctx.fillText(label, toX(i), h - 4);
  }
}

// ====== Init ======
document.getElementById('filterToggleBtn').addEventListener('click', (e) => {
  e.stopPropagation();
  const panel = document.getElementById('filterPanel');
  const isOpen = panel.classList.toggle('open');
  if (isOpen) renderFilterPanel();
  document.getElementById('colPanel').style.display = 'none';
  document.getElementById('qrPanel').classList.remove('open');
});
document.getElementById('qrBtn').addEventListener('click', (e) => {
  e.stopPropagation();
  document.getElementById('qrPanel').classList.toggle('open');
  document.getElementById('filterPanel').classList.remove('open');
  document.getElementById('colPanel').style.display = 'none';
});
document.addEventListener('click', (e) => {
  const panel = document.getElementById('filterPanel');
  if (panel.classList.contains('open') && !e.target.closest('.fp-wrap')) {
    panel.classList.remove('open');
  }
  const colPanel = document.getElementById('colPanel');
  if (colPanel.style.display === 'block' && !e.target.closest('.col-wrap') && !e.target.closest('.fp-wrap')) {
    colPanel.style.display = 'none';
  }
  const qrPanel = document.getElementById('qrPanel');
  if (qrPanel.classList.contains('open') && !e.target.closest('.qr-wrap')) {
    qrPanel.classList.remove('open');
  }
});
document.getElementById('filterPanel').addEventListener('click', (e) => {
  if (e.target.id === 'fpCloseBtn') {
    document.getElementById('filterPanel').classList.remove('open');
  }
  e.stopPropagation();
});

document.getElementById('colToggleBtn').addEventListener('click', () => {
  const panel = document.getElementById('colPanel');
  panel.style.display = panel.style.display === 'block' ? 'none' : 'block';
  if (panel.style.display === 'block') renderColPanel();
  document.getElementById('filterPanel').classList.remove('open');
});

let searchTimer;
document.getElementById('searchInput').addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => render(), 150);
});
document.getElementById('exchangeFilter').addEventListener('change', () => render());
document.getElementById('refreshBtn').addEventListener('click', loadData);

document.getElementById('sectorFlowToggle').addEventListener('click', () => {
  const panel = document.getElementById('sectorFlowPanel');
  const body = document.getElementById('sectorFlowBody');
  const arrow = document.querySelector('.sf-arrow');
  panel.style.display = '';
  const isHidden = body.style.display === 'none' || body.style.display === '';
  if (isHidden) {
    body.style.display = 'block';
    if(arrow) arrow.textContent = '▾';
  } else {
    body.style.display = 'none';
    if(arrow) arrow.textContent = '▸';
  }
});

updateFilterBadge();
loadData();

// Code column click -> detail panel
document.getElementById('tbody').addEventListener('click', (e) => {
  const td = e.target.closest('td.cell-code');
  if(!td) return;
  const tr = td.closest('tr');
  if(!tr || !tr.dataset.code) return;
  const code = tr.dataset.code;
  const d = allData.find(x => x['代码'] === code);
  if(!d) return;
  openDetail(code, d['名称']);
  // Close mobile filter/col panels
  document.getElementById('filterPanel').classList.remove('open');
  document.getElementById('colPanel').style.display = 'none';
});
setInterval(loadData, 300000);
