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
  {key:'汇金持股_亿', label:'汇金(亿)', group:'其他', def:false, srt:true},
  {key:'比汇金改变比', label:'份额强度', group:'其他', def:true, srt:true, tip:'份额改变额÷汇金披露线索份额'},
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
  {label:'⚡ 信号监测', keys:['折价博弈(<-1.5%)','溢价预警(>1.5%)','资金持续流入','大额赎回预警','放量下跌异动','规模激增异动','汇金 ETF 份额异动']},
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
  '汇金 ETF 份额异动': [
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
const PRESET_RENAMES = {
  ['汇金' + '动态调仓']: '汇金 ETF 份额异动',
  ['国家队' + '增仓']: '汇金 ETF 份额观察'
};
if (PRESET_RENAMES[_selectedPreset]) {
  _selectedPreset = PRESET_RENAMES[_selectedPreset];
  localStorage.setItem('etf_selected_preset', _selectedPreset);
}

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
        '汇金 ETF 份额异动': ['汇金持股_亿','比汇金改变比'],
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

async function loadCffexPositionRank(){
  try{
    const r = await fetch('/api/huijin/cffex-position-rank?limit=50');
    const d = await r.json();
    if(Array.isArray(d)){
      cffexPositionRank = d;
      renderHuijinWatch();
    }
  }catch(e){}
}

function firstIssueText(item){
  const issues = item.blockers && item.blockers.length ? item.blockers : (item.warnings || []);
  if(!issues.length) return '';
  const issue = issues[0];
  return issue.message || issue.issue_type || '';
}

function huijinOverviewItem(code){
  if(!huijinOverview || !Array.isArray(huijinOverview.items)) return null;
  return huijinOverview.items.find(i => String(i.code) === String(code)) || null;
}

function renderHuijinDetailMeta(code){
  const item = huijinOverviewItem(code);
  if(!item) return '';
  const share = item.latest_share || {};
  const source = share.source_name || '待审计';
  const sourceDate = share.source_date || share.date || '';
  const inferred = share.source_date_inferred ? ' 推断' : '';
  const status = item.can_calculate_interval ? '可计算' : '数据不足/需复核';
  let html = '<span class="dm-item">汇金观察:<b>' + esc(status) + '</b></span>';
  html += '<span class="dm-item">份额日:<b>' + esc(share.date || '--') + '</b></span>';
  html += '<span class="dm-item">来源:<b>' + esc(source + (sourceDate ? ' ' + sourceDate : '') + inferred) + '</b></span>';
  if(item.can_calculate_interval && item.interval){
    html += '<span class="dm-item">归一化区间:<b>' + fmtRatio(item.interval.y_min) + '~' + fmtRatio(item.interval.y_max) + '</b></span>';
    html += '<span class="dm-item">公式:<b>B=S1/S0, Y=max(0,B-(1-A))~B</b></span>';
  }else{
    const reason = firstIssueText(item) || '缺少已核验基准或有效份额审计';
    html += '<span class="dm-item">阻断:<b>' + esc(reason) + '</b></span>';
  }
  return html;
}

function renderHuijinWatch(){
  const panel = document.getElementById('huijinWatchPanel');
  if(!panel || !huijinOverview || !Array.isArray(huijinOverview.items)) return;
  const items = huijinOverview.items;
  if(!items.length){ panel.style.display='none'; return; }
  const ok = items.filter(i => i.can_calculate_interval).length;
  const blocked = items.length - ok;
  const inferred = items.filter(i => i.latest_share && i.latest_share.source_date_inferred).length;
  const rows = [...items].sort((a,b) => {
    if(a.can_calculate_interval !== b.can_calculate_interval) return a.can_calculate_interval ? -1 : 1;
    return String(a.code).localeCompare(String(b.code));
  }).slice(0, 12);

  let html = '<div class="hjw-head">';
  html += '<div class="hjw-title">汇金观察</div>';
  html += `<div class="hjw-summary"><span>可计算 <b>${ok}</b></span><span>需复核 <b>${blocked}</b></span><span>推断源日期 <b>${inferred}</b></span><span>期指辅助 <b>${cffexPositionRank.length}</b></span><span>截至 ${esc(huijinOverview.as_of_date || '')}</span></div>`;
  html += '</div>';
  html += '<div class="hjw-note">相对披露日总份额归一化口径；不是实时汇金持仓，也不是交易确认。</div>';
  html += '<div class="hjw-table-wrap"><table class="hjw-table"><thead><tr><th>代码</th><th>观察组</th><th>报告期</th><th>披露日</th><th>份额日</th><th>状态</th><th>区间/原因</th></tr></thead><tbody>';
  rows.forEach(item => {
    const base = item.baseline || {};
    const share = item.latest_share || {};
    const groups = (item.watch_groups || []).join(' / ');
    const inferredMark = share.source_date_inferred ? '<span class="hjw-warn">推断</span>' : '';
    const status = item.can_calculate_interval ? '<span class="hjw-ok">可计算</span>' : '<span class="hjw-block">数据不足/需复核</span>';
    let result = esc(firstIssueText(item));
    if(item.can_calculate_interval && item.interval){
      result = `${fmtRatio(item.interval.y_min)} ~ ${fmtRatio(item.interval.y_max)}`;
    }
    html += `<tr>
      <td><span class="code">${esc(item.code)}</span></td>
      <td>${groups ? esc(groups) : _na()}</td>
      <td>${base.report_period ? esc(base.report_period) : _na()}</td>
      <td>${base.disclosure_date ? esc(base.disclosure_date) : _na()}</td>
      <td>${share.date ? esc(share.date) : _na()} ${inferredMark}</td>
      <td>${status}</td>
      <td>${result || _na()}</td>
    </tr>`;
  });
  html += '</tbody></table></div>';
  if(cffexPositionRank.length){
    const rankRows = cffexPositionRank.slice(0, 8);
    html += '<div class="hjw-cffex">';
    html += '<div class="hjw-subhead"><span>期指辅助</span><span>中金所成交持仓排名，不进入核心公式</span></div>';
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
    html += '</tbody></table></div></div>';
  }
  panel.innerHTML = html;
  panel.style.display = '';
}

function rankTypeText(type){
  if(type === 'long') return '多单';
  if(type === 'short') return '空单';
  if(type === 'volume') return '成交';
  return type || '';
}

let _sfData = [];
let _sfPeriod = '1d';
let _sfSortCol = 'net_main';
let _sfSortDir = 'desc';

async function loadSectorFlow(){
  await _sfLoad(_sfPeriod);
}

async function _sfLoad(period){
  try{
    const r=await fetch('/api/etf/sector-flow?period='+period);
    const d=await r.json();
    if(!d || !d.length) return;
    _sfData = d;
    _sfPeriod = period;
    const panel = document.getElementById('sectorFlowPanel');
    panel.style.display = '';
    const body = document.getElementById('sectorFlowBody');
    body.style.display = 'none';
    _sfRender();
  }catch(e){}
}

function _sfRender(){
  const wrap = document.getElementById('sfTableWrap');
  if(!_sfData.length){ wrap.innerHTML='<div class="sf-empty">暂无数据</div>'; return; }

  const maxAbs = Math.max(..._sfData.map(s => Math.abs(Number(s[_sfSortCol] || 0))), 1);
  const sorted = [..._sfData].sort((a,b) => {
    const va = Number(a[_sfSortCol] || 0);
    const vb = Number(b[_sfSortCol] || 0);
    return _sfSortDir === 'desc' ? vb - va : va - vb;
  });

  const cols = [
    {key:'sector_name', label:'行业',      align:'left'},
    {key:'net_main',    label:'主力净流入', align:'right'},
    {key:'net_super_large', label:'超大单', align:'right'},
    {key:'net_large',   label:'大单',      align:'right'},
    {key:'net_medium',  label:'中单',      align:'right'},
    {key:'net_small',   label:'小单',      align:'right'},
  ];

  let html = '<table class="sf-table"><tr>';
  cols.forEach(c => {
    const active = c.key === _sfSortCol;
    const arrow = active ? (_sfSortDir === 'desc' ? ' ▼' : ' ▲') : '';
    html += `<th class="sf-th" data-key="${c.key}" style="text-align:${c.align}">${c.label}${arrow}</th>`;
  });
  html += '</tr>';

  sorted.forEach(s => {
    const nm = Number(s.net_main || 0);
    const cls = nm >= 0 ? 'pos' : 'neg';
    const pct = maxAbs > 0 ? Math.abs(nm) / maxAbs : 0;
    const barDir = nm >= 0 ? 'right' : 'left';
    html += `<tr class="sf-row" data-sector="${escHtml(s.sector_name)}">
      <td class="sf-name">${escHtml(s.sector_name)}</td>
      <td class="sf-num ${cls}">
        <div class="sf-bar-wrap">
          <div class="sf-bar sf-bar-${barDir}" style="width:${(pct*100).toFixed(0)}%"></div>
          <span class="sf-bar-val">${fmtNum(nm)}</span>
        </div>
      </td>
      <td class="sf-num">${fmtNum(s.net_super_large)}</td>
      <td class="sf-num">${fmtNum(s.net_large)}</td>
      <td class="sf-num">${fmtNum(s.net_medium)}</td>
      <td class="sf-num">${fmtNum(s.net_small)}</td>
    </tr>`;
  });
  html += '</table>';
  wrap.innerHTML = html;

  document.querySelectorAll('.sf-th').forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.key;
      if(key === _sfSortCol) _sfSortDir = _sfSortDir === 'desc' ? 'asc' : 'desc';
      else { _sfSortCol = key; _sfSortDir = 'desc'; }
      _sfRender();
    });
  });
  document.querySelectorAll('.sf-row').forEach(row => {
    row.addEventListener('click', () => {
      const sector = row.dataset.sector;
      applySectorFilter(sector);
    });
  });
}

document.getElementById('sfTabs').addEventListener('click', (e) => {
  const tab = e.target.closest('.sf-tab');
  if(!tab) return;
  document.querySelectorAll('.sf-tab').forEach(t => t.classList.remove('active'));
  tab.classList.add('active');
  _sfSortCol = 'net_main';
  _sfSortDir = 'desc';
  _sfLoad(tab.dataset.period);
});

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
function openDetail(code, name){
  const modal = document.getElementById('detailModal');
  document.getElementById('detailTitle').textContent = code + ' ' + (name || '');
  modal.style.display = 'flex';
  document.getElementById('detailMeta').innerHTML = '<span class="loading" style="padding:8px">加载K线数据...</span>';
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
  document.getElementById('detailModal').style.display = 'none';
}

async function fetchKlineAndRender(code, name){
  try{
    const r = await fetch('/api/etf/kline?code=' + code + '&limit=120');
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
  }catch(e){
    document.getElementById('detailMeta').innerHTML = '<span class="error" style="padding:8px">加载失败: ' + e.message + '</span>';
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
  const body = document.getElementById('sectorFlowBody');
  const arrow = document.querySelector('.sf-arrow');
  if (body.style.display === 'none') {
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
